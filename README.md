# MaternaLink

AI-driven maternal medicine logistics for Indonesian *puskesmas*, built for the ASEAN AI Hackathon 2026.

---

## Problem

Maternal medicine stockouts in remote and archipelagic Indonesia are a structural problem: reactive LPLPO workflows, 30–60 day delivery lead times, and Eastern Indonesia facilities with stockout rates above 75%. These gaps contribute to preventable postpartum hemorrhage, which accounts for 27–48% of maternal deaths in the region.

MaternaLink targets the IFK (*Instalasi Farmasi Kabupaten/Kota*) hub layer, each responsible for ~30 puskesmas, with predictive inventory allocation and explainable recommendations that IFK staff can act on without needing a data science background.

---

## Architecture

The system is a three-layer AI pipeline. Layer 0 extracts probable conditions from raw anamnesis transcripts and merges them with structured diagnoses. Layer 1 translates those condition estimates into per-drug demand forecasts with adaptive buffers. Layer 2 runs a MILP optimizer to allocate IFK warehouse stock across facilities equitably, then generates LLM-written justifications for each decision.

**Key design constraint:** the LLM never decides quantities. All numeric allocation decisions come from the deterministic MILP solver. The LLM only verbalizes those decisions.

---

## Data Flow

### Layer 0: NLP & Data Standardization

**Reads:**

| File | Key columns used |
| --- | --- |
| `master/facilities.csv` | `facility_id`, `has_lab` |
| `master/conditions.csv` | `condition_id`, `prior_prevalence` |
| `master/kb_symptom_condition.csv` | `symptom_id`, `condition_id`, `likelihood`, `no_lab_weight` |
| `transactional/diagnoses_monthly.csv` | `facility_id`, `period`, `condition_id`, `case_count` |
| `transactional/anamnesis_records.csv` | `anamnesis_id`, `facility_id`, `period`, `transcript` |

**Processing:**

- Symptom extraction: Qwen3-4B-Instruct 4-bit NF4, zero-shot, constrained to closed vocabulary G01–G15; CPU fallback = keyword regex
- HITL flag: records with confidence < 0.85 or no symptoms extracted are flagged for midwife validation
- Bayesian scoring: posterior `P(condition | symptoms)` = prior_prevalence × Π likelihood × no_lab_weight multiplier; indication threshold 0.25
- Aggregation: sum indicated posteriors per (facility, period, condition); merge with manual diagnoses (non-overlapping by construction)

**Writes:**

| File | Description |
| --- | --- |
| `layer0_output/l0_extraction_results.csv` | Per-anamnesis extraction detail + HITL flag |
| `layer0_output/l0_condition_posteriors.csv` | Per-(anamnesis, condition) posterior score + evidence |
| `layer0_output/l0_condition_estimates.csv` | **L0→L1 contract**: `facility_id`, `period`, `condition_id`, `manual_cases`, `anamnesis_indicated_cases`, `estimated_total_cases`, `confidence_level` |

---

### Layer 1: Demand Forecasting

**Reads:**

| File | Key columns used |
| --- | --- |
| `layer0_output/l0_condition_estimates.csv` | `estimated_total_cases` per facility/period/condition |
| `master/facilities.csv` | `lead_time_days`, `rainy_season_access`, `accessibility_score`, `has_cold_chain` |
| `master/drugs.csv` | `drug_id`, `standard_daily_dose`, `treatment_duration_days`, `requires_cold_chain` |
| `master/kb_condition_drug.csv` | `condition_id`, `drug_id` |
| `transactional/context_monthly.csv` | `facility_id`, `period`, `season` |
| `transactional/stock_monthly.csv` | `facility_id`, `drug_id`, `period`, `closing_stock` |

**Processing:**

- **Categorical encoding:** `facility_id`, `drug_id`, and `rainy_season_access` are integer-encoded with saved `LabelEncoder` instances (`le_facility.pkl`, `drug_enc.pkl`, `le_rainy.pkl`)
- **Static exog lookup:** time-invariant attributes per (facility, drug) — `lead_time_days`, `rainy_season_enc`, `accessibility_score`, `standard_daily_dose`, `treatment_duration_days` — cached in `static_exog_lookup.csv`
- **Feature engineering:** lag bank of `closing_stock` at 1, 2, 3, 6, 12 months; lag bank of `estimated_total_cases` and derived `estimated_consumption` at 1–3 months; rolling mean & std at windows 3, 6, 12 months (computed from lag-1 to avoid leakage); cyclic month encoding (`sin`/`cos`); binary flags `is_november`, `is_high_season` (Oct–Dec), `is_low_season` (Apr); interaction terms `cases × accessibility_score`, `lead_time × accessibility_score`, `standard_daily_dose × treatment_duration_days`, `lag_1 × accessibility_score`
- **Target transform:** `log1p(closing_stock)` before training; `expm1` after prediction; predictions clipped to ≥ 0
- **Model:** global XGBoost (`n_estimators=1500`, `learning_rate=0.02`, `max_depth=6`, `min_child_weight=5`, `subsample=0.85`, `colsample_bytree=0.85`); trained on all (facility, drug) combinations jointly; early stopping on log-RMSE with patience 50
- **Train/val split:** cutoff `2024-11-01`; last 3 months (Dec 2024, Jan 2025, Feb 2025) held out; November 2024 spike fully in training
- **Buffer (rule-based, post-inference):** baseline 20%; +5 pp if `lead_time_days > 7`, +10 pp if `> 14`; +5 pp if `accessibility_score < 0.75`, +10 pp if `< 0.5`

**Writes:**

| File | Description |
| --- | --- |
| `layer1_output/l1_forecast.csv` | `facility_id`, `forecast_period`, `drug_id`, `forecast_demand`, `buffer_pct`, `buffer_units`, `total_requirement`, `current_stock` |
| `model/xgboost_drug_forecast_v3.json` | Trained XGBoost model |
| `model/static_exog_lookup.csv` | Time-invariant feature lookup per (facility, drug) |
| `model/feature_cols.pkl` | Ordered feature column list for inference |
| `model/le_facility.pkl` / `le_drug.pkl` / `le_rainy.pkl` | Fitted label encoders |

---

### Layer 2: Explainable Allocation Recommender

**Reads:**

| File | Key columns used |
| --- | --- |
| `layer1_mock/l1_forecast_mock.csv` | `facility_id`, `drug_id`, `total_requirement`, `current_stock` |
| `layer1_mock/ifk_stock_mock.csv` | `drug_id`, `available_stock` |
| `master/facilities.csv` | `remoteness`, `regional_mmr`, `storage_capacity_total`, `distance_to_ifk_km` |
| `master/drugs.csv` | `category` (emergency/essential/routine) |
| `transactional/stock_monthly.csv` | Last 6 months — stockout history per (facility, drug) |

**Processing:**

- Priority weight: `w = w_category × w_access × w_stockout × w_days_of_stock × w_mmr`
- Central MILP: maximize `Σ(w × allocated/requirement) + 25.0 × Σ(equity_floor[drug])` subject to per-drug supply, per-facility storage/cold-chain, and demand caps
- CBC solver flags: `msg=0, timeLimit=120, gapRel=0.001`
- Inter-facility redistribution: min-cost transshipment on surpluses ≥ 5 units; route cost = distance + accessibility penalty
- Factor attribution: log-space additive decomposition of priority weights for auditability
- LLM justification: Qwen3-4B-Instruct (fallback: deterministic templates); faithfulness guard — generated text may only reference numbers present in the LP payload

**Writes:**

| File | Description |
| --- | --- |
| `layer2_output/l2_allocation.csv` | `facility_id`, `drug_id`, `requirement`, `allocated`, `coverage_ratio`, `priority_score`, `post_allocation_days_of_stock`, `unmet_demand` |
| `layer2_output/l2_redistribution.csv` | `drug_id`, `from_facility_id`, `to_facility_id`, `transfer_qty`, `route_cost_index` |
| `layer2_output/l2_decision_factors.csv` | Per-(facility, drug, factor) weight contribution in log-space |
| `layer2_output/l2_justifications.csv` | LLM-generated natural language per allocation/redistribution decision |
| `layer2_output/l2_output.json` | Consolidated dashboard payload (allocations + factors + justifications) |

---

## Notebooks

| Notebook | Layer | Purpose |
| --- | --- | --- |
| `notebooks/01_data_simulator.ipynb` | Data | Synthetic master data + 36-month transaction history |
| `notebooks/02_layer0_extraction.ipynb` | L0 | NLP symptom extraction + Bayesian condition scoring |
| `notebooks/03_layer1_forecast.ipynb` | L1 | XGBoost demand forecasting model — training, evaluation, and 1-month-ahead forecast |
| `notebooks/04_layer2_allocation.ipynb` | L2 | MILP allocation + LLM explanation generation |

---

## Data Schema

- **Facilities:** 30 puskesmas (PKM-001..030), typed by accessibility, cold chain availability, and lead time
- **Drugs:** 30 maternal drugs (OBT-001..030), categorized as `darurat / esensial / rutin`
- **Conditions:** 16 maternal conditions (K01–K16) including Hyperemesis Gravidarum and Calcium Deficiency
- **Symptoms:** 15 closed-vocabulary symptoms (G01–G15)
- **Cold chain drugs:** OBT-007, OBT-010, OBT-011, OBT-019 — zeroed for non-equipped facilities

The Layer 0 → Layer 1 contract is `l0_condition_estimates.csv`: posterior case counts per facility/period/condition, produced by L0 and consumed by L1.

---

## Technical Decisions

| Component | Choice | Rationale |
| --- | --- | --- |
| Symptom extraction | Qwen3-4B-Instruct 4-bit NF4, zero-shot | Runs on T4; CPU fallback = keyword regex |
| Demand forecasting | XGBoost (global model, log1p target) | Single model across all facility-drug combos; lag + rolling + calendar + interaction features; MAE ~109 units, R² 0.907 on held-out 3-month validation |
| Allocation core | PuLP MILP + CBC solver | Deterministic, auditable, handles equity constraints explicitly |
| Equity objective | Per-drug maximin, `ALPHA_EQUITY=25` | Prevents the optimizer from ignoring low-volume remote facilities |
| Synthetic data | Rule-based probabilistic simulator | Enforces clinical/geographic constraints; reproducible at `SEED=42` |

**CBC solver flags** (mandatory, prevents hang on maximin MILP):
```python
msg=0, timeLimit=120, gapRel=0.001
```

---

