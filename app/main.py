import os
from contextlib import asynccontextmanager
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import layer0
import layer1
import layer2
import llm
from schema import (
    AllocateRequest,
    AllocateResponse,
    BatchForecastItem,
    ConditionOut,
    DrugOut,
    ExtractRequest,
    ExtractResponse,
    FacilityOut,
    ForecastRequest,
    ForecastResponse,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "model")

# Master data loaded at startup for GET endpoints
_facilities_df: pd.DataFrame = None
_drugs_df: pd.DataFrame = None
_conditions_df: pd.DataFrame = None
_batch_forecast_df: pd.DataFrame = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _facilities_df, _drugs_df, _conditions_df, _batch_forecast_df

    # Layer 1 artifacts
    layer1.load_artifacts()

    # Layer 0 knowledge base
    layer0.load_artifacts(DATA_DIR)

    # Layer 2 master data
    layer2.load_master_data(DATA_DIR)

    # Shared LLM loaded once, used by both Layer 0 and Layer 2
    llm.load()

    # Master data for GET endpoints
    _facilities_df = pd.read_csv(os.path.join(DATA_DIR, "facilities.csv"))
    _drugs_df = pd.read_csv(os.path.join(DATA_DIR, "drugs.csv"))
    _conditions_df = pd.read_csv(os.path.join(DATA_DIR, "conditions.csv"))

    batch_path = os.path.join(MODEL_DIR, "forecast_march_2025.csv")
    if os.path.exists(batch_path):
        _batch_forecast_df = pd.read_csv(batch_path)

    yield


TAGS = [
    {"name": "Health", "description": "Service availability check."},
    {"name": "Master Data", "description": "Facility, drug, and condition reference tables."},
    {"name": "Layer 0", "description": "NLP symptom extraction and Bayesian condition scoring."},
    {"name": "Layer 1", "description": "XGBoost demand forecast per facility-drug."},
    {"name": "Layer 2", "description": "MILP equitable allocation and LLM justification."},
]

app = FastAPI(
    title="MaternaLink AI",
    version="1.0.0",
    contact={"name": "MaternaLink Team — AI ASEAN Hackathon"},
    license_info={"name": "MIT"},
    openapi_tags=TAGS,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"], summary="Health check")
def health():
    return {"status": "ok", "llm_loaded": llm.is_loaded()}


# ---------------------------------------------------------------------------
# Master Data
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/data/facilities",
    response_model=List[FacilityOut],
    tags=["Master Data"],
    summary="List all 30 puskesmas facilities",
)
def get_facilities():
    return _facilities_df.to_dict(orient="records")


@app.get(
    "/api/v1/data/drugs",
    response_model=List[DrugOut],
    tags=["Master Data"],
    summary="List all 30 maternal drugs",
)
def get_drugs():
    return _drugs_df.to_dict(orient="records")


@app.get(
    "/api/v1/data/conditions",
    response_model=List[ConditionOut],
    tags=["Master Data"],
    summary="List all 16 maternal health conditions",
)
def get_conditions():
    return _conditions_df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Layer 0
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/layer0/extract",
    response_model=ExtractResponse,
    tags=["Layer 0"],
    summary="Extract symptoms and estimate condition prevalence from anamnesis transcripts",
    response_description=(
        "Per-record extraction results with HITL flags, and aggregated condition "
        "estimates forming the Layer 1 input contract."
    ),
)
def extract(req: ExtractRequest) -> ExtractResponse:
    records = [r.model_dump() for r in req.records]
    manual = [m.model_dump() for m in req.manual_diagnoses] if req.manual_diagnoses else None

    result = layer0.run_extraction(records, req.period, manual_diagnoses=manual)

    return ExtractResponse(
        extraction_results=result["extraction_results"],
        condition_estimates=result["condition_estimates"],
    )


# ---------------------------------------------------------------------------
# Layer 1
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/layer1/forecast",
    response_model=ForecastResponse,
    tags=["Layer 1"],
    summary="Forecast drug requirement for one facility-drug-period",
    response_description="Forecast demand, buffer components, and total requirement for the next period.",
)
def forecast(req: ForecastRequest) -> ForecastResponse:
    return layer1.run_forecast(req)


@app.get(
    "/api/v1/layer1/forecast/batch",
    response_model=List[BatchForecastItem],
    tags=["Layer 1"],
    summary="Return pre-computed forecast for all 900 facility-drug combinations",
    response_description="One forecast row per (facility_id, drug_id) from the last training run.",
)
def forecast_batch(
    facility_id: Optional[str] = Query(None, description="Filter by facility_id"),
    drug_id: Optional[str] = Query(None, description="Filter by drug_id"),
):
    if _batch_forecast_df is None:
        raise HTTPException(
            status_code=503,
            detail="Batch forecast file not found. Run the Layer 1 training notebook first.",
        )
    df = _batch_forecast_df.copy()
    if facility_id:
        df = df[df["facility_id"] == facility_id]
    if drug_id:
        df = df[df["drug_id"] == drug_id]
    return df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Layer 2
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/layer2/allocate",
    response_model=AllocateResponse,
    tags=["Layer 2"],
    summary="Run MILP allocation and generate LLM justifications",
    response_description=(
        "Equitable drug allocation plan for all facilities, inter-facility redistribution "
        "recommendations, and natural language justifications for priority decisions."
    ),
)
def allocate(req: AllocateRequest) -> AllocateResponse:
    l1_forecasts = [item.model_dump() for item in req.l1_forecasts]
    ifk_stock = [item.model_dump() for item in req.ifk_stock]
    stockout_history = (
        [item.model_dump() for item in req.stockout_history]
        if req.stockout_history else None
    )

    result = layer2.run_allocation(
        l1_forecasts=l1_forecasts,
        ifk_stock=ifk_stock,
        run_id=req.run_id,
        stockout_history=stockout_history,
    )

    return AllocateResponse(**result)
