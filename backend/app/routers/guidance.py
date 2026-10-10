from __future__ import annotations

from fastapi import APIRouter, Request

from app.errors import AppError, request_id_of
from app.guidance import budget_check, methodology
from app.schemas import BudgetRequest, BudgetResponse, ErrorResponse, MethodologyResponse
from app.scoring import compute_report

router = APIRouter(prefix="/api", tags=["guidance"])


@router.post(
    "/budget",
    response_model=BudgetResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def budget(body: BudgetRequest, request: Request) -> BudgetResponse:
    """Compare an equipment budget (JOD) with the category's equipment cost range. Pure Python, no LLM."""
    record = request.app.state.store.get(body.category_id)
    if record is None:
        raise AppError(404, "unknown_category", f"Unknown category_id {body.category_id!r}.")
    report = compute_report(record)
    capex = report.capex_usd_range
    if capex is None or capex.min is None or capex.max is None:
        raise AppError(422, "capex_unavailable", "This category has no equipment cost range.")
    return BudgetResponse(request_id=request_id_of(request), **budget_check(report, body.budget_jod))


@router.get("/methodology", response_model=MethodologyResponse)
def get_methodology(request: Request) -> MethodologyResponse:
    """How the score is calculated (en and ar). Static text built from the scoring constants."""
    return MethodologyResponse(request_id=request_id_of(request), **methodology())
