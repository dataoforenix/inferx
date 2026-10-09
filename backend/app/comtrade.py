"""Jordan's yearly imports for one HS6 code from the public UN Comtrade preview API.

Used for the market preview (products outside the categories) and by scripts/refresh_trade_data.py.
No API key: https://comtradeapi.un.org/public/v1/preview/C/A/HS. The preview accepts one period per
request and rate-limits to roughly one request every 2-3 seconds per IP (HTTP 429 "Try again in N
seconds"), so the years are fetched sequentially, paced, most important first: the latest year (required),
then the first year (the growth trend), then the years in between (display only).

fetch() never raises. It returns None when the latest year can't be read (network error, timeout, HTTP
error, bad JSON, no data); an earlier year that fails or runs out of time is None in the series.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.schemas import IMPORT_YEARS

logger = logging.getLogger("sannaha.comtrade")

BASE_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
JORDAN = 400  # reporterCode
WORLD = 0  # partnerCode
TOTAL_TIMEOUT_SECONDS = 10.0
MIN_REQUEST_INTERVAL_SECONDS = 2.5  # measured: 2.0 s still gets occasional 429s
CACHE_TTL_SECONDS = 24 * 3600
_HS6 = re.compile(r"^\d{6}$")
_RETRY_IN = re.compile(r"try again in (\d+(?:\.\d+)?) second", re.IGNORECASE)


@dataclass(frozen=True)
class TradeSeries:
    hs6: str
    imports_usd: dict[int, float | None]  # CIF USD (primaryValue) per year; None = no data / not fetched
    import_weight_kg_2024: float | None  # netWgt for the latest year

    @property
    def complete(self) -> bool:
        return all(v is not None for v in self.imports_usd.values())


class _RateLimited(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after


def _urllib_get_json(url: str, timeout: float) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "sannaha-backend"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 (fixed https URL)
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            match = _RETRY_IN.search((exc.read() or b"").decode("utf-8", "replace"))
            raise _RateLimited(float(match.group(1)) if match else MIN_REQUEST_INTERVAL_SECONDS) from exc
        raise


def _total_row(data: Any) -> dict | None:
    """The world-total row: no partner2 / customs / transport-mode breakdown when those fields are present."""
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("partner2Code", 0) not in (0, None) or row.get("motCode", 0) not in (0, None):
            continue
        if row.get("customsCode", "C00") not in ("C00", None):
            continue
        return row
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or value < 0:
        return None
    return float(value)


def fetch_order(years: tuple[int, ...]) -> list[int]:
    """Latest year, first year, then the rest: the score needs only the first two."""
    return list(dict.fromkeys([years[-1], years[0], *years[1:-1]]))


class ComtradeClient:
    def __init__(self, get_json: Callable[[str, float], Any] = _urllib_get_json,
                 total_timeout: float = TOTAL_TIMEOUT_SECONDS, cache_ttl: float = CACHE_TTL_SECONDS,
                 min_interval: float = MIN_REQUEST_INTERVAL_SECONDS,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self._get_json = get_json
        self.total_timeout = total_timeout
        self.cache_ttl = cache_ttl
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._cache: dict[str, tuple[float, TradeSeries]] = {}
        self._cache_lock = threading.Lock()
        self._request_lock = threading.Lock()  # pacing is shared by every request to this client
        self._last_request: float | None = None

    @staticmethod
    def url(hs6: str, year: int) -> str:
        params = {"reporterCode": JORDAN, "partnerCode": WORLD, "flowCode": "M", "period": year, "cmdCode": hs6}
        return f"{BASE_URL}?{urlencode(params)}"

    def fetch(self, hs6: str, years: tuple[int, ...] = IMPORT_YEARS) -> TradeSeries | None:
        if not isinstance(hs6, str) or not _HS6.match(hs6):
            return None
        now = self._clock()
        with self._cache_lock:
            hit = self._cache.get(hs6)
            if hit and now - hit[0] < self.cache_ttl:
                return hit[1]
        try:
            series = self._fetch_uncached(hs6, years)
        except Exception as exc:  # never raise to the caller
            logger.warning("comtrade fetch failed hs6=%s: %s", hs6, type(exc).__name__)
            return None
        if series is not None:  # failures are not cached, so the next request tries again
            with self._cache_lock:
                self._cache[hs6] = (now, series)
        return series

    def _fetch_uncached(self, hs6: str, years: tuple[int, ...]) -> TradeSeries | None:
        deadline = self._clock() + self.total_timeout
        values: dict[int, float | None] = dict.fromkeys(years)
        weight = None
        latest = years[-1]
        for year in fetch_order(years):
            row = self._get_row(hs6, year, deadline)
            if row is False and year == latest:
                return None  # the latest year is required
            if row is False:
                continue
            values[year] = _number(row.get("primaryValue")) if row else None
            if year == latest:
                if values[year] is None:
                    logger.info("comtrade no data hs6=%s year=%s", hs6, year)
                    return None
                weight = _number(row.get("netWgt")) or None
        missing = [y for y, v in values.items() if v is None]
        if missing:
            logger.info("comtrade partial hs6=%s missing years=%s", hs6, missing)
        return TradeSeries(hs6=hs6, imports_usd=values, import_weight_kg_2024=weight)

    def _get_row(self, hs6: str, year: int, deadline: float) -> dict | None | bool:
        """The total row, None when Comtrade has no data, False when the request failed or ran out of time."""
        for attempt in (1, 2):  # one retry after a 429, if the wait fits in the budget
            with self._request_lock:
                if self._last_request is not None:
                    wait = self._last_request + self.min_interval - self._clock()
                    if wait > 0:
                        if self._clock() + wait >= deadline:
                            logger.info("comtrade out of time hs6=%s year=%s", hs6, year)
                            return False
                        self._sleep(wait)
                remaining = deadline - self._clock()
                if remaining <= 0:
                    logger.info("comtrade out of time hs6=%s year=%s", hs6, year)
                    return False
                self._last_request = self._clock()
                try:
                    return _total_row(self._get_json(self.url(hs6, year), remaining))
                except _RateLimited as exc:
                    # The server says when the next request may go: count that as the last request time.
                    self._last_request = self._clock() + exc.retry_after - self.min_interval
                    logger.info("comtrade rate limited hs6=%s year=%s retry_in=%ss", hs6, year, exc.retry_after)
                    if attempt == 2:
                        return False
                except (URLError, TimeoutError, OSError, ValueError) as exc:
                    logger.warning("comtrade request failed hs6=%s year=%s: %s", hs6, year, type(exc).__name__)
                    return False
        return False
