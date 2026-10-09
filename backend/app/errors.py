"""Uniform error responses: every error body is {"error": {code, message, request_id, details?}}."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas import ErrorBody, ErrorResponse

logger = logging.getLogger("sannaha")


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: list[dict] | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_response(request: Request, status_code: int, code: str, message: str, details: list[dict] | None = None):
    rid = request_id_of(request)
    body = ErrorResponse(error=ErrorBody(code=code, message=message, request_id=rid, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True), headers={"X-Request-ID": rid})


_HTTP_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 413: "payload_too_large",
               415: "unsupported_media_type", 422: "validation_error", 503: "service_unavailable"}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return error_response(request, exc.status_code, _HTTP_CODES.get(exc.status_code, "http_error"), str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        # Drop the raw "input" echo so uploaded content / long text is never reflected back.
        details = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()]
        return error_response(request, 422, "validation_error", "Request validation failed.", details)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error request_id=%s", request_id_of(request))
        return error_response(request, 500, "internal_error", "An unexpected error occurred.")
