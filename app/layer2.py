import json
import math
import os
import re
import time
import uuid

import numpy as np
import pandas as pd
import pulp

import llm as _llm

ALPHA_EQUITY = 25.0
CBC_OPTIONS = dict(msg=0, timeLimit=120, gapRel=0.001)
MIN_SURPLUS_TO_SHIP = 5
ACCESS_PENALTY_KM = 15.0
DOS_TARGET = 30.0

W_CATEGORY = {"emergency": 3.0, "essential": 2.0, "routine": 1.0}
W_ACCESS = {1: 1.5, 2: 1.2, 3: 1.0}

FACTOR_VALUE_COLUMNS = {
    "drug_category": "category",
    "accessibility": "accessibility_score",
    "stockout_history": "stockouts_6m",
    "days_of_stock": "days_of_stock",
    "regional_mmr": "regional_mmr",
}
FACTOR_WEIGHT_COLUMNS = {
    "drug_category": "w_category",
    "accessibility": "w_access",
    "stockout_history": "w_stockout",
    "days_of_stock": "w_dos",
    "regional_mmr": "w_mmr",
}

FACTOR_PHRASES = {
    "drug_category": "the drug urgency category",
    "accessibility": "poor road accessibility",
    "stockout_history": "repeated recent stockouts",
    "days_of_stock": "a depleted stock position",
    "regional_mmr": "high regional maternal mortality",
}

EXPLAINER_SYSTEM_PROMPT = (
    "You write short allocation justifications for district pharmacy (IFK) staff. "
    "You receive a JSON payload describing one decision made by a deterministic optimizer. "
    "Explain in two to four plain professional English sentences why this decision was made, "
    "citing the dominant priority factors. Use only numbers that literally appear in the payload. "
    "Never invent, recompute, or round numbers. Do not use emojis or bullet points."
)

N_ALLOCATION_EXPLANATIONS = 12

# Module-level state loaded from master data
_facilities: pd.DataFrame = None
_drugs: pd.DataFrame = None
_facility_names: dict = None
_drug_names: dict = None
_cc_drug_ids: set = None
_mmr_max: float = None


def load_master_data(data_dir: str):
    """Load facilities and drugs master tables. Must be called at service startup."""
    global _facilities, _drugs, _facility_names, _drug_names, _cc_drug_ids, _mmr_max

    _facilities = pd.read_csv(os.path.join(data_dir, "facilities.csv"))
    _drugs = pd.read_csv(os.path.join(data_dir, "drugs.csv"))

    _facility_names = _facilities.set_index("facility_id")["name"].to_dict()
    _drug_names = _drugs.set_index("drug_id")["drug_name"].to_dict()
    _cc_drug_ids = set(_drugs.loc[_drugs["requires_cold_chain"], "drug_id"])
    _mmr_max = float(_facilities["regional_mmr"].max())


def _build_allocation_input(l1_forecasts: list[dict], stockout_history: list[dict] | None) -> pd.DataFrame:
    """Merge forecast with master data and compute priority scores."""
    forecast_df = pd.DataFrame(l1_forecasts)
    forecast_df.rename(columns={"total_requirement": "requirement"}, inplace=True)

    stockout_df = (
        pd.DataFrame(stockout_history)
        if stockout_history
        else pd.DataFrame(columns=["facility_id", "drug_id", "stockouts_6m"])
    )

    alloc = (
        forecast_df
        .merge(_drugs[["drug_id", "drug_name", "category", "requires_cold_chain"]], on="drug_id")
        .merge(
            _facilities[[
                "facility_id", "name", "remoteness", "accessibility_score",
                "regional_mmr", "has_cold_chain", "storage_capacity_total",
                "cold_chain_capacity", "distance_to_ifk_km",
            ]],
            on="facility_id",
        )
        .merge(stockout_df, on=["facility_id", "drug_id"], how="left")
    )
    alloc["stockouts_6m"] = alloc["stockouts_6m"].fillna(0).astype(int)

    daily_need = alloc["forecast_demand"] / 30.0
    alloc["days_of_stock"] = np.where(
        daily_need > 0,
        (alloc["current_stock"] / daily_need.replace(0, np.nan)).round(1),
        np.inf,
    )

    alloc["w_category"] = alloc["category"].map(W_CATEGORY)
    alloc["w_access"] = alloc["accessibility_score"].map(W_ACCESS)
    alloc["w_stockout"] = np.minimum(2.0, 1.0 + 0.2 * alloc["stockouts_6m"])
    alloc["w_dos"] = 1.0 + np.maximum(
        0.0, (DOS_TARGET - np.minimum(alloc["days_of_stock"], DOS_TARGET)) / DOS_TARGET
    )
    alloc["w_mmr"] = 1.0 + alloc["regional_mmr"] / _mmr_max

    weight_cols = ["w_category", "w_access", "w_stockout", "w_dos", "w_mmr"]
    alloc["priority_score"] = alloc[weight_cols].prod(axis=1).round(3)

    return alloc[alloc["requirement"] > 0].reset_index(drop=True)


def _compute_capacity_headroom(alloc_input: pd.DataFrame, forecast_df: pd.DataFrame) -> tuple[dict, dict]:
    """Compute remaining storage and cold chain capacity per facility."""
    facility_totals = forecast_df.groupby("facility_id")["current_stock"].sum().to_dict()
    cc_current = (
        forecast_df[forecast_df["drug_id"].isin(_cc_drug_ids)]
        .groupby("facility_id")["current_stock"].sum().to_dict()
    )
    facility_meta = _facilities.set_index("facility_id")

    storage_headroom = {
        fid: max(0, int(facility_meta.loc[fid, "storage_capacity_total"] - facility_totals.get(fid, 0)))
        for fid in _facilities["facility_id"]
        if fid in facility_meta.index
    }
    cc_headroom = {
        fid: max(0, int(facility_meta.loc[fid, "cold_chain_capacity"] - cc_current.get(fid, 0)))
        for fid in _facilities["facility_id"]
        if fid in facility_meta.index
    }
    return storage_headroom, cc_headroom


def _solve_central_allocation(
    alloc_input: pd.DataFrame,
    supply: dict,
    storage_headroom: dict,
    cc_headroom: dict,
) -> tuple[pd.DataFrame, str]:
    """Build and solve the central allocation MILP. Returns (result_df, solver_status)."""
    prob = pulp.LpProblem("central_allocation", pulp.LpMaximize)

    x = {}
    for row in alloc_input.itertuples():
        if row.requires_cold_chain and not row.has_cold_chain:
            continue
        x[(row.facility_id, row.drug_id)] = pulp.LpVariable(
            f"x_{row.facility_id}_{row.drug_id}",
            lowBound=0,
            upBound=int(row.requirement),
            cat="Integer",
        )

    drug_cells: dict[str, list] = {}
    for fid, did in x:
        drug_cells.setdefault(did, []).append(fid)

    z = {
        did: pulp.LpVariable(f"z_{did}", lowBound=0, upBound=1)
        for did in drug_cells
    }

    weight = alloc_input.set_index(["facility_id", "drug_id"])
    prob += (
        pulp.lpSum(
            weight.loc[key, "priority_score"] * var / weight.loc[key, "requirement"]
            for key, var in x.items()
        )
        + ALPHA_EQUITY * pulp.lpSum(z.values())
    )

    for did, fids in drug_cells.items():
        prob += pulp.lpSum(x[(fid, did)] for fid in fids) <= supply.get(did, 0)
        for fid in fids:
            req = weight.loc[(fid, did), "requirement"]
            prob += z[did] * req <= x[(fid, did)]

    for fid in _facilities["facility_id"]:
        fid_vars = [var for (f, d), var in x.items() if f == fid]
        if fid_vars:
            prob += pulp.lpSum(fid_vars) <= storage_headroom.get(fid, 0)
        cc_vars = [var for (f, d), var in x.items() if f == fid and d in _cc_drug_ids]
        if cc_vars:
            prob += pulp.lpSum(cc_vars) <= cc_headroom.get(fid, 0)

    prob.solve(pulp.PULP_CBC_CMD(**CBC_OPTIONS))
    status = pulp.LpStatus[prob.status]

    allocated = {key: int(var.value() or 0) for key, var in x.items()}
    result = alloc_input.copy()
    result["allocated"] = result.apply(
        lambda r: allocated.get((r["facility_id"], r["drug_id"]), 0), axis=1
    )
    return result, status


def _run_redistribution(post: pd.DataFrame) -> pd.DataFrame:
    """Min-cost transshipment per drug for surplus-to-deficit transfers."""
    post = post.copy()
    post["available"] = post["current_stock"] + post["allocated"]
    post["surplus"] = np.maximum(0, post["available"] - post["requirement"])
    post["deficit"] = np.maximum(0, post["requirement"] - post["available"])

    facility_meta = _facilities.set_index("facility_id")
    dist = facility_meta["distance_to_ifk_km"].to_dict()
    acc = facility_meta["accessibility_score"].to_dict()

    def route_cost(i, j):
        return round(
            dist[i] + dist[j] + ACCESS_PENALTY_KM * ((3 - acc[i]) + (3 - acc[j])), 1
        )

    transfer_rows = []
    for drug_id, group in post.groupby("drug_id"):
        sources = group[group["surplus"] >= MIN_SURPLUS_TO_SHIP]
        sinks = group[group["deficit"] >= 1]
        if sources.empty or sinks.empty:
            continue

        prob = pulp.LpProblem(f"redistribution_{drug_id}", pulp.LpMaximize)
        t = {}
        costs = {}
        for src in sources.itertuples():
            for snk in sinks.itertuples():
                key = (src.facility_id, snk.facility_id)
                costs[key] = route_cost(*key)
                t[key] = pulp.LpVariable(
                    f"t_{drug_id}_{key[0]}_{key[1]}", lowBound=0, cat="Integer"
                )

        big = 10.0 * max(costs.values())
        prob += pulp.lpSum((big - costs[key]) * var for key, var in t.items())

        for src in sources.itertuples():
            prob += pulp.lpSum(
                t[(src.facility_id, snk.facility_id)] for snk in sinks.itertuples()
            ) <= int(src.surplus)
        for snk in sinks.itertuples():
            prob += pulp.lpSum(
                t[(src.facility_id, snk.facility_id)] for src in sources.itertuples()
            ) <= int(snk.deficit)

        prob.solve(pulp.PULP_CBC_CMD(**CBC_OPTIONS))

        for (src_id, snk_id), var in t.items():
            qty = int(var.value() or 0)
            if qty > 0:
                transfer_rows.append({
                    "drug_id": drug_id,
                    "from_facility_id": src_id,
                    "to_facility_id": snk_id,
                    "transfer_qty": qty,
                    "route_cost_index": costs[(src_id, snk_id)],
                })

    cols = ["drug_id", "from_facility_id", "to_facility_id", "transfer_qty", "route_cost_index"]
    return pd.DataFrame(transfer_rows, columns=cols) if transfer_rows else pd.DataFrame(columns=cols)


def _numeric_tokens(text: str) -> set:
    return set(re.findall(r"\d+(?:\.\d+)?", text.replace(",", "")))


def _generate_llm_text(payload: dict) -> str:
    messages = [
        {"role": "system", "content": EXPLAINER_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload)},
    ]
    return _llm.generate_reply(messages, max_new_tokens=500).strip()


def _faithful_explanation(payload: dict, template_fn) -> tuple[str, str]:
    """LLM text accepted only if numerically faithful; else template fallback."""
    allowed = _numeric_tokens(json.dumps(payload))
    for _ in range(2):
        text = _generate_llm_text(payload)
        if _numeric_tokens(text) <= allowed:
            return text, f"{_llm.LLM_MODEL_ID}-4bit"
    return template_fn(payload), "template-fallback"


def _template_allocation_text(payload: dict) -> str:
    leads = [FACTOR_PHRASES[f["factor"]] for f in payload["priority_factors"][:2]]
    text = (
        f"{payload['facility']} receives {payload['allocated_units']} of the "
        f"{payload['requirement_units']} required units of {payload['drug']} "
        f"({payload['coverage_pct']} percent coverage). "
        f"The allocation was prioritized mainly due to {leads[0]} and {leads[1]}. "
        f"District supply covers {payload['district_supply_pct_of_requirement']} percent "
        f"of the total requirement for this drug, so full coverage is not possible this cycle."
    )
    if payload["unmet_units"] > 0:
        text += (
            f" The remaining {payload['unmet_units']} units are deferred to "
            f"inter facility redistribution or the next resupply."
        )
    return text


def _template_transfer_text(payload: dict) -> str:
    return (
        f"{payload['transfer_qty']} units of {payload['drug']} move from "
        f"{payload['from_facility']} to {payload['to_facility']}. "
        f"The sender holds stock above its own requirement while the receiver "
        f"still faces a deficit after the central allocation, and this route has "
        f"the lowest cost index ({payload['route_cost_index']}) among available pairs."
    )


def _template_summary_text(payload: dict) -> str:
    return (
        f"For {payload['forecast_period']}, the IFK allocates "
        f"{payload['total_allocated_units']} of {payload['total_requirement_units']} "
        f"required units across {payload['facilities_served']} facilities. "
        f"{payload['unmet_after_allocation_units']} units remain unmet after central allocation, "
        f"of which {payload['units_redistributed']} units are covered by inter facility transfers."
    )


def _build_allocation_payload(row, supply: dict, district_requirement: dict) -> dict:
    factors = sorted(
        [
            {
                "factor": factor,
                "value": str(getattr(row, FACTOR_VALUE_COLUMNS[factor])),
                "contribution": round(math.log(getattr(row, FACTOR_WEIGHT_COLUMNS[factor])), 2),
            }
            for factor in FACTOR_VALUE_COLUMNS
        ],
        key=lambda f: f["contribution"],
        reverse=True,
    )
    supply_pct = int(round(
        100 * supply.get(row.drug_id, 0) / max(1, district_requirement[row.drug_id])
    ))
    return {
        "facility": _facility_names[row.facility_id],
        "remoteness": row.remoteness,
        "drug": _drug_names[row.drug_id],
        "category": row.category,
        "requirement_units": int(row.requirement),
        "allocated_units": int(row.allocated),
        "coverage_pct": int(round(100 * row.allocated / row.requirement)),
        "unmet_units": int(row.requirement - row.allocated),
        "district_supply_pct_of_requirement": supply_pct,
        "priority_factors": factors[:3],
    }


def run_allocation(
    l1_forecasts: list[dict],
    ifk_stock: list[dict],
    run_id: str | None = None,
    stockout_history: list[dict] | None = None,
) -> dict:
    """
    Full Layer 2 pipeline: MILP allocation + redistribution + LLM justifications.

    l1_forecasts: list of {facility_id, drug_id, forecast_demand, current_stock,
                            total_requirement, forecast_period}
    ifk_stock: list of {drug_id, available_units}
    run_id: optional identifier for this run
    stockout_history: optional list of {facility_id, drug_id, stockouts_6m};
                      if omitted stockouts_6m = 0 for all cells

    Returns dict matching l2_output.json schema.
    """
    if run_id is None:
        run_id = f"L2-{uuid.uuid4().hex[:8].upper()}"

    forecast_period = l1_forecasts[0]["forecast_period"] if l1_forecasts else ""
    forecast_df = pd.DataFrame(l1_forecasts)

    supply = {item["drug_id"]: int(item["available_units"]) for item in ifk_stock}
    alloc_input = _build_allocation_input(l1_forecasts, stockout_history)
    storage_headroom, cc_headroom = _compute_capacity_headroom(alloc_input, forecast_df)

    allocation_result, solver_status = _solve_central_allocation(
        alloc_input, supply, storage_headroom, cc_headroom
    )

    if solver_status != "Optimal":
        raise RuntimeError(f"MILP solver returned non-optimal status: {solver_status}")

    allocation_result["coverage_ratio"] = (
        allocation_result["allocated"] / allocation_result["requirement"]
    ).round(3)
    allocation_result["unmet_demand"] = (
        allocation_result["requirement"] - allocation_result["allocated"]
    )
    post_daily_need = allocation_result["forecast_demand"] / 30.0
    allocation_result["post_allocation_days_of_stock"] = np.where(
        post_daily_need > 0,
        (allocation_result["current_stock"] + allocation_result["allocated"])
        / post_daily_need.replace(0, np.nan),
        np.inf,
    ).round(1)
    allocation_result["post_allocation_days_of_stock"] = (
        allocation_result["post_allocation_days_of_stock"].replace(np.inf, 999.0)
    )

    redistribution = _run_redistribution(allocation_result)

    # Decision factor attribution
    factor_lookup = {}
    for row in allocation_result.itertuples():
        factor_lookup[(row.facility_id, row.drug_id)] = sorted(
            [
                {
                    "factor": factor,
                    "value": str(getattr(row, FACTOR_VALUE_COLUMNS[factor])),
                    "contribution": round(math.log(getattr(row, FACTOR_WEIGHT_COLUMNS[factor])), 4),
                }
                for factor in FACTOR_VALUE_COLUMNS
            ],
            key=lambda f: f["contribution"],
            reverse=True,
        )

    # Justification generation
    district_requirement = (
        allocation_result.groupby("drug_id")["requirement"].sum().to_dict()
    )

    justification_lookup: dict[tuple, str] = {}

    explained = allocation_result[allocation_result["unmet_demand"] > 0].nlargest(
        N_ALLOCATION_EXPLANATIONS, "priority_score"
    )
    for row in explained.itertuples():
        payload = _build_allocation_payload(row, supply, district_requirement)
        text, _ = _faithful_explanation(payload, _template_allocation_text)
        justification_lookup[("allocation", row.facility_id, row.drug_id)] = text
        time.sleep(2)

    for row in redistribution.itertuples():
        payload = {
            "drug": _drug_names[row.drug_id],
            "from_facility": _facility_names[row.from_facility_id],
            "to_facility": _facility_names[row.to_facility_id],
            "transfer_qty": int(row.transfer_qty),
            "route_cost_index": float(row.route_cost_index),
        }
        text, _ = _faithful_explanation(payload, _template_transfer_text)
        justification_lookup[("redistribution", row.to_facility_id, row.drug_id)] = text
        time.sleep(2)

    total_alloc = int(allocation_result["allocated"].sum())
    total_req = int(allocation_result["requirement"].sum())
    units_redistributed = int(redistribution["transfer_qty"].sum()) if len(redistribution) else 0
    facilities_served = int((allocation_result.groupby("facility_id")["allocated"].sum() > 0).sum())
    unmet = int(allocation_result["unmet_demand"].sum())

    time.sleep(2)
    summary_payload = {
        "forecast_period": str(forecast_period),
        "total_requirement_units": total_req,
        "total_allocated_units": total_alloc,
        "unmet_after_allocation_units": unmet,
        "units_redistributed": units_redistributed,
        "facilities_served": facilities_served,
    }
    summary_text, _ = _faithful_explanation(summary_payload, _template_summary_text)

    coverage_by_drug = (
        allocation_result.groupby("drug_id")
        .apply(lambda g: g["allocated"].sum() / g["requirement"].sum(), include_groups=False)
    )

    allocation_entries = []
    for row in allocation_result.itertuples():
        allocation_entries.append({
            "facility_id": row.facility_id,
            "facility_name": _facility_names[row.facility_id],
            "drug_id": row.drug_id,
            "drug_name": _drug_names[row.drug_id],
            "category": row.category,
            "requirement": int(row.requirement),
            "allocated": int(row.allocated),
            "coverage_ratio": round(float(row.allocated / row.requirement), 3),
            "unmet": int(row.requirement - row.allocated),
            "priority_score": float(row.priority_score),
            "factors": factor_lookup[(row.facility_id, row.drug_id)],
            "justification": justification_lookup.get(
                ("allocation", row.facility_id, row.drug_id)
            ),
        })

    redistribution_entries = []
    for row in redistribution.itertuples():
        redistribution_entries.append({
            "drug_id": row.drug_id,
            "drug_name": _drug_names[row.drug_id],
            "from_facility_id": row.from_facility_id,
            "to_facility_id": row.to_facility_id,
            "transfer_qty": int(row.transfer_qty),
            "route_cost_index": float(row.route_cost_index),
            "justification": justification_lookup.get(
                ("redistribution", row.to_facility_id, row.drug_id)
            ),
        })

    return {
        "run_id": run_id,
        "forecast_period": str(forecast_period),
        "summary": {
            **summary_payload,
            "min_drug_coverage": round(float(coverage_by_drug.min()), 3),
            "n_transfers": len(redistribution),
            "district_summary": summary_text,
        },
        "allocations": allocation_entries,
        "redistribution": redistribution_entries,
    }
