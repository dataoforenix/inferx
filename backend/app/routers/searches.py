from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.errors import request_id_of
from app.schemas import TopSearchesResponse

router = APIRouter(prefix="/api", tags=["searches"])


@router.get("/searches/top", response_model=TopSearchesResponse)
def top_searches(request: Request, limit: int = Query(default=10, ge=1, le=50)) -> TopSearchesResponse:
    """Most analysed products (complete and market-preview results). Only exists while the response cache is on."""
    return TopSearchesResponse(request_id=request_id_of(request), searches=request.app.state.cache.top_searches(limit))
