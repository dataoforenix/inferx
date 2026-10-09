"""Demo cache: prepared LLM outputs served without calling the API.

Only the *LLM* parts are cached (product normalisation and, optionally, explanations).
Scores are always recomputed live from categories.csv, and cached explanations still go
through the grounding guard, so the demo can never show numbers the report doesn't hold.

Entries marked generated_by="PLACEHOLDER_HANDWRITTEN" were written by hand and carry no
explanation (the deterministic template is used instead). Run scripts/record_demo_cache.py
with an API key to replace them with real pipeline outputs (generated_by="pipeline").
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.image_utils import PreparedImage
from app.llm import LLMError, LLMUnavailable
from app.schemas import UNSUPPORTED, CategoryRecord, ExplanationLLMOutput, Language, NormalizationLLMOutput

logger = logging.getLogger("sannaha.demo")

PLACEHOLDER = "PLACEHOLDER_HANDWRITTEN"
DEMO_INPUTS_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_inputs.json"


class DemoPlaceholder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_en: str
    name_ar: str
    description: str
    confidence: float = Field(ge=0, le=1)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    # Default: physical unless the expected category is "unsupported". Set true for a physical
    # product that is simply outside the catalogue (e.g. a solar panel).
    is_physical_product: bool | None = None


class DemoInput(BaseModel):
    """One prepared demo input (data/demo_inputs.json). Edit that file when the categories change."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    text: str = Field(min_length=1)
    match_keywords: list[str] = Field(min_length=1)
    expected_category_id: str
    placeholder: DemoPlaceholder

    @property
    def accepted_category_ids(self) -> set[str]:
        """The expected category, plus listed alternatives for deliberately ambiguous inputs."""
        return {self.expected_category_id, *(a["category_id"] for a in self.placeholder.alternatives)}


def load_demo_inputs(path: Path = DEMO_INPUTS_PATH) -> list[DemoInput]:
    return [DemoInput.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def demo_input_mismatches(inputs: list[DemoInput], category_ids: list[str]) -> list[str]:
    """Inputs whose categories (expected or alternatives) are not in categories.csv."""
    valid = {*category_ids, UNSUPPORTED}
    problems = []
    for item in inputs:
        unknown = sorted(c for c in item.accepted_category_ids if c not in valid)
        if unknown:
            problems.append(f"{item.id}: unknown category {', '.join(unknown)}")
    return problems


class DemoNoMatch(LLMError):
    code = "demo_no_match"


class DemoEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    generated_by: Literal["pipeline", "PLACEHOLDER_HANDWRITTEN"]
    generated_at: str | None = None
    model: str | None = None
    example_input: dict[str, Any] = Field(description="The request that produced (or illustrates) this entry")
    match_keywords: list[str] = Field(min_length=1)
    image_sha256: str | None = None
    normalization: NormalizationLLMOutput
    explanations: dict[Language, ExplanationLLMOutput | None] = Field(default_factory=dict)

    @property
    def is_placeholder(self) -> bool:
        return self.generated_by == PLACEHOLDER


def keyword_in(keyword: str, text: str) -> bool:
    """Latin keywords match whole words ("app" must not match "wrapping"); Arabic keywords match
    as substrings because Arabic attaches prefixes such as "ال" directly to the word."""
    if keyword.isascii():
        return re.search(rf"(?<![a-z0-9]){re.escape(keyword.casefold())}(?![a-z0-9])", text.casefold()) is not None
    return keyword.casefold() in text.casefold()


def image_fingerprint(image: PreparedImage) -> str:
    return hashlib.sha256(base64.b64decode(image.base64_data)).hexdigest()


class DemoCache:
    """Implements the LLMClient protocol from cached entries."""

    def __init__(self, entries: list[DemoEntry], warnings: list[str] | None = None):
        self.entries = entries
        self.warnings = warnings or []

    @classmethod
    def load(cls, directory: Path, category_ids: list[str]) -> "DemoCache":
        entries, warnings = [], []
        for path in sorted(directory.glob("*.json")) if directory.exists() else []:
            try:
                entry = DemoEntry.model_validate(json.loads(path.read_text(encoding="utf-8")))
            except (ValidationError, json.JSONDecodeError, OSError) as exc:
                warnings.append(f"demo cache {path.name} ignored: {type(exc).__name__}")
                continue
            norm = entry.normalization
            if norm.category_id not in (*category_ids, UNSUPPORTED):
                warnings.append(f"demo cache {path.name} ignored: unknown category {norm.category_id!r}")
                continue
            entries.append(entry)
        placeholders = sum(e.is_placeholder for e in entries)
        if placeholders:
            warnings.append(f"demo cache: {placeholders} of {len(entries)} entries are hand-written placeholders "
                            f"(run scripts/record_demo_cache.py to record real outputs)")
        return cls(entries, warnings)

    @property
    def placeholder_count(self) -> int:
        return sum(e.is_placeholder for e in self.entries)

    def example_texts(self) -> list[str]:
        return [e.example_input.get("text", "") for e in self.entries if e.example_input.get("text")]

    def match(self, image: PreparedImage | None, text: str | None) -> DemoEntry | None:
        if image is not None:
            fingerprint = image_fingerprint(image)
            for entry in self.entries:
                if entry.image_sha256 == fingerprint:
                    return entry
        if text:
            # Longest keyword wins, so "paper cup" beats "paper".
            hits = [(len(k), e) for e in self.entries for k in e.match_keywords if keyword_in(k, text)]
            if hits:
                return max(hits, key=lambda h: h[0])[1]
        return None

    # LLMClient protocol

    def normalize(self, image, text, categories: list[CategoryRecord]) -> NormalizationLLMOutput:
        entry = self.match(image, text)
        if entry is None:
            raise DemoNoMatch("no prepared demo example matches this input")
        return entry.normalization

    def explain(
        self, product: dict[str, Any], facts: dict[str, Any], language: Language, feedback: str | None = None
    ) -> ExplanationLLMOutput:
        # feedback is ignored: a recorded answer can't be rewritten, so a failed retry falls back to the template.
        category = facts["report"]["category_id"]
        for entry in self.entries:
            if entry.normalization.category_id == category and entry.explanations.get(language):
                return entry.explanations[language]
        # No recorded explanation: the pipeline uses the deterministic template and says so.
        raise LLMUnavailable("no recorded explanation in the demo cache")
