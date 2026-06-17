---
title: MaternaLink AI
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# MaternaLink AI

REST API for AI-driven maternal medicine logistics symptom extraction, demand forecasting, and equitable drug allocation for Indonesian puskesmas.

Built for the ASEAN AI Hackathon 2026, Team Furap Jogja, Gadjah Mada University.

## Base URL

```
https://azrilfahmiardi-maternalink-ai.hf.space
```

## Interactive Docs

| UI | URL |
| --- | --- |
| Swagger UI | `/docs` |
| ReDoc | `/redoc` |

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Service health check |
| GET | `/api/v1/data/facilities` | List all 30 puskesmas facilities |
| GET | `/api/v1/data/drugs` | List all 30 maternal drugs |
| GET | `/api/v1/data/conditions` | List all 16 maternal conditions |
| GET | `/api/v1/layer1/forecast/batch` | Pre-computed forecasts for all facility-drug pairs (query: `facility_id`, `drug_id`) |
| POST | `/api/v1/layer1/forecast` | Single facility-drug demand forecast |
| POST | `/api/v1/layer0/extract` | NLP symptom extraction + Bayesian condition scoring from anamnesis transcripts |
| POST | `/api/v1/layer2/allocate` | MILP equitable allocation + LLM justifications |

## Example Requests

### Health check

```bash
curl https://azrilfahmiardi-maternalink-ai.hf.space/health
```


### Layer 0: Symptom extraction

```bash
curl -X POST https://azrilfahmiardi-maternalink-ai.hf.space/api/v1/layer0/extract \
  -H "Content-Type: application/json" \
  -d '{
    "period": "2025-03-01",
    "records": [
      {
        "record_id": "ANM-000001",
        "facility_id": "PKM-001",
        "transcript": "Patient presents with severe nausea and vomiting for 3 days, dizziness, and upper abdominal pain. Pregnancy at 10 weeks.",
        "has_lab": false
      }
    ],
    "manual_diagnoses": null
  }'
```

### Layer 1: Demand forecast

```bash
curl -X POST https://azrilfahmiardi-maternalink-ai.hf.space/api/v1/layer1/forecast \
  -H "Content-Type: application/json" \
  -d '{
    "facility_id": "PKM-001",
    "drug_id": "OBT-001",
    "period": "2025-03-01",
    "closing_stock": 120,
    "estimated_total_cases": 15,
    "lead_time_days": 14,
    "rainy_season_access": "cut_off",
    "accessibility_score": 0.3,
    "standard_daily_dose": 6,
    "treatment_duration_days": 7
  }'
```

### Layer 2: Allocation

```bash
curl -X POST https://azrilfahmiardi-maternalink-ai.hf.space/api/v1/layer2/allocate \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "march-2025",
    "l1_forecasts": [
      {"facility_id": "PKM-001", "drug_id": "OBT-001", "forecast_demand": 42, "current_stock": 15, "total_requirement": 53, "forecast_period": "2025-03-01"},
      {"facility_id": "PKM-002", "drug_id": "OBT-001", "forecast_demand": 55, "current_stock": 20, "total_requirement": 69, "forecast_period": "2025-03-01"}
    ],
    "ifk_stock": [
      {"drug_id": "OBT-001", "available_units": 80}
    ],
    "stockout_history": null
  }'
```

> Layer 2 runs MILP solving + multiple LLM calls. Expect 3-8 minutes for a full 30-facility run.

## Run Locally

```bash
git clone https://github.com/AzrilFahmiardi/ai-logistik-obat-bumil.git
cd ai-logistik-obat-bumil
echo "GROQ_API_KEY=your_key_here" > .env
export $(cat .env | xargs) && conda run -n ml uvicorn main:app --app-dir app --host 0.0.0.0 --port 8000
```

Run tests:

```bash
python test_api.py                                                              # local
python test_api.py --base-url https://azrilfahmiardi-maternalink-ai.hf.space   # live
```

## Stack

- **Layer 0**: Qwen3-32B via Groq API, zero-shot symptom extraction (G01-G15) and Bayesian condition scoring (K01-K16)
- **Layer 1**: XGBoost, per-facility-drug demand forecast with lag features, accessibility buffers, and seasonal adjustments
- **Layer 2**: PuLP CBC MILP, equitable allocation with maximin equity objective and Qwen3-32B natural language justifications; faithfulness guard ensures the LLM cites only numbers from the LP solution
