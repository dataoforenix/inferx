"""Application factory. Importing this module has no side effects (no data is loaded)."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.formparsers import MultiPartParser

from app import __version__
from app.config import Settings, get_settings
from app.cache import AnalysisCache
from app.comtrade import ComtradeClient
from app.data_store import DataStore, load_categories
from app.demo import DemoCache
from app.errors import error_response, register_error_handlers
from app.llm import OpenAILLM, LLMClient
from app.pipeline import Pipeline
from app.rate_limit import LIMITED_PATHS, RateLimiter
from app.routers import analyze, guidance, meta, searches, whatif

logger = logging.getLogger("sannaha")

MULTIPART_OVERHEAD_BYTES = 256 * 1024  # form fields, boundaries and headers on top of the image


def create_app(
    settings: Settings | None = None, store: DataStore | None = None, llm: LLMClient | None = None,
    comtrade: ComtradeClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    # Fail fast: the app must not start on an invalid categories.csv.
    store = store or load_categories(settings.categories_csv)
    for warning in store.warnings:
        logger.warning("data: %s", warning)

    if llm is None and settings.llm_configured:
        llm = OpenAILLM(settings)
    demo = DemoCache.load(settings.demo_cache_dir, store.ids)
    for warning in demo.warnings:
        logger.warning("%s", warning)
    if settings.demo_mode:
        logger.warning("DEMO_MODE is on: /api/analyze serves prepared examples only")

    # Starlette spools uploads above spool_max_size to a temp file; keep every accepted upload in memory.
    max_request_bytes = settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES
    MultiPartParser.spool_max_size = max_request_bytes

    app = FastAPI(title="Sanna'ha API", version=__version__)
    app.state.settings = settings
    app.state.store = store
    app.state.llm = llm
    app.state.demo = demo
    # The market preview is live-only: no Comtrade client at all in demo mode.
    if comtrade is None and settings.market_preview and not settings.demo_mode:
        comtrade = ComtradeClient()
    app.state.pipeline = Pipeline(settings, store, llm, demo, comtrade)
    # Optional SQLite cache: off with DB_ENABLED=false and never in DEMO_MODE (then nothing changes at all).
    app.state.cache = (AnalysisCache(settings.db_path, settings.cache_ttl_hours * 3600)
                       if settings.db_enabled and not settings.demo_mode else None)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.rate_limiter = limiter

    @app.middleware("http")
    async def request_id_and_size_limit(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        started = time.perf_counter()
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > max_request_bytes:
            return error_response(request, 413, "payload_too_large", "Request body is too large.")
        # Without a declared length (chunked upload) the size can't be checked before Starlette
        # spools the body, which could spill to disk. Browsers always send it for form uploads.
        if request.method == "POST" and request.url.path == "/api/analyze" and not declared:
            return error_response(request, 411, "length_required", "Content-Length header is required.")
        if request.method == "POST" and request.url.path in LIMITED_PATHS:
            allowed, retry_after = limiter.check(request.client.host if request.client else "unknown")
            if not allowed:
                response = error_response(request, 429, "rate_limited",
                                          f"Too many requests. Try again in {retry_after} seconds.")
                response.headers["Retry-After"] = str(retry_after)
                return response
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        # Method, path, status and timing only: bodies (images, text) are never logged.
        logger.info("request_id=%s %s %s -> %s %.0fms", request.state.request_id, request.method,
                    request.url.path, response.status_code, (time.perf_counter() - started) * 1000)
        return response

    # Added last, so CORS is the outermost middleware: the 411/413/429 responses returned above
    # also carry the CORS headers, and the browser can read them (and Retry-After).
    wildcard = "*" in settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if wildcard else settings.cors_origins,
        allow_credentials=not wildcard,  # browsers reject credentials with a wildcard origin
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    register_error_handlers(app)
    app.include_router(meta.router)
    app.include_router(whatif.router)
    app.include_router(analyze.router)
    app.include_router(guidance.router)
    if app.state.cache is not None:  # the endpoint only exists while the cache is on
        app.include_router(searches.router)
    return app
