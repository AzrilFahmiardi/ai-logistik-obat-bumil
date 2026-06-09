import os
import math
import pickle
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import HTTPException

from schema import ForecastRequest, ForecastResponse

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "model")

_model: xgb.XGBRegressor = None
_feature_cols: list = None
_static_lookup: pd.DataFrame = None
_le_facility = None
_le_drug = None
_le_rainy = None


def load_artifacts():
    global _model, _feature_cols, _static_lookup, _le_facility, _le_drug, _le_rainy

    _model = xgb.XGBRegressor()
    _model.load_model(os.path.join(MODEL_DIR, "xgboost_drug_forecast_v3.json"))

    with open(os.path.join(MODEL_DIR, "feature_cols.pkl"), "rb") as f:
        _feature_cols = pickle.load(f)

    _static_lookup = pd.read_csv(os.path.join(MODEL_DIR, "static_exog_lookup.csv"))

    _le_facility = joblib.load(os.path.join(MODEL_DIR, "le_facility.pkl"))
    _le_drug = joblib.load(os.path.join(MODEL_DIR, "le_drug.pkl"))
    _le_rainy = joblib.load(os.path.join(MODEL_DIR, "le_rainy.pkl"))


def _encode_label(encoder, value: str, field_name: str) -> int:
    classes = list(encoder.classes_)
    if value not in classes:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown {field_name} value '{value}'. Valid values: {classes}",
        )
    return int(encoder.transform([value])[0])


def _get_static_exog(facility_id: str, drug_id: str, req: ForecastRequest) -> dict:
    row = _static_lookup[
        (_static_lookup["facility_id"] == facility_id)
        & (_static_lookup["drug_id"] == drug_id)
    ]
    if not row.empty:
        r = row.iloc[0]
        return {
            "facility_enc": int(r["facility_enc"]),
            "drug_enc": int(r["drug_enc"]),
            "lead_time_days": float(r["lead_time_days"]),
            "rainy_season_enc": int(r["rainy_season_enc"]),
            "accessibility_score": float(r["accessibility_score"]),
            "standard_daily_dose": float(r["standard_daily_dose"]),
            "treatment_duration_days": float(r["treatment_duration_days"]),
        }

    facility_enc = _encode_label(_le_facility, facility_id, "facility_id")
    drug_enc = _encode_label(_le_drug, drug_id, "drug_id")
    rainy_enc = _encode_label(_le_rainy, req.rainy_season_access, "rainy_season_access")

    return {
        "facility_enc": facility_enc,
        "drug_enc": drug_enc,
        "lead_time_days": req.lead_time_days,
        "rainy_season_enc": rainy_enc,
        "accessibility_score": req.accessibility_score,
        "standard_daily_dose": req.standard_daily_dose,
        "treatment_duration_days": req.treatment_duration_days,
    }


def _build_feature_vector(req: ForecastRequest, exog: dict, period: pd.Timestamp) -> dict:
    closing_stock = req.closing_stock
    estimated_total_cases = req.estimated_total_cases
    estimated_consumption = (
        estimated_total_cases
        * exog["standard_daily_dose"]
        * exog["treatment_duration_days"]
    )

    month = period.month
    year = period.year
    quarter = period.quarter
    month_sin = math.sin(2 * math.pi * month / 12)
    month_cos = math.cos(2 * math.pi * month / 12)
    is_november = int(month == 11)
    is_high_season = int(month in [10, 11, 12])
    is_low_season = int(month == 4)

    accessibility_score = exog["accessibility_score"]
    lead_time_days = exog["lead_time_days"]
    standard_daily_dose = exog["standard_daily_dose"]
    treatment_duration_days = exog["treatment_duration_days"]

    return {
        "lag_1": closing_stock,
        "lag_2": closing_stock,
        "lag_3": closing_stock,
        "lag_6": closing_stock,
        "lag_12": closing_stock,
        "cases_lag_1": estimated_total_cases,
        "cases_lag_2": estimated_total_cases,
        "cases_lag_3": estimated_total_cases,
        "cons_lag_1": estimated_consumption,
        "cons_lag_2": estimated_consumption,
        "cons_lag_3": estimated_consumption,
        "roll_mean_3": closing_stock,
        "roll_mean_6": closing_stock,
        "roll_mean_12": closing_stock,
        "roll_std_3": 0.0,
        "roll_std_6": 0.0,
        "roll_std_12": 0.0,
        "facility_enc": exog["facility_enc"],
        "drug_enc": exog["drug_enc"],
        "lead_time_days": lead_time_days,
        "rainy_season_enc": exog["rainy_season_enc"],
        "accessibility_score": accessibility_score,
        "standard_daily_dose": standard_daily_dose,
        "treatment_duration_days": treatment_duration_days,
        "month": month,
        "month_sin": month_sin,
        "month_cos": month_cos,
        "year": year,
        "quarter": quarter,
        "is_november": is_november,
        "is_high_season": is_high_season,
        "is_low_season": is_low_season,
        "cases_x_access": estimated_total_cases * accessibility_score,
        "lead_x_access": lead_time_days * accessibility_score,
        "nov_x_cases": is_november * estimated_total_cases,
        "dose_x_duration": standard_daily_dose * treatment_duration_days,
        "lag1_x_access": closing_stock * accessibility_score,
    }


def _compute_buffer(lead_time_days: float, accessibility_score: float, forecast_demand: int) -> dict:
    base_buffer_pct = 0.20

    if lead_time_days > 14:
        base_buffer_pct += 0.10
    elif lead_time_days > 7:
        base_buffer_pct += 0.05

    if accessibility_score < 0.5:
        base_buffer_pct += 0.10
    elif accessibility_score < 0.75:
        base_buffer_pct += 0.05

    buffer_pct = round(base_buffer_pct, 4)
    buffer_units = math.ceil(forecast_demand * buffer_pct)
    total_requirement = forecast_demand + buffer_units

    return {
        "buffer_pct": buffer_pct,
        "buffer_units": buffer_units,
        "total_requirement": total_requirement,
    }


def run_forecast(req: ForecastRequest) -> ForecastResponse:
    try:
        period = pd.Timestamp(req.period)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid period format. Use YYYY-MM-DD.")

    exog = _get_static_exog(req.facility_id, req.drug_id, req)
    feat = _build_feature_vector(req, exog, period)

    X = pd.DataFrame([feat])[_feature_cols]
    pred_log = _model.predict(X)[0]
    forecast_demand = int(max(0, round(float(np.expm1(pred_log)))))

    buffer = _compute_buffer(exog["lead_time_days"], exog["accessibility_score"], forecast_demand)

    return ForecastResponse(
        facility_id=req.facility_id,
        drug_id=req.drug_id,
        period=req.period,
        forecast_demand=forecast_demand,
        buffer_pct=buffer["buffer_pct"],
        buffer_units=buffer["buffer_units"],
        total_requirement=buffer["total_requirement"],
        current_stock=int(req.closing_stock),
    )
