import json
import os

import numpy as np
import pandas as pd

import llm as _llm

LLM_MODEL_ID = _llm.LLM_MODEL_ID

EPSILON = 0.02
INDICATION_THRESHOLD = 0.25
HITL_THRESHOLD = 0.85

SYMPTOM_CUES = {
    "G01": "fever, high temperature, running hot",
    "G02": "chills, shivering, cold sweats",
    "G03": "nausea, vomiting, cannot keep food down",
    "G04": "fatigue, weakness, exhaustion, always tired",
    "G05": "headache, dizziness, room spinning",
    "G06": "swelling of face, legs, or feet",
    "G07": "pain or burning when urinating",
    "G08": "abnormal or smelly vaginal discharge",
    "G09": "blurred or hazy vision",
    "G10": "burning or sharp pain in the upper stomach or below the chest",
    "G11": "shortness of breath, difficulty breathing",
    "G12": "yellowish skin or eyes, jaundice",
    "G13": "leg cramps, bone or calf pain",
    "G14": "prolonged sadness, anxiety, hopelessness, frequent crying",
    "G15": "constipation, bloating, no bowel movement",
}

JSON_RETRY_MESSAGE = (
    "Your previous reply was not valid JSON matching the schema. "
    "Respond again with only the JSON object."
)

# Module-level state
_kb_lookup: dict = None
_condition_priors: dict = None
_valid_symptom_ids: set = None
_has_lab_map: dict = None
_symptom_names: dict = None
_system_prompt: str = None


def load_artifacts(data_dir: str):
    """Load knowledge base and build extraction prompt. Must be called at service startup."""
    global _kb_lookup, _condition_priors, _valid_symptom_ids
    global _has_lab_map, _symptom_names, _system_prompt

    kb = pd.read_csv(os.path.join(data_dir, "kb_symptom_condition.csv"))
    conditions = pd.read_csv(os.path.join(data_dir, "conditions.csv"))
    facilities = pd.read_csv(os.path.join(data_dir, "facilities.csv"))

    _symptom_names = (
        kb[["symptom_id", "symptom_name"]]
        .drop_duplicates()
        .set_index("symptom_id")["symptom_name"]
        .to_dict()
    )
    _valid_symptom_ids = set(_symptom_names)
    _has_lab_map = facilities.set_index("facility_id")["has_lab"].to_dict()

    _kb_lookup = {
        (row.symptom_id, row.condition_id): (row.likelihood, row.no_lab_weight)
        for row in kb.itertuples()
    }
    _condition_priors = (
        conditions.set_index("condition_id")["prior_prevalence"].to_dict()
    )

    vocab_lines = "\n".join(
        f"- {sid}: {_symptom_names[sid]} (cues: {SYMPTOM_CUES[sid]})"
        for sid in sorted(_symptom_names)
    )
    _system_prompt = (
        "You are a clinical information extraction assistant for maternal health visit notes.\n"
        "Identify which symptoms from the fixed catalog below are explicitly mentioned in the transcript.\n\n"
        f"Symptom catalog:\n{vocab_lines}\n\n"
        "Rules:\n"
        "- Respond with valid JSON only, no other text.\n"
        '- Schema: {"symptoms": [{"symptom_id": "G01", "confidence": 0.95}]}\n'
        "- Use only symptom_id values from the catalog.\n"
        "- Report a symptom only if the transcript actually mentions it. Do not infer diagnoses or unstated symptoms.\n"
        "- confidence is your certainty between 0 and 1 that the symptom is mentioned.\n"
        '- If no catalog symptom is mentioned, respond with {"symptoms": []}.'
    )


def _parse_extraction_response(text: str) -> list | None:
    """Parse LLM reply into [(symptom_id, confidence)] or None on failure."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    items = payload.get("symptoms")
    if not isinstance(items, list):
        return None
    parsed = []
    for item in items:
        if not isinstance(item, dict):
            return None
        symptom_id = item.get("symptom_id")
        if symptom_id not in _valid_symptom_ids:
            continue
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            return None
        parsed.append((symptom_id, float(np.clip(confidence, 0.0, 1.0))))
    return parsed


def _extract_llm(transcript: str) -> tuple[list, bool]:
    """Return ([(symptom_id, confidence)], parse_failed) for one transcript."""
    messages = [
        {"role": "system", "content": _system_prompt},
        {"role": "user", "content": f"Transcript: {transcript}"},
    ]
    reply = _llm.generate_reply(messages, max_new_tokens=800)
    parsed = _parse_extraction_response(reply)
    if parsed is None:
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": JSON_RETRY_MESSAGE})
        parsed = _parse_extraction_response(_llm.generate_reply(messages, max_new_tokens=800))
    if parsed is None:
        return [], True
    return parsed, False


def _condition_posteriors(symptoms: list, has_lab: bool) -> tuple[dict, dict]:
    """Return (posterior dict, evidence dict) for a validated symptom set."""
    scores = {}
    evidence = {}
    for condition_id, prior in _condition_priors.items():
        score = prior
        terms = {}
        for symptom_id in symptoms:
            entry = _kb_lookup.get((symptom_id, condition_id))
            if entry is None:
                likelihood = EPSILON
            else:
                likelihood = entry[0] * (entry[1] if not has_lab else 1.0)
            score *= likelihood
            terms[symptom_id] = round(likelihood, 3)
        scores[condition_id] = score
        evidence[condition_id] = terms
    total = sum(scores.values())
    if total <= 0:
        uniform = 1.0 / len(scores)
        return {c: uniform for c in scores}, evidence
    return {c: s / total for c, s in scores.items()}, evidence


def run_extraction(
    records: list[dict],
    period: str,
    manual_diagnoses: list[dict] | None = None,
) -> dict:
    """
    Process a batch of transcript records through the full Layer 0 pipeline.

    records: list of {record_id, facility_id, transcript, has_lab (optional)}
    period: ISO date string YYYY-MM-DD
    manual_diagnoses: optional list of {facility_id, condition_id, case_count}

    Returns dict with keys: extraction_results, condition_posteriors, condition_estimates
    """
    extraction_rows = []
    posterior_rows = []

    for record in records:
        record_id = record["record_id"]
        facility_id = record["facility_id"]
        transcript = record["transcript"]
        has_lab = record.get("has_lab")
        if has_lab is None:
            has_lab = bool(_has_lab_map.get(facility_id, False))

        symptoms_raw, parse_failed = _extract_llm(transcript)
        confidences = [c for _, c in symptoms_raw]
        min_confidence = min(confidences) if confidences else 0.0
        hitl_flag = bool(parse_failed or min_confidence < HITL_THRESHOLD)
        validated = sorted(s for s, _ in symptoms_raw)

        extraction_rows.append({
            "record_id": record_id,
            "facility_id": facility_id,
            "period": period,
            "extracted_symptoms": json.dumps(
                [{"symptom_id": s, "confidence": round(c, 3)} for s, c in symptoms_raw]
            ),
            "min_confidence": round(min_confidence, 3),
            "hitl_flag": hitl_flag,
            "validated_symptoms": json.dumps(validated),
            "extraction_model": f"{LLM_MODEL_ID}-4bit",
        })

        posteriors, evidence = _condition_posteriors(validated, has_lab)
        for condition_id, posterior in posteriors.items():
            if posterior < 0.01:
                continue
            posterior_rows.append({
                "record_id": record_id,
                "facility_id": facility_id,
                "period": period,
                "condition_id": condition_id,
                "posterior": round(posterior, 4),
                "indicated": posterior >= INDICATION_THRESHOLD,
                "evidence": json.dumps(evidence[condition_id]),
            })

    extraction_df = pd.DataFrame(extraction_rows)
    posteriors_df = pd.DataFrame(posterior_rows) if posterior_rows else pd.DataFrame(
        columns=["record_id", "facility_id", "period", "condition_id",
                 "posterior", "indicated", "evidence"]
    )

    # Aggregate to condition estimates (L0 -> L1 contract)
    indicated = posteriors_df[posteriors_df["indicated"]].copy()
    record_confidence = extraction_df[["record_id", "min_confidence"]].copy()
    record_confidence["record_confidence"] = record_confidence["min_confidence"].where(
        ~extraction_df["hitl_flag"], 1.0
    )

    if not indicated.empty:
        indicated = indicated.merge(
            record_confidence[["record_id", "record_confidence"]], on="record_id"
        )
        anamnesis_agg = (
            indicated.groupby(["facility_id", "period", "condition_id"])
            .agg(
                anamnesis_indicated_cases=("posterior", "sum"),
                mean_record_confidence=("record_confidence", "mean"),
            )
            .reset_index()
        )
    else:
        anamnesis_agg = pd.DataFrame(
            columns=["facility_id", "period", "condition_id",
                     "anamnesis_indicated_cases", "mean_record_confidence"]
        )

    if manual_diagnoses:
        manual_df = pd.DataFrame(manual_diagnoses)
        manual_df["period"] = period
        manual_agg = (
            manual_df.groupby(["facility_id", "period", "condition_id"])["case_count"]
            .sum()
            .reset_index()
            .rename(columns={"case_count": "manual_cases"})
        )
    else:
        manual_agg = pd.DataFrame(
            columns=["facility_id", "period", "condition_id", "manual_cases"]
        )

    estimates = manual_agg.merge(
        anamnesis_agg, on=["facility_id", "period", "condition_id"], how="outer"
    )
    estimates["manual_cases"] = estimates["manual_cases"].fillna(0).astype(int)
    estimates["anamnesis_indicated_cases"] = (
        estimates["anamnesis_indicated_cases"].fillna(0.0).round(3)
    )
    estimates["estimated_total_cases"] = (
        estimates["manual_cases"] + estimates["anamnesis_indicated_cases"]
    ).round(3)

    def _confidence_level(row):
        if row["anamnesis_indicated_cases"] == 0:
            return "high"
        conf = row.get("mean_record_confidence", 1.0)
        if conf > 0.8:
            return "high"
        if conf >= 0.5:
            return "medium"
        return "low"

    estimates["confidence_level"] = estimates.apply(_confidence_level, axis=1)
    estimates = estimates.drop(columns=["mean_record_confidence"], errors="ignore")

    return {
        "extraction_results": extraction_df.to_dict(orient="records"),
        "condition_posteriors": posteriors_df.to_dict(orient="records"),
        "condition_estimates": estimates.to_dict(orient="records"),
    }
