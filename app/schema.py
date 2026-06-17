from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Layer 1 — Demand Forecast
# ---------------------------------------------------------------------------

class ForecastRequest(BaseModel):
    facility_id: str = Field(..., example="PKM-001")
    drug_id: str = Field(..., example="OBT-001")
    period: str = Field(..., example="2025-03-01", description="ISO date YYYY-MM-DD")
    closing_stock: float = Field(..., ge=0, example=120)
    estimated_total_cases: float = Field(..., ge=0, example=15)
    lead_time_days: float = Field(..., ge=0, example=14)
    rainy_season_access: str = Field(..., example="cut_off")
    accessibility_score: float = Field(..., ge=0, le=1, example=0.3)
    standard_daily_dose: float = Field(..., gt=0, example=6)
    treatment_duration_days: float = Field(..., gt=0, example=7)


class ForecastResponse(BaseModel):
    facility_id: str
    drug_id: str
    period: str
    forecast_demand: int
    buffer_pct: float
    buffer_units: int
    total_requirement: int
    current_stock: int


class BatchForecastItem(BaseModel):
    facility_id: str
    drug_id: str
    forecast_period: str
    predicted_closing_stock: float


# ---------------------------------------------------------------------------
# Layer 0 — Symptom Extraction + Condition Scoring
# ---------------------------------------------------------------------------

class ExtractRecord(BaseModel):
    record_id: str = Field(..., example="ANM-000001")
    facility_id: str = Field(..., example="PKM-001")
    transcript: str = Field(
        ...,
        description="Free-text patient anamnesis transcript in English",
        example=(
            "Patient presents with severe nausea and vomiting for 3 days, "
            "unable to keep food down, dizziness, and upper abdominal pain. "
            "Pregnancy at 10 weeks."
        ),
    )
    has_lab: Optional[bool] = Field(
        None,
        description="Whether the facility has a laboratory. Defaults to facility master data.",
    )


class ManualDiagnosis(BaseModel):
    facility_id: str
    condition_id: str
    case_count: int = Field(..., ge=0)


class ExtractRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "period": "2025-03-01",
                "records": [
                    {
                        "record_id": "ANM-000001",
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
        }
    }

    period: str = Field(..., example="2025-01-01", description="ISO date YYYY-MM-DD")
    records: List[ExtractRecord]
    manual_diagnoses: Optional[List[ManualDiagnosis]] = Field(
        None,
        description="Optional manual diagnosis counts to merge with anamnesis estimates.",
    )


class ExtractionResultItem(BaseModel):
    record_id: str
    facility_id: str
    period: str
    extracted_symptoms: str = Field(..., description="JSON array of {symptom_id, confidence}")
    min_confidence: float
    hitl_flag: bool = Field(..., description="True if record should be reviewed by a midwife")
    validated_symptoms: str = Field(..., description="JSON array of accepted symptom_id strings")
    extraction_model: str


class ConditionEstimateItem(BaseModel):
    facility_id: str
    period: str
    condition_id: str
    manual_cases: int
    anamnesis_indicated_cases: float
    estimated_total_cases: float
    confidence_level: str = Field(..., description="high / medium / low")


class ExtractResponse(BaseModel):
    extraction_results: List[ExtractionResultItem]
    condition_estimates: List[ConditionEstimateItem]


# ---------------------------------------------------------------------------
# Layer 2 — MILP Allocation
# ---------------------------------------------------------------------------

class IFKStockItem(BaseModel):
    drug_id: str = Field(..., example="OBT-001")
    available_units: int = Field(..., ge=0, example=500)


class StockoutHistoryItem(BaseModel):
    facility_id: str
    drug_id: str
    stockouts_6m: int = Field(..., ge=0, description="Stockout events in the last 6 months")


class L1ForecastItem(BaseModel):
    facility_id: str = Field(..., example="PKM-001")
    drug_id: str = Field(..., example="OBT-001")
    forecast_demand: int = Field(..., ge=0, example=42)
    current_stock: int = Field(..., ge=0, example=15)
    total_requirement: int = Field(..., ge=0, example=53)
    forecast_period: str = Field(..., description="ISO date YYYY-MM-DD", example="2025-03-01")


class AllocateRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "run_id": "march-2025",
                "l1_forecasts": [
                    {"facility_id": "PKM-001", "drug_id": "OBT-001", "forecast_demand": 42, "current_stock": 15, "total_requirement": 53, "forecast_period": "2025-03-01"},
                    {"facility_id": "PKM-001", "drug_id": "OBT-002", "forecast_demand": 30, "current_stock": 10, "total_requirement": 38, "forecast_period": "2025-03-01"},
                    {"facility_id": "PKM-002", "drug_id": "OBT-001", "forecast_demand": 55, "current_stock": 20, "total_requirement": 69, "forecast_period": "2025-03-01"},
                ],
                "ifk_stock": [
                    {"drug_id": "OBT-001", "available_units": 80},
                    {"drug_id": "OBT-002", "available_units": 30},
                ],
                "stockout_history": None,
            }
        }
    }

    l1_forecasts: List[L1ForecastItem]
    ifk_stock: List[IFKStockItem]
    run_id: Optional[str] = Field(None, description="Optional run identifier. Auto-generated if omitted.")
    stockout_history: Optional[List[StockoutHistoryItem]] = Field(
        None,
        description="Optional stockout counts per facility-drug. Defaults to 0 if omitted.",
    )


class AllocationFactor(BaseModel):
    factor: str
    value: str
    contribution: float = Field(..., description="log-space weight contribution")


class AllocationItem(BaseModel):
    facility_id: str
    facility_name: str
    drug_id: str
    drug_name: str
    category: str
    requirement: int
    allocated: int
    coverage_ratio: float
    unmet: int
    priority_score: float
    factors: List[AllocationFactor]
    justification: Optional[str]


class RedistributionItem(BaseModel):
    drug_id: str
    drug_name: str
    from_facility_id: str
    to_facility_id: str
    transfer_qty: int
    route_cost_index: float
    justification: Optional[str]


class AllocateSummary(BaseModel):
    forecast_period: str
    total_requirement_units: int
    total_allocated_units: int
    unmet_after_allocation_units: int
    units_redistributed: int
    facilities_served: int
    min_drug_coverage: float
    n_transfers: int
    district_summary: Optional[str]


class AllocateResponse(BaseModel):
    run_id: str
    forecast_period: str
    summary: AllocateSummary
    allocations: List[AllocationItem]
    redistribution: List[RedistributionItem]


# ---------------------------------------------------------------------------
# Master data read models
# ---------------------------------------------------------------------------

class FacilityOut(BaseModel):
    facility_id: str
    name: str
    district: str
    province: str
    remoteness: str
    accessibility_score: int
    has_cold_chain: bool
    has_lab: bool
    lead_time_days: float
    regional_mmr: float
    baseline_pregnancy_count: int


class DrugOut(BaseModel):
    drug_id: str
    drug_name: str
    category: str
    unit: str
    requires_cold_chain: bool
    standard_daily_dose: float
    treatment_duration_days: float


class ConditionOut(BaseModel):
    condition_id: str
    condition_name: str
    prior_prevalence: float
