from pydantic import BaseModel, Field
from typing import List


class ForecastRequest(BaseModel):
    facility_id: str = Field(..., example="PKM-001")
    drug_id: str = Field(..., example="OBT-001")
    period: str = Field(..., example="2025-03-01", description="ISO date string YYYY-MM-DD, month is extracted automatically")
    closing_stock: float = Field(..., ge=0)
    estimated_total_cases: float = Field(..., ge=0)
    lead_time_days: float = Field(..., ge=0)
    rainy_season_access: str = Field(..., example="yes")
    accessibility_score: float = Field(..., ge=0, le=1)
    standard_daily_dose: float = Field(..., gt=0)
    treatment_duration_days: float = Field(..., gt=0)


class ForecastResponse(BaseModel):
    facility_id: str
    drug_id: str
    period: str
    forecast_demand: int
    buffer_pct: float
    buffer_units: int
    total_requirement: int
    current_stock: int
