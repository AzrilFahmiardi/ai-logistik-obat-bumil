from contextlib import asynccontextmanager
from fastapi import FastAPI

import layer1
from schema import ForecastRequest, ForecastResponse

TAGS = [
    {
        "name": "Forecast",
        "description": "One-month-ahead drug demand forecast endpoint.",
    },
    {
        "name": "Health",
        "description": "Service availability check.",
    },
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    layer1.load_artifacts()
    yield


app = FastAPI(
    title="MaternaLink AI",
    version="1.0.0",
    contact={
        "name": "MaternaLink Team — AI ASEAN Hackathon",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=TAGS,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.post(
    "/api/v1/layer1/forecast",
    response_model=ForecastResponse,
    tags=["Forecast"],
    summary="Forecast drug requirement",
    response_description="Forecast demand, buffer components, and total requirement for the next period",
)
def forecast(req: ForecastRequest) -> ForecastResponse:
    return layer1.run_forecast(req)


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
)
def health():
    return {"status": "ok"}
