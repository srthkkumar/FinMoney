from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from simulation import run_simulation, run_lever_analysis, ALLOCATIONS
from database import init_db, save_run, list_runs


class CustomAllocation(BaseModel):
    equity: float = Field(..., ge=0, le=1)
    debt: float = Field(..., ge=0, le=1)
    gold: float = Field(..., ge=0, le=1)

    @field_validator("gold")
    @classmethod
    def weights_must_sum_to_one(cls, gold, info):
        equity = info.data.get("equity", 0)
        debt = info.data.get("debt", 0)
        total = equity + debt + gold
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"equity + debt + gold must sum to 1.0 (got {total:.2f})"
            )
        return gold

app = FastAPI(
    title="SIP Monte Carlo Planner",
    description="A small personal-finance planning engine: simulates many "
                 "possible market futures across several asset allocations "
                 "and shows a range of outcomes instead of one guessed number.",
    version="0.1.0",
)

# Allow the static frontend (served from anywhere, incl. file://) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    current_age: int = Field(..., ge=18, le=70)
    retirement_age: int = Field(..., ge=19, le=75)
    monthly_income: float = Field(..., ge=0)
    monthly_expenses: float = Field(..., ge=0)
    current_savings: float = Field(0, ge=0)
    monthly_sip: float = Field(..., ge=0)
    custom_allocation: Optional[CustomAllocation] = None


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/allocations")
def get_allocations():
    """Returns the allocation presets available, so the frontend never
    hardcodes them."""
    return ALLOCATIONS


@app.post("/api/simulate")
def simulate(req: PlanRequest):
    if req.retirement_age <= req.current_age:
        raise HTTPException(400, "retirement_age must be greater than current_age")

    custom_weights = req.custom_allocation.dict() if req.custom_allocation else None

    result = run_simulation(
        current_age=req.current_age,
        retirement_age=req.retirement_age,
        monthly_income=req.monthly_income,
        monthly_expenses=req.monthly_expenses,
        current_savings=req.current_savings,
        monthly_sip=req.monthly_sip,
        custom_allocation=custom_weights,
    )

    lever = run_lever_analysis(
        current_age=req.current_age,
        retirement_age=req.retirement_age,
        current_savings=req.current_savings,
        base_monthly_sip=req.monthly_sip,
    )
    result["lever_analysis"] = lever

    run_id = save_run(inputs=req.dict(), summary={
        "monthly_surplus": result["monthly_surplus"],
        "balanced_median_final": result["allocations"]["balanced"]["final_corpus_percentiles"]["p50"],
    })
    result["run_id"] = run_id

    return result


@app.get("/api/history")
def history(limit: int = 20):
    return list_runs(limit=limit)
