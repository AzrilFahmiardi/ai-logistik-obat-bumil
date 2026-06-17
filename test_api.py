"""
End-to-end API test for MaternaLink AI service.

Usage:
    python test_api.py
    python test_api.py --base-url https://azrilfahmiardi-maternalink-ai.hf.space
"""

import argparse
import json
import sys
import time

import httpx

TIMEOUT = 30.0
L2_TIMEOUT = 600.0

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

_failures = 0
_timings: list[tuple[str, float]] = []


def check(name: str, ok: bool, detail: str = ""):
    global _failures
    status = PASS if ok else FAIL
    suffix = f"  {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")
    if not ok:
        _failures += 1


def timed_get(client: httpx.Client, url: str, **kwargs) -> tuple[httpx.Response, float]:
    t0 = time.perf_counter()
    r = client.get(url, **kwargs)
    return r, round(time.perf_counter() - t0, 3)


def timed_post(client: httpx.Client, url: str, **kwargs) -> tuple[httpx.Response, float]:
    t0 = time.perf_counter()
    r = client.post(url, **kwargs)
    return r, round(time.perf_counter() - t0, 3)


def record(label: str, elapsed: float):
    _timings.append((label, elapsed))
    print(f"  time: {elapsed}s")


def test_health(client: httpx.Client, base: str):
    print("\n--- Health ---")
    r, t = timed_get(client, f"{base}/health", timeout=TIMEOUT)
    record("GET /health", t)
    check("status 200", r.status_code == 200, f"got {r.status_code}")
    d = r.json()
    check("status=ok", d.get("status") == "ok")
    check("llm_loaded=true", d.get("llm_loaded") is True)


def test_master_data(client: httpx.Client, base: str):
    print("\n--- Master Data ---")

    r, t = timed_get(client, f"{base}/api/v1/data/facilities", timeout=TIMEOUT)
    record("GET /data/facilities", t)
    check("facilities status 200", r.status_code == 200)
    fac = r.json()
    check("facilities count 30", len(fac) == 30, f"got {len(fac)}")
    check("facility_id field present", "facility_id" in fac[0])

    r, t = timed_get(client, f"{base}/api/v1/data/drugs", timeout=TIMEOUT)
    record("GET /data/drugs", t)
    check("drugs status 200", r.status_code == 200)
    check("drugs count 30", len(r.json()) == 30, f"got {len(r.json())}")

    r, t = timed_get(client, f"{base}/api/v1/data/conditions", timeout=TIMEOUT)
    record("GET /data/conditions", t)
    check("conditions status 200", r.status_code == 200)
    check("conditions count 16", len(r.json()) == 16, f"got {len(r.json())}")


def test_layer1(client: httpx.Client, base: str):
    print("\n--- Layer 1: Forecast ---")

    r, t = timed_get(client, f"{base}/api/v1/layer1/forecast/batch", timeout=TIMEOUT)
    record("GET /layer1/forecast/batch (all)", t)
    check("batch status 200", r.status_code == 200)
    batch = r.json()
    check("batch non-empty", len(batch) >= 1, f"got {len(batch)}")
    check("predicted_closing_stock field present", "predicted_closing_stock" in batch[0])

    r, t = timed_get(
        client, f"{base}/api/v1/layer1/forecast/batch",
        params={"facility_id": "PKM-001"}, timeout=TIMEOUT,
    )
    record("GET /layer1/forecast/batch?facility_id=PKM-001", t)
    check("batch filter status 200", r.status_code == 200)
    filtered = r.json()
    check("batch filter facility_id correct", all(x["facility_id"] == "PKM-001" for x in filtered))

    payload = {
        "facility_id": "PKM-001",
        "drug_id": "OBT-001",
        "period": "2025-03-01",
        "closing_stock": 120,
        "estimated_total_cases": 15,
        "lead_time_days": 14,
        "rainy_season_access": "cut_off",
        "accessibility_score": 0.3,
        "standard_daily_dose": 6,
        "treatment_duration_days": 7,
    }
    r, t = timed_post(client, f"{base}/api/v1/layer1/forecast", json=payload, timeout=TIMEOUT)
    record("POST /layer1/forecast", t)
    check("forecast status 200", r.status_code == 200, f"got {r.status_code}")
    d = r.json()
    check("forecast_demand present", "forecast_demand" in d)
    check("total_requirement >= forecast_demand", d.get("total_requirement", 0) >= d.get("forecast_demand", 0))


def test_layer0(client: httpx.Client, base: str):
    print("\n--- Layer 0: Symptom Extraction ---")
    payload = {
        "period": "2025-03-01",
        "records": [
            {
                "record_id": "ANM-TEST-001",
                "facility_id": "PKM-001",
                "transcript": (
                    "Patient presents with severe nausea and vomiting for 3 days, "
                    "unable to keep food down, dizziness, and upper abdominal pain. "
                    "Pregnancy at 10 weeks."
                ),
                "has_lab": False,
            }
        ],
        "manual_diagnoses": None,
    }
    r, t = timed_post(client, f"{base}/api/v1/layer0/extract", json=payload, timeout=60.0)
    record("POST /layer0/extract (1 transcript)", t)
    check("extract status 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        return
    d = r.json()
    results = d.get("extraction_results", [])
    check("extraction_results has 1 row", len(results) == 1)
    if results:
        row = results[0]
        symptoms = json.loads(row.get("extracted_symptoms", "[]"))
        check("symptoms extracted", len(symptoms) > 0, f"got {symptoms}")
        check("hitl_flag is bool", isinstance(row.get("hitl_flag"), bool))
    estimates = d.get("condition_estimates", [])
    check("condition_estimates non-empty", len(estimates) >= 1, f"got {len(estimates)}")


def test_layer2(client: httpx.Client, base: str):
    print("\n--- Layer 2: MILP Allocation ---")
    payload = {
        "run_id": "test-run",
        "l1_forecasts": [
            {"facility_id": "PKM-001", "drug_id": "OBT-001", "forecast_demand": 42, "current_stock": 15, "total_requirement": 53, "forecast_period": "2025-03-01"},
            {"facility_id": "PKM-001", "drug_id": "OBT-002", "forecast_demand": 30, "current_stock": 10, "total_requirement": 38, "forecast_period": "2025-03-01"},
            {"facility_id": "PKM-002", "drug_id": "OBT-001", "forecast_demand": 55, "current_stock": 20, "total_requirement": 69, "forecast_period": "2025-03-01"},
            {"facility_id": "PKM-002", "drug_id": "OBT-002", "forecast_demand": 25, "current_stock": 8,  "total_requirement": 32, "forecast_period": "2025-03-01"},
        ],
        "ifk_stock": [
            {"drug_id": "OBT-001", "available_units": 80},
            {"drug_id": "OBT-002", "available_units": 45},
        ],
        "stockout_history": None,
    }
    r, t = timed_post(client, f"{base}/api/v1/layer2/allocate", json=payload, timeout=L2_TIMEOUT)
    record("POST /layer2/allocate (2 facilities, 2 drugs)", t)
    check("allocate status 200", r.status_code == 200, f"got {r.status_code}: {r.text[:300]}")
    if r.status_code != 200:
        return
    d = r.json()
    check("run_id present", "run_id" in d)
    allocs = d.get("allocations", [])
    check("allocations non-empty", len(allocs) >= 1)
    check("summary present", "summary" in d)
    with_just = [a for a in allocs if a.get("justification")]
    check("at least one LLM justification", len(with_just) >= 1, f"{len(with_just)}/{len(allocs)} have justification")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000", dest="base")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    print(f"Testing: {base}\n")

    with httpx.Client() as client:
        test_health(client, base)
        test_master_data(client, base)
        test_layer1(client, base)
        test_layer0(client, base)
        test_layer2(client, base)

    print(f"\n--- Inference times ---")
    total = 0.0
    for label, elapsed in _timings:
        print(f"  {elapsed:>8.3f}s  {label}")
        total += elapsed
    print(f"  {'':->8}  --------")
    print(f"  {total:>8.3f}s  total wall time")

    print(f"\n{'='*40}")
    if _failures == 0:
        print(f"{PASS} All tests passed.")
    else:
        print(f"{FAIL} {_failures} test(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
