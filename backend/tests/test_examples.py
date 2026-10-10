"""docs/examples/*.json and docs/openapi.json stay valid against the response models.

Regenerate with: python scripts/build_examples.py && python scripts/export_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import schemas
from scripts.export_openapi import build_openapi

DOCS = Path(__file__).resolve().parent.parent / "docs"
EXAMPLES = DOCS / "examples"
INDEX = json.loads((EXAMPLES / "index.json").read_text(encoding="utf-8"))

REQUIRED = {
    "analyze_complete_en.json", "analyze_complete_ar.json", "analyze_needs_confirmation.json",
    "analyze_unsupported.json", "confirm_complete.json", "whatif.json", "categories.json", "health.json",
    "error_400_empty_input.json", "error_413_payload_too_large.json", "error_415_unsupported_image_type.json",
    "error_422_validation_error.json", "error_503_llm_unavailable.json", "error_404_demo_no_match.json",
    "budget_partial.json", "methodology.json",
}


def test_all_required_examples_exist_and_are_indexed():
    files = {p.name for p in EXAMPLES.glob("*.json")} - {"index.json"}
    assert REQUIRED <= files
    assert files == set(INDEX)


@pytest.mark.parametrize(("name", "model"), sorted(INDEX.items()))
def test_example_validates_against_its_model(name, model):
    body = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    getattr(schemas, model).model_validate(body)


@pytest.mark.parametrize(
    ("name", "status"),
    [("analyze_complete_en.json", "complete"), ("analyze_complete_ar.json", "complete"),
     ("analyze_needs_confirmation.json", "needs_confirmation"), ("analyze_unsupported.json", "unsupported"),
     ("confirm_complete.json", "complete")],
)
def test_analyze_examples_show_each_status(name, status):
    assert json.loads((EXAMPLES / name).read_text(encoding="utf-8"))["status"] == status


def test_error_examples_have_expected_codes():
    codes = {name: json.loads((EXAMPLES / name).read_text(encoding="utf-8"))["error"]["code"]
             for name in INDEX if name.startswith("error_")}
    assert codes["error_400_empty_input.json"] == "empty_input"
    assert codes["error_503_llm_unavailable.json"] == "llm_unavailable"
    assert codes["error_404_demo_no_match.json"] == "demo_no_match"


def test_openapi_file_matches_the_app():
    on_disk = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    assert on_disk == build_openapi(), "docs/openapi.json is stale: run python scripts/export_openapi.py"
    assert set(on_disk["paths"]) == {"/api/health", "/api/categories", "/api/whatif", "/api/analyze",
                                     "/api/analyze/confirm", "/api/budget", "/api/methodology"}
