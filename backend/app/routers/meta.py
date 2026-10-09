from __future__ import annotations

from fastapi import APIRouter, Request

from app import __version__
from app.errors import request_id_of
from app.schemas import CategoriesResponse, CategorySummary, ErrorResponse, HealthResponse

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    store = request.app.state.store
    # Analysis needs either a live LLM or demo mode; without both the service is degraded.
    can_analyze = settings.llm_configured or settings.demo_mode
    return HealthResponse(
        request_id=request_id_of(request),
        status="ok" if can_analyze else "degraded",
        version=__version__,
        demo_mode=settings.demo_mode,
        llm_configured=settings.llm_configured,
        categories_loaded=len(store.categories),
        data_warnings=[*store.warnings, *request.app.state.demo.warnings],
        demo_cache_entries=len(request.app.state.demo.entries),
        demo_cache_placeholder_entries=request.app.state.demo.placeholder_count,
    )


@router.get("/categories", response_model=CategoriesResponse, responses={500: {"model": ErrorResponse}})
def categories(request: Request) -> CategoriesResponse:
    store = request.app.state.store
    return CategoriesResponse(
        request_id=request_id_of(request),
        categories=[
            CategorySummary(
                category_id=c.category_id,
                name_en=c.name_en,
                name_ar=c.name_ar,
                description_en=c.description_en,
                hs6=c.hs6,
                data_status=c.data_status,
                is_placeholder_data=c.data_status == "TODO_REAL_DATA",
                missing_fields=c.missing_fields,
            )
            for c in store.list()
        ],
    )
