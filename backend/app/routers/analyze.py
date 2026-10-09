from __future__ import annotations

import time

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.errors import AppError, request_id_of
from app.image_utils import prepare_image
from app.schemas import AnalyzeResponse, ConfirmRequest, ErrorResponse, Language

router = APIRouter(prefix="/api", tags=["analyze"])

_ERRORS = {code: {"model": ErrorResponse} for code in (400, 404, 411, 413, 415, 422, 429, 502, 503)}


# Sync handlers: FastAPI runs them in a threadpool, so blocking LLM calls don't stall the event loop.
@router.post("/analyze", response_model=AnalyzeResponse, responses=_ERRORS)
def analyze(
    request: Request,
    image: UploadFile | None = File(default=None, description="JPEG, PNG or WebP, max 8 MB"),
    text: str | None = Form(default=None, description="Product description in Arabic or English"),
    language: Language = Form(default="en"),
) -> AnalyzeResponse:
    started = time.perf_counter()
    settings = request.app.state.settings

    text = (text or "").strip() or None
    if text and len(text) > settings.max_text_chars:
        raise AppError(400, "text_too_long", f"Description must be at most {settings.max_text_chars} characters.")

    prepared = None
    if image is not None and (image.filename or image.size):
        # Read at most limit+1 bytes from the in-memory upload; never written to disk.
        data = image.file.read(settings.max_upload_bytes + 1)
        prepared = prepare_image(data, image.content_type, settings.max_upload_bytes)

    if prepared is None and text is None:
        raise AppError(400, "empty_input", "Provide a product photo, a description, or both.")

    response = request.app.state.pipeline.analyze(request_id_of(request), prepared, text, language)
    return _with_total(response, started)


@router.post("/analyze/confirm", response_model=AnalyzeResponse, responses=_ERRORS)
def confirm(body: ConfirmRequest, request: Request) -> AnalyzeResponse:
    """Analyse the category the user confirmed after a needs_confirmation response."""
    started = time.perf_counter()
    response = request.app.state.pipeline.confirm(
        request_id_of(request), body.category_id, body.product, body.language)
    return _with_total(response, started)


def _with_total(response: AnalyzeResponse, started: float) -> AnalyzeResponse:
    response.timings_ms.total = round((time.perf_counter() - started) * 1000, 1)
    return response
