from __future__ import annotations

from fastapi import APIRouter, Request

from app.errors import AppError, request_id_of
from app.schemas import ErrorResponse, WhatIfRequest, WhatIfResponse
from app.scoring import compute_report

router = APIRouter(prefix="/api", tags=["whatif"])


@router.post(
    "/whatif",
    response_model=WhatIfResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def whatif(body: WhatIfRequest, request: Request) -> WhatIfResponse:
    """Recalculate a category's report with overrides. Pure Python, no LLM call."""
    record = request.app.state.store.get(body.category_id)
    if record is None:
        raise AppError(404, "unknown_category", f"Unknown category_id {body.category_id!r}.")

    baseline = compute_report(record)
    scenario = compute_report(record, body.overrides)
    delta = None
    if baseline.score is not None and scenario.score is not None:
        delta = round(scenario.score - baseline.score, 1)
    return WhatIfResponse(request_id=request_id_of(request), baseline=baseline, scenario=scenario, score_delta=delta)
