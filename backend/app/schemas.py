"""Pydantic models shared across the API.

Milestone 1 defines the category, health and error contracts. Report / analysis
schemas are added alongside the scoring engine and pipeline.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer

Language = Literal["ar", "en"]
DataStatus = Literal["VERIFIED", "ESTIMATE", "TODO_REAL_DATA"]

IMPORT_YEARS = (2020, 2021, 2022, 2023, 2024)


class CategoryRecord(BaseModel):
    """One validated row of categories.csv. Numeric fields are None when the cell is empty."""

    model_config = ConfigDict(frozen=True)

    category_id: str
    name_en: str
    name_ar: str
    description_en: str
    keywords_en: list[str]
    keywords_ar: list[str]
    hs6: str
    imports_usd: dict[int, float | None]
    import_weight_kg_2024: float | None
    import_price_per_kg_usd: float | None
    shipping_pct: float | None
    customs_pct: float | None
    local_cost_per_kg_est_usd: float | None
    machinery_availability: float | None
    raw_material_local: float | None
    skills_availability: float | None
    local_factories: int | None
    factories_saturation: int | None
    machinery: str
    raw_materials: str
    data_status: DataStatus
    source_notes: str
    # Optional columns: not part of missing_fields / data completeness.
    risk_notes: str = ""
    competition_note: str = ""
    source_url: str = ""
    tariff_source_url: str = ""
    estimated_fields: list[str] = Field(default_factory=list)
    machine_cost_jod_min: float | None = None
    machine_cost_jod_max: float | None = None
    raw_material_price_usd_per_kg: float | None = None
    material_kg_per_kg_product: float | None = None
    conversion_cost_per_kg_usd: float | None = None
    protection_pct: float | None = None
    landed_price_per_kg_usd: float | None = None
    machine_cost_usd_min: float | None = None
    machine_cost_usd_max: float | None = None
    machine_source: str = ""
    machine_source_urls: list[str] = Field(default_factory=list)

    @property
    def missing_fields(self) -> list[str]:
        missing = [f"imports_{y}_usd" for y, v in self.imports_usd.items() if v is None]
        for name in (
            "import_weight_kg_2024",
            "import_price_per_kg_usd",
            "shipping_pct",
            "customs_pct",
            "local_cost_per_kg_est_usd",
            "machinery_availability",
            "raw_material_local",
            "skills_availability",
            "local_factories",
            "factories_saturation",
        ):
            if getattr(self, name) is None:
                missing.append(name)
        return missing


class CategorySummary(BaseModel):
    category_id: str
    name_en: str
    name_ar: str
    description_en: str
    hs6: str
    data_status: DataStatus
    is_placeholder_data: bool = Field(description="True when values are TODO_REAL_DATA placeholders.")
    missing_fields: list[str]


class CategoriesResponse(BaseModel):
    request_id: str
    categories: list[CategorySummary]


class HealthResponse(BaseModel):
    request_id: str
    status: Literal["ok", "degraded"]
    version: str
    demo_mode: bool
    llm_configured: bool
    categories_loaded: int
    data_warnings: list[str]
    demo_cache_entries: int
    demo_cache_placeholder_entries: int = Field(description="Hand-written entries, not recorded from the AI.")


# --- scoring / reports ------------------------------------------------------

Verdict = Literal["MANUFACTURE", "MAYBE", "DONT"]


class WhatIfOverrides(BaseModel):
    """Optional what-if inputs. Ranges mirror the CSV validation rules."""

    model_config = ConfigDict(extra="forbid")

    customs_pct: float | None = Field(default=None, ge=0, le=2, description="Fraction, e.g. 0.2 = 20%")
    shipping_pct: float | None = Field(default=None, ge=0, le=2, description="Fraction, e.g. 0.08 = 8%")
    local_cost_per_kg_est_usd: float | None = Field(default=None, gt=0, le=1e6)
    import_price_per_kg_usd: float | None = Field(default=None, gt=0, le=1e6)
    local_factories: int | None = Field(default=None, ge=0, le=100_000)


class MarketBreakdown(BaseModel):
    score: float | None
    volume_score: float | None
    trend_score: float | None
    cagr: float | None = Field(description="Compound annual growth 2020-2024, as a fraction")
    latest_import_usd: float | None
    latest_import_jod: float | None = Field(
        default=None, description="Derived: latest_import_usd x 0.709 (fixed JOD peg). Not a separate data source.")


class CostBreakdown(BaseModel):
    score: float | None
    import_price_per_kg_usd: float | None
    shipping_pct: float | None
    customs_pct: float | None
    landed_cost_per_kg_usd: float | None
    local_cost_per_kg_est_usd: float | None
    margin: float | None = Field(description="(landed - local) / landed, as a fraction")
    # Build-up of the local cost (from the CSV; informational, the score uses local_cost_per_kg_est_usd).
    raw_material_price_usd_per_kg: float | None = None
    material_kg_per_kg_product: float | None = None
    conversion_cost_per_kg_usd: float | None = None


class FeasibilityBreakdown(BaseModel):
    score: float | None
    machinery_availability: float | None
    raw_material_local: float | None
    skills_availability: float | None


class CompetitionBreakdown(BaseModel):
    score: float | None
    local_factories: int | None
    factories_saturation: int | None


TrendLabel = Literal["growing", "stable", "declining"]


class MachineCostRange(BaseModel):
    min: float | None = Field(description="JOD")
    max: float | None = Field(description="JOD")


CAPEX_DESCRIPTION = (
    "Equipment only: supplier listing prices ex-works, excluding shipping, customs, installation, "
    "moulds and buildings (USD)."
)


class CapexRange(BaseModel):
    min: float | None = Field(description=CAPEX_DESCRIPTION)
    max: float | None = Field(description=CAPEX_DESCRIPTION)


BREAK_EVEN_DESCRIPTION = (
    "Indicative: equipment only, excludes buildings and working capital, assumes selling at import-parity price."
)


class BreakEven(BaseModel):
    """How much must be sold at import-parity price before the equipment pays for itself."""

    capex_mid_usd: float = Field(description="(capex_usd_range.min + max) / 2, USD")
    unit_saving_usd_per_kg: float = Field(description="landed import cost - local cost, USD/kg")
    break_even_tons: float = Field(description="capex_mid_usd / unit_saving_usd_per_kg, in tonnes")
    share_of_2024_imports: float = Field(description="break-even weight / import_weight_kg_2024, as a fraction")


class LocalizedSteps(BaseModel):
    en: list[str]
    ar: list[str]


class Advisor(BaseModel):
    """An official Jordanian body (URL verified). No phone numbers or personal names."""

    name_en: str
    name_ar: str
    offer_en: str = Field(description="What the body offers, one line")
    offer_ar: str
    url: str


class SupplierLink(BaseModel):
    marketplace: str
    url: str = Field(description="A marketplace search for the item name, not a supplier recommendation")


class SupplierItemLinks(BaseModel):
    item: str = Field(description="An entry of report.machinery or report.raw_materials")
    kind: Literal["machinery", "raw_material"]
    links: list[SupplierLink]


class SupplierLinks(BaseModel):
    caption_en: str = Field(description="Mandatory caption: show it with the links")
    caption_ar: str
    items: list[SupplierItemLinks]
    local_directory: Advisor | None = Field(default=None, description="Directory of Jordanian manufacturers")


class FeasibilityReport(BaseModel):
    """Everything here is computed by Python (app/scoring.py) or copied from the CSV. LLMs only explain it."""

    category_id: str
    name_en: str
    name_ar: str
    hs6: str
    data_status: DataStatus
    is_placeholder_data: bool
    score: float | None = Field(description="0-10, one decimal. None only when no component is computable.")
    verdict: Verdict
    verdict_forced_maybe: bool = Field(description="True when data completeness was too low to trust the score.")
    verdict_capped_by: Literal["cost_gate"] | None = Field(
        default=None,
        description="cost_gate: producing locally costs more than importing (margin < 0), so the score/verdict "
                    "was capped (at most MAYBE / 5.9; DONT / 3.9 when margin < -0.25). Null when nothing was capped.",
    )
    data_completeness: float = Field(ge=0, le=1)
    flags: list[Literal["high_capital_requirement", "market_preview_only"]] = Field(
        default_factory=list,
        description="Information flags that never change the score. high_capital_requirement: "
                    "machine_cost_usd_max >= 250,000 USD (equipment only). market_preview_only: a preliminary "
                    "scan built from UN Comtrade imports alone for a product outside the categories.",
    )
    missing_fields: list[str]
    weights: dict[str, float]
    market: MarketBreakdown
    cost: CostBreakdown
    feasibility: FeasibilityBreakdown
    competition: CompetitionBreakdown
    imports_usd: dict[int, float | None]
    overrides_applied: dict[str, float]
    notes: list[str]
    # Category context from the CSV, so the frontend can render every card without another lookup.
    trend_label: TrendLabel | None = Field(description="growing if CAGR > 3%, declining if < -3%, else stable")
    machinery: list[str]
    raw_materials: list[str]
    risk_notes: str
    competition_note: str
    source_notes: str
    sources: list[str] = Field(description="Non-empty source_url, tariff_source_url and machine_source_urls")
    estimated_fields: list[str] = Field(description="CSV columns whose values are estimates")
    machine_cost_range_jod: MachineCostRange | None
    capex_usd_range: CapexRange | None = Field(default=None, description=CAPEX_DESCRIPTION)
    machine_source: str = Field(default="", description="Where the equipment prices come from")
    import_weight_kg_2024: float | None = Field(default=None, description="Weight of 2024 imports, kg")
    break_even: BreakEven | None = Field(
        default=None,
        description=f"{BREAK_EVEN_DESCRIPTION} Null unless capex_usd_range (min and max), import_weight_kg_2024 "
                    f"and a cost advantage (landed > local) all exist.",
    )
    next_steps: LocalizedSteps | None = Field(default=None, description="Static next steps for this verdict (en/ar)")
    advisors: list[Advisor] = Field(
        default_factory=list,
        description="Official Jordanian bodies offering feasibility, consulting, registration or funding support")
    suppliers: SupplierLinks | None = Field(
        default=None, description="Marketplace search links per machinery / raw-material item, with a mandatory caption")


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(min_length=1, max_length=64)
    overrides: WhatIfOverrides = Field(default_factory=WhatIfOverrides)


class WhatIfResponse(BaseModel):
    request_id: str
    baseline: FeasibilityReport
    scenario: FeasibilityReport
    score_delta: float | None = Field(description="scenario.score - baseline.score, one decimal")


class BudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(min_length=1, max_length=64)
    budget_jod: float = Field(ge=0, le=1e10, description="Available budget for equipment, JOD")


class JodRange(BaseModel):
    min: float
    max: float


class BudgetResponse(BaseModel):
    request_id: str
    category_id: str
    budget_jod: float
    status: Literal["covered", "partial", "short"] = Field(
        description="covered: budget >= top of the equipment range; partial: >= bottom; short: below the bottom")
    capex_jod_range: JodRange = Field(description="capex_usd_range x 0.709 (fixed JOD peg), equipment only")
    gap_jod: float = Field(description="Still missing to reach the top of the range; 0 when covered")
    caption_en: str = Field(description="Mandatory caption: equipment only, partial investment")
    caption_ar: str


class MethodologySection(BaseModel):
    title: str
    body: str


class MethodologyResponse(BaseModel):
    request_id: str
    weights: dict[str, float]
    thresholds: dict[str, float]
    cost_gate: dict[str, float]
    min_completeness: float
    growth_years: dict[str, int | str]
    sections: dict[Language, list[MethodologySection]]


# --- product normalisation / explanation --------------------------------------

UNSUPPORTED = "unsupported"
AnalyzeStatus = Literal["complete", "needs_confirmation", "unsupported", "market_preview"]


class LLMAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str
    confidence: float = Field(ge=0, le=1)


class NormalizationLLMOutput(BaseModel):
    """Exactly what the normalisation LLM must return. Validated after every call."""

    model_config = ConfigDict(extra="forbid")

    is_physical_product: bool
    product_name_en: str = Field(max_length=200)
    product_name_ar: str = Field(max_length=200)
    description: str = Field(max_length=600)
    category_id: str
    confidence: float = Field(ge=0, le=1)
    alternatives: list[LLMAlternative] = Field(max_length=4)
    # Only for physical products outside every category; used for the market preview. Optional so recorded
    # demo-cache entries and older fakes stay valid. Anything that isn't exactly 6 digits becomes None.
    hs6_guess: str | None = None

    @field_validator("hs6_guess", mode="before")
    @classmethod
    def _six_digits_or_none(cls, value):
        if isinstance(value, str):
            value = value.strip().replace(".", "")
            return value if re.fullmatch(r"\d{6}", value) else None
        return None


class ExplanationLLMOutput(BaseModel):
    """Exactly what the explanation LLM must return. Note: no score or verdict fields."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1200)
    reasons_for: list[str] = Field(min_length=3, max_length=3)
    concerns: list[str] = Field(min_length=3, max_length=3)
    next_steps: list[str] = Field(min_length=3, max_length=3)
    caveats: list[str] = Field(max_length=6)


class CategoryCandidate(BaseModel):
    category_id: str
    name_en: str
    name_ar: str
    confidence: float | None = None


class ProductInfo(BaseModel):
    """Normalised product. In /confirm requests it comes from the client, so it is length-limited."""

    model_config = ConfigDict(extra="forbid")

    name_en: str = Field(default="", max_length=200)
    name_ar: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=600)


class NormalizedProduct(ProductInfo):
    category_id: str | None
    confidence: float | None
    alternatives: list[CategoryCandidate]
    hs6_guess: str | None = Field(
        default=None, description="AI-guessed 6-digit HS code (market_preview only); show it so the user can check it.",
    )


class Explanation(BaseModel):
    language: Language
    summary: str
    reasons_for: list[str]
    concerns: list[str]
    next_steps: list[str]
    caveats: list[str]


class Timings(BaseModel):
    """Server-side milliseconds per step; null when the step did not run."""

    normalize: float | None = Field(default=None, description="Product recognition (LLM or demo cache)")
    score: float | None = Field(default=None, description="Deterministic scoring")
    explain: float | None = Field(default=None, description="Explanation incl. grounding retry")
    market_data: float | None = Field(default=None, description="UN Comtrade lookup (market preview only)")
    total: float = Field(default=0, description="Whole request handler, incl. image processing")


class AnalyzeResponse(BaseModel):
    request_id: str
    status: AnalyzeStatus
    language: Language
    source: Literal["live", "demo_cache"] = "live"
    product: NormalizedProduct | None
    needs_confirmation: bool
    candidates: list[CategoryCandidate] = Field(
        description="Categories the user can confirm via /api/analyze/confirm when needs_confirmation is true."
    )
    report: FeasibilityReport | None
    explanation: Explanation | None
    explanation_source: Literal["llm", "fallback", "template"] | None = Field(
        description="llm: AI-written and grounding-checked; fallback: template used because the AI text was "
                    "unavailable or ungrounded; template: deterministic text by design (market_preview)."
    )
    warnings: list[str]
    timings_ms: Timings = Field(default_factory=Timings)
    cache: Literal["hit", "miss"] | None = Field(
        default=None,
        description="Only present when the server's response cache is on (DB_ENABLED): hit = a stored response for "
                    "the same text / image / language younger than CACHE_TTL_HOURS was returned without calling the AI.",
    )

    @model_serializer(mode="wrap")
    def _omit_cache_when_off(self, handler):
        # With the cache off the field is absent, so responses stay byte-for-byte what they were before it existed.
        data = handler(self)
        if self.cache is None:
            data.pop("cache", None)
        return data


class TopSearch(BaseModel):
    category_id: str | None = Field(description="Set for the supported categories")
    hs6_guess: str | None = Field(description="Set for market-preview products outside the categories")
    name_en: str
    name_ar: str
    count: int


class TopSearchesResponse(BaseModel):
    request_id: str
    searches: list[TopSearch] = Field(description="Most analysed products first. No personal data, no IP addresses.")


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: str = Field(min_length=1, max_length=64)
    language: Language = "en"
    product: ProductInfo | None = None


# --- errors -----------------------------------------------------------------


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
