"""Application settings, read once from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Google Gemini through its OpenAI-compatible endpoint (the OpenAI SDK talks to it unchanged).
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.8-flash"

# .env values never override variables already set in the real environment.
load_dotenv(BACKEND_DIR / ".env", override=False)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw and raw.strip() else default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw and raw.strip() else default


def _path(name: str, default: str) -> Path:
    p = Path(os.getenv(name) or default)
    return p if p.is_absolute() else BACKEND_DIR / p


def _list(name: str, default: str) -> list[str]:
    raw = os.getenv(name) or default
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = field(repr=False)  # repr=False keeps the key out of logs
    openai_base_url: str  # OpenAI-compatible endpoint; the default is Google Gemini's
    normalize_model: str
    explain_model: str
    llm_timeout_seconds: float
    llm_max_retries: int
    demo_mode: bool
    cors_origins: list[str]
    log_level: str
    categories_csv: Path
    demo_cache_dir: Path
    max_upload_bytes: int
    max_text_chars: int
    confirm_confidence_threshold: float
    rate_limit_per_minute: int
    market_preview: bool = True  # UN Comtrade scan for physical products outside the categories

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_base_url=os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL,
        normalize_model=os.getenv("NORMALIZE_MODEL") or DEFAULT_MODEL,
        explain_model=os.getenv("EXPLAIN_MODEL") or DEFAULT_MODEL,
        llm_timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 60.0),
        llm_max_retries=_int("LLM_MAX_RETRIES", 2),
        demo_mode=_bool("DEMO_MODE", False),
        cors_origins=_list("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"),
        log_level=(os.getenv("LOG_LEVEL") or "INFO").upper(),
        categories_csv=_path("CATEGORIES_CSV", "data/categories.csv"),
        demo_cache_dir=_path("DEMO_CACHE_DIR", "data/demo_cache"),
        max_upload_bytes=_int("MAX_UPLOAD_MB", 8) * 1024 * 1024,
        max_text_chars=_int("MAX_TEXT_CHARS", 1000),
        confirm_confidence_threshold=_float("CONFIRM_CONFIDENCE_THRESHOLD", 0.7),
        rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", 30),
        market_preview=_bool("MARKET_PREVIEW", True),
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()
