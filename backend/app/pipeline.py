"""Analysis pipeline: normalise product -> decide on confirmation -> score -> explain.

The LLM never produces numbers that reach the user unchecked: scores come from
scoring.py, and the explanation passes the grounding guard or is replaced by the
deterministic template.
"""

from __future__ import annotations

import logging
import time

from app.comtrade import ComtradeClient
from app.config import Settings
from app.data_store import DataStore
from app.demo import DemoCache, DemoNoMatch
from app.errors import AppError
from app.explanation import fallback_explanation, grounding_issues, llm_facts
from app.image_utils import PreparedImage
from app.llm import LLMClient, LLMError, LLMInvalidOutput, LLMRefused, LLMUnavailable
from app.market_preview import preview_explanation, preview_report
from app.schemas import (
    UNSUPPORTED,
    AnalyzeResponse,
    CategoryCandidate,
    Explanation,
    FeasibilityReport,
    Language,
    NormalizationLLMOutput,
    NormalizedProduct,
    ProductInfo,
    Timings,
)
from app.scoring import compute_report

logger = logging.getLogger("sannaha.pipeline")


def llm_error_to_app_error(exc: LLMError) -> AppError:
    if isinstance(exc, LLMRefused):
        return AppError(422, "input_refused", "The AI model declined to analyse this input.")
    if isinstance(exc, LLMUnavailable):
        return AppError(503, "llm_unavailable", "The AI service is temporarily unavailable. Please try again.")
    if isinstance(exc, LLMInvalidOutput):
        return AppError(502, "llm_invalid_output", "The AI service returned an invalid answer. Please try again.")
    return AppError(502, "llm_error", "The AI service could not process the request.")


DEMO_WARNING = "Demo mode: this is a prepared example; no live AI call was made."
LIVE_FALLBACK_WARNING = "The AI service is unavailable, so a prepared demo example is shown instead."
UNSUPPORTED_WARNING = "This product does not match any of the supported categories."
PREVIEW_UNAVAILABLE_WARNING = ("A market preview from UN Comtrade (HS {hs6}) could not be loaded, "
                               "so only the unsupported result is shown.")
PREVIEW_WARNING = ("Market preview only: this product is outside the supported categories. The figures are "
                   "UN Comtrade imports for HS {hs6}, a code guessed by the AI; please check it.")


def _ms_since(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def grounding_feedback(issues: list[str]) -> str:
    return (
        f"Your previous answer used numbers that are not in the report: [{', '.join(issues)}]. "
        "Rewrite using only numbers from <key_figures>, <report> or <data_notes>."
    )


class Pipeline:
    def __init__(self, settings: Settings, store: DataStore, llm: LLMClient | None, demo: DemoCache | None = None,
                 comtrade: ComtradeClient | None = None):
        self.settings = settings
        self.store = store
        self.llm = llm
        self.demo = demo or DemoCache([])
        self.comtrade = comtrade

    # --- entry points -------------------------------------------------------------

    def analyze(
        self, request_id: str, image: PreparedImage | None, text: str | None, language: Language
    ) -> AnalyzeResponse:
        llm, source, warnings = self._pick_llm()
        if llm is None:
            raise AppError(
                503, "llm_not_configured",
                "Product recognition needs OPENAI_API_KEY (or DEMO_MODE=true for prepared examples).",
            )
        started = time.perf_counter()
        try:
            norm = llm.normalize(image, text, self.store.list())
        except DemoNoMatch as exc:
            examples = "; ".join(self.demo.example_texts()) or "none"
            raise AppError(404, "demo_no_match",
                           f"Demo mode only knows the prepared examples. Try one of: {examples}") from exc
        except LLMUnavailable as exc:
            # Live AI is down: serve a matching prepared example if there is one, never a guess.
            entry = self.demo.match(image, text)
            logger.warning("normalize unavailable request_id=%s demo_match=%s: %s", request_id, bool(entry), exc)
            if entry is None:
                raise llm_error_to_app_error(exc) from exc
            norm, llm, source, warnings = entry.normalization, self.demo, "demo_cache", [LIVE_FALLBACK_WARNING]
        except LLMError as exc:
            logger.warning("normalize failed request_id=%s: %s", request_id, exc)
            raise llm_error_to_app_error(exc) from exc
        timings = {"normalize": _ms_since(started)}

        alternatives = self._candidates(
            [(a.category_id, a.confidence) for a in norm.alternatives], exclude=norm.category_id
        )

        if norm.category_id == UNSUPPORTED or not norm.is_physical_product:
            preview = self._market_preview(request_id, norm, alternatives, language, source, warnings, timings)
            if preview is not None:
                return preview
            if self._preview_allowed(norm, source):
                warnings = [*warnings, PREVIEW_UNAVAILABLE_WARNING.format(hs6=norm.hs6_guess)]
            return self._response(
                request_id, "unsupported", language, source=source,
                product=self._product(norm, None, alternatives),
                candidates=alternatives, timings=timings,
                warnings=[*warnings, UNSUPPORTED_WARNING],
            )

        product = self._product(norm, norm.category_id, alternatives)
        # Confirmation is a Python decision, never the model's.
        if norm.confidence < self.settings.confirm_confidence_threshold:
            primary = self._candidates([(norm.category_id, norm.confidence)])
            return self._response(
                request_id, "needs_confirmation", language, source=source, product=product,
                candidates=primary + alternatives, needs_confirmation=True, timings=timings,
                warnings=[*warnings, "The product category is uncertain. Please confirm it."],
            )

        return self._complete(request_id, self.store.get(norm.category_id), product, language, llm, source, warnings,
                              timings)

    def confirm(
        self, request_id: str, category_id: str, product: ProductInfo | None, language: Language
    ) -> AnalyzeResponse:
        record = self.store.get(category_id)
        if record is None:
            raise AppError(404, "unknown_category", f"Unknown category_id {category_id!r}.")
        product = product or ProductInfo()
        normalized = NormalizedProduct(
            name_en=product.name_en or record.name_en,
            name_ar=product.name_ar or record.name_ar,
            description=product.description or record.description_en,
            category_id=category_id,
            confidence=None,
            alternatives=[],
        )
        llm, source, warnings = self._pick_llm()
        return self._complete(request_id, record, normalized, language, llm, source, warnings, {})

    # --- internals ------------------------------------------------------------------

    def _pick_llm(self) -> tuple[LLMClient | None, str, list[str]]:
        if self.settings.demo_mode:
            return self.demo, "demo_cache", [DEMO_WARNING]
        return self.llm, "live", []

    def _preview_allowed(self, norm: NormalizationLLMOutput, source: str) -> bool:
        """Live mode only (never DEMO_MODE or a demo fallback), physical products with a valid HS6 guess."""
        return (self.comtrade is not None and not self.settings.demo_mode and source == "live"
                and norm.is_physical_product and norm.category_id == UNSUPPORTED and norm.hs6_guess is not None)

    def _market_preview(self, request_id, norm: NormalizationLLMOutput, alternatives, language: Language,
                        source: str, warnings: list[str], timings: dict) -> AnalyzeResponse | None:
        if not self._preview_allowed(norm, source):
            return None
        started = time.perf_counter()
        trade = self.comtrade.fetch(norm.hs6_guess)
        timings["market_data"] = _ms_since(started)
        if trade is None:
            logger.info("market preview unavailable request_id=%s hs6=%s", request_id, norm.hs6_guess)
            return None
        started = time.perf_counter()
        report = preview_report(trade, norm.product_name_en, norm.product_name_ar)
        timings["score"] = _ms_since(started)
        started = time.perf_counter()
        explanation = preview_explanation(report, language)  # fixed template: no LLM call
        timings["explain"] = _ms_since(started)
        product = self._product(norm, None, alternatives).model_copy(update={"hs6_guess": norm.hs6_guess})
        return self._response(
            request_id, "market_preview", language, source=source, product=product, candidates=alternatives,
            report=report, explanation=explanation, explanation_source="template", timings=timings,
            warnings=[*warnings, PREVIEW_WARNING.format(hs6=norm.hs6_guess)],
        )

    def _complete(self, request_id, record, product: NormalizedProduct, language: Language,
                  llm: LLMClient | None, source: str, warnings: list[str], timings: dict) -> AnalyzeResponse:
        started = time.perf_counter()
        report = compute_report(record)
        timings["score"] = _ms_since(started)
        started = time.perf_counter()
        explanation, explanation_source, explain_warnings = self._explain(request_id, llm, product, report, language)
        timings["explain"] = _ms_since(started)
        return self._response(
            request_id, "complete", language, source=source, product=product, report=report,
            explanation=explanation, explanation_source=explanation_source, warnings=[*warnings, *explain_warnings],
            timings=timings,
        )

    def _explain(
        self, request_id: str, llm: LLMClient | None, product: NormalizedProduct, report: FeasibilityReport,
        language: Language,
    ) -> tuple[Explanation, str, list[str]]:
        if llm is None:
            return fallback_explanation(report, language), "fallback", [
                "AI explanation unavailable (no API key); a template explanation was used."
            ]
        product_data = product.model_dump(include={"name_en", "name_ar", "description"})
        facts = llm_facts(report)
        feedback = None
        for attempt in (1, 2):  # one retry with feedback when the grounding guard fails
            try:
                out = llm.explain(product_data, facts, language, feedback=feedback)
            except LLMError as exc:
                logger.warning("explain failed request_id=%s attempt=%d: %s", request_id, attempt, exc)
                return fallback_explanation(report, language), "fallback", [
                    "AI explanation unavailable; a template explanation based on the same report was used."
                ]
            issues = grounding_issues(out, report)
            if not issues:
                logger.info("explain grounded request_id=%s attempt=%d", request_id, attempt)
                return Explanation(language=language, **out.model_dump()), "llm", []
            logger.warning("grounding failed request_id=%s attempt=%d ungrounded=%s", request_id, attempt, issues)
            feedback = grounding_feedback(issues)
        return fallback_explanation(report, language), "fallback", [
            "AI explanation mentioned numbers not found in the report, even after a retry; "
            "a template explanation was used."
        ]

    def _candidates(self, pairs, exclude: str | None = None) -> list[CategoryCandidate]:
        seen, out = set(), []
        for cid, conf in sorted(pairs, key=lambda p: -p[1]):
            record = self.store.get(cid)
            if record is None or cid == exclude or cid in seen:
                continue
            seen.add(cid)
            out.append(CategoryCandidate(category_id=cid, name_en=record.name_en, name_ar=record.name_ar,
                                         confidence=round(conf, 2)))
        return out

    @staticmethod
    def _product(norm: NormalizationLLMOutput, category_id, alternatives) -> NormalizedProduct:
        return NormalizedProduct(
            name_en=norm.product_name_en, name_ar=norm.product_name_ar, description=norm.description,
            category_id=category_id, confidence=round(norm.confidence, 2), alternatives=alternatives,
        )

    @staticmethod
    def _response(request_id, status, language, *, source="live", product=None, candidates=None,
                  needs_confirmation=False, report=None, explanation=None, explanation_source=None,
                  warnings=None, timings=None) -> AnalyzeResponse:
        return AnalyzeResponse(
            request_id=request_id, status=status, language=language, source=source, product=product,
            needs_confirmation=needs_confirmation, candidates=candidates or [], report=report,
            explanation=explanation, explanation_source=explanation_source, warnings=warnings or [],
            # total is overwritten by the router with the whole handler time (incl. image processing).
            timings_ms=Timings(**(timings or {}), total=round(sum((timings or {}).values()), 1)),
        )
