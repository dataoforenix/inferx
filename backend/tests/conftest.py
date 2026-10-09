from __future__ import annotations

import dataclasses
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.factory import create_app
from app.schemas import ExplanationLLMOutput, LLMAlternative, NormalizationLLMOutput

# Offline tests never read data/: they use these frozen copies of the placeholder data.
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEST_CSV = FIXTURES / "categories_test.csv"
TEST_DEMO_CACHE = FIXTURES / "demo_cache"


def test_settings(**overrides):
    """Settings with no API key and fixture data, so tests never reach the real API or data/."""
    base = dataclasses.replace(
        load_settings(), openai_api_key=None, demo_mode=False,
        categories_csv=TEST_CSV, demo_cache_dir=TEST_DEMO_CACHE,
        rate_limit_per_minute=0,  # disabled in tests unless a test enables it
        market_preview=False,  # never reach UN Comtrade; market-preview tests pass a fake client
    )
    return dataclasses.replace(base, **overrides)


test_settings.__test__ = False  # not a test, despite the name


@pytest.fixture
def make_settings():
    def _make(**overrides):
        return test_settings(**overrides)

    return _make


@pytest.fixture
def client(make_settings):
    return TestClient(create_app(make_settings()))


# --- fake LLM ---------------------------------------------------------------------

def norm_output(category_id="plastic_kitchenware", confidence=0.92, alternatives=(), physical=True, **kw):
    return NormalizationLLMOutput(
        is_physical_product=physical,
        product_name_en=kw.get("name_en", "Plastic lunch box"),
        product_name_ar=kw.get("name_ar", "علبة طعام بلاستيكية"),
        description=kw.get("description", "A reusable plastic food container."),
        category_id=category_id,
        confidence=confidence,
        alternatives=[LLMAlternative(category_id=c, confidence=p) for c, p in alternatives],
    )


def grounded_explanation(facts) -> ExplanationLLMOutput:
    k = facts["key_figures"]
    return ExplanationLLMOutput(
        summary=f"This product scored {k['score_out_of_10']} out of 10.",
        reasons_for=[
            f"Imports reached about {k['latest_imports_usd_millions']} million USD in {k['latest_year']}.",
            f"Landed import cost is about {k['landed_cost_per_kg_usd']} USD/kg.",
            "Local skills are available.",
        ],
        concerns=["Raw materials are imported.", "Competition exists.", "Costs are estimates."],
        next_steps=["Get supplier quotes.", "Talk to retailers.", "Check licences."],
        caveats=["The figures are illustrative placeholders."],
    )


class FakeLLM:
    """Stands in for OpenAILLM. Results may be values, exceptions, or callables of the inputs."""

    def __init__(self, normalize=None, explain=grounded_explanation):
        self.normalize_result = normalize if normalize is not None else norm_output()
        self.explain_result = explain
        self.calls: list[tuple] = []

    def normalize(self, image, text, categories):
        self.calls.append(("normalize", image, text, [c.category_id for c in categories]))
        return self._resolve(self.normalize_result, image, text)

    def explain(self, product, facts, language, feedback=None):
        self.calls.append(("explain", product, facts, language, feedback))
        result = self.explain_result
        if isinstance(result, list):  # one result per call, in order
            result = result.pop(0)
        return self._resolve(result, facts)

    @staticmethod
    def _resolve(result, *args):
        if isinstance(result, Exception):
            raise result
        return result(*args) if callable(result) else result

    def ops(self):
        return [c[0] for c in self.calls]


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def llm_client(make_settings, fake_llm):
    return TestClient(create_app(make_settings(), llm=fake_llm))


@pytest.fixture
def csv_frame() -> pd.DataFrame:
    return pd.read_csv(TEST_CSV, dtype=str, keep_default_na=False, encoding="utf-8")


@pytest.fixture
def write_csv(tmp_path):
    def _write(df: pd.DataFrame, name: str = "categories.csv") -> Path:
        path = tmp_path / name
        df.to_csv(path, index=False, encoding="utf-8")
        return path

    return _write
