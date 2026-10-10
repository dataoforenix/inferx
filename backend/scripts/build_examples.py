"""Regenerate docs/examples/*.json: real responses from the app, run offline.

    python scripts/build_examples.py

The app runs with the installed data (data/categories.csv, data/demo_cache) and the test suite's
fake LLM, so no API key is needed. The fake LLM "recognises" products as listed below and writes
its explanation with the deterministic template in the requested language; everything else
(report, scores, verdicts, caps, flags, statuses, errors) is exactly what the API returns.
request_id values are replaced with a fixed placeholder so the files don't change on every run.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.comtrade import TradeSeries  # noqa: E402
from app.explanation import fallback_explanation  # noqa: E402
from app.factory import create_app  # noqa: E402
from app.llm import LLMUnavailable  # noqa: E402
from app.schemas import ExplanationLLMOutput, FeasibilityReport, NormalizationLLMOutput  # noqa: E402
from tests.conftest import FakeLLM, norm_output, test_settings  # noqa: E402

OUT = BACKEND_DIR / "docs" / "examples"
DATA = BACKEND_DIR / "data"
REQUEST_ID = "0123456789abcdef0123456789abcdef"

# file name -> response model name (used by tests/test_examples.py)
EXAMPLES: dict[str, str] = {}


def explainer(language: str):
    """Fake LLM that 'writes' the template explanation in the given language."""

    def explain(facts):
        # The model sees long text in data_notes and the lists in key_figures; put them back together.
        kf, notes = facts["key_figures"], facts.get("data_notes", {})
        report = FeasibilityReport.model_validate({
            **facts["report"],
            "machinery": kf["machinery"], "raw_materials": kf["raw_materials"],
            "source_notes": notes.get("source_notes", ""), "risk_notes": notes.get("risk_notes", ""),
            "competition_note": notes.get("competition_note", ""),
            "machine_source": notes.get("machine_source", ""), "sources": notes.get("sources", []),
        })
        return ExplanationLLMOutput(**fallback_explanation(report, language).model_dump(exclude={"language"}))
    return explain


def save(name: str, response, model: str, expected_status: int) -> None:
    assert response.status_code == expected_status, (name, response.status_code, response.text)
    body = response.json()
    _scrub(body)
    (OUT / name).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EXAMPLES[name] = model
    print(f"wrote docs/examples/{name} ({response.status_code})")


def _scrub(obj) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "request_id":
                obj[key] = REQUEST_ID
            else:
                _scrub(value)
    elif isinstance(obj, list):
        for value in obj:
            _scrub(value)


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 120, 200)).save(buf, format="PNG")
    return buf.getvalue()


def client(llm=None, comtrade=None, **settings) -> TestClient:
    settings.setdefault("categories_csv", DATA / "categories.csv")
    settings.setdefault("demo_cache_dir", DATA / "demo_cache")
    return TestClient(create_app(test_settings(openai_api_key="example-key", **settings), llm=llm,
                                 comtrade=comtrade))


# Recorded from the UN Comtrade public preview API on 2026-10-10 (Jordan imports, HS 854143, photovoltaic
# modules). The code exists only from HS 2022, so 2020 and 2021 have no data: the trend is unavailable.
SOLAR_TRADE = TradeSeries(hs6="854143", imports_usd={2020: None, 2021: None, 2022: 58675722.148,
                                                     2023: 41114161.694, 2024: 67533519.488},
                          import_weight_kg_2024=19579573.5)


class RecordedComtrade:
    def fetch(self, hs6):
        return SOLAR_TRADE if hs6 == SOLAR_TRADE.hs6 else None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()

    chair = FakeLLM(normalize=norm_output("metal_chair", 0.93, name_en="Metal office chair",
                                          name_ar="كرسي مكتب معدني",
                                          description="An office chair with a steel frame and a padded seat."),
                    explain=explainer("en"))
    live = client(chair)
    save("health.json", live.get("/api/health"), "HealthResponse", 200)
    save("categories.json", live.get("/api/categories"), "CategoriesResponse", 200)
    save("analyze_complete_en.json",
         live.post("/api/analyze", data={"text": "metal office chair", "language": "en"}), "AnalyzeResponse", 200)

    racks = client(FakeLLM(normalize=norm_output("warehouse_racks", 0.94, name_en="Warehouse racks",
                                                 name_ar="رفوف مستودعات",
                                                 description="Metal storage racks for a warehouse."),
                           explain=explainer("ar")))
    save("analyze_complete_ar.json",
         racks.post("/api/analyze", data={"text": "رفوف مستودعات", "language": "ar"},
                    files={"image": ("racks.png", png_bytes(), "image/png")}),
         "AnalyzeResponse", 200)

    uncertain = client(FakeLLM(normalize=norm_output(
        "metal_chair", 0.45, alternatives=[("plastic_tableware", 0.30)], name_en="Plastic folding chair",
        name_ar="كرسي بلاستيك قابل للطي", description="A folding chair made mostly of moulded plastic.")))
    save("analyze_needs_confirmation.json",
         uncertain.post("/api/analyze", data={"text": "plastic folding chair", "language": "en"}),
         "AnalyzeResponse", 200)

    unsupported = client(FakeLLM(normalize=norm_output(
        "unsupported", 0.97, physical=False, name_en="Accounting software", name_ar="برنامج محاسبة",
        description="A software product, not a physical good.")))
    save("analyze_unsupported.json",
         unsupported.post("/api/analyze", data={"text": "accounting software for small shops"}),
         "AnalyzeResponse", 200)

    solar = NormalizationLLMOutput(
        is_physical_product=True, product_name_en="Rooftop solar panel", product_name_ar="لوح طاقة شمسية",
        description="A photovoltaic module for rooftops.", category_id="unsupported", confidence=0.95,
        alternatives=[], hs6_guess="854143")
    preview = client(FakeLLM(normalize=solar), comtrade=RecordedComtrade())
    save("analyze_market_preview.json",
         preview.post("/api/analyze", data={"text": "rooftop solar panel", "language": "en"}), "AnalyzeResponse", 200)

    # Cost gate (tomato_paste: local 4.01 vs landed 1.44 USD/kg -> DONT, capped) and capital flag.
    save("confirm_complete.json",
         live.post("/api/analyze/confirm", json={"category_id": "tomato_paste", "language": "en",
                                                 "product": {"name_en": "Tomato paste", "name_ar": "معجون بندورة",
                                                             "description": "Concentrated tomato paste in a can."}}),
         "AnalyzeResponse", 200)
    ar_live = client(FakeLLM(explain=explainer("ar")))
    save("confirm_complete_ar.json",
         ar_live.post("/api/analyze/confirm", json={"category_id": "tomato_paste", "language": "ar"}),
         "AnalyzeResponse", 200)
    # Every optional field populated, plus the high_capital_requirement flag.
    save("confirm_complete_all_fields.json",
         live.post("/api/analyze/confirm", json={"category_id": "frozen_fries", "language": "en"}),
         "AnalyzeResponse", 200)

    save("whatif.json",
         live.post("/api/whatif", json={"category_id": "tomato_paste",
                                        "overrides": {"local_cost_per_kg_est_usd": 1.0}}),
         "WhatIfResponse", 200)
    save("whatif_shipping_info_only.json",
         live.post("/api/whatif", json={"category_id": "frozen_fries", "overrides": {"shipping_pct": 0.5}}),
         "WhatIfResponse", 200)

    save("budget_partial.json",
         live.post("/api/budget", json={"category_id": "tomato_paste", "budget_jod": 100000}), "BudgetResponse", 200)
    save("methodology.json", live.get("/api/methodology"), "MethodologyResponse", 200)

    # Common errors
    save("error_400_empty_input.json", live.post("/api/analyze", data={"language": "en"}), "ErrorResponse", 400)
    small = client(FakeLLM(), max_upload_bytes=1024)
    save("error_413_payload_too_large.json",
         small.post("/api/analyze", files={"image": ("big.png", b"\0" * (400 * 1024), "image/png")}),
         "ErrorResponse", 413)
    save("error_415_unsupported_image_type.json",
         live.post("/api/analyze", files={"image": ("a.gif", b"GIF89a....", "image/gif")}), "ErrorResponse", 415)
    save("error_422_validation_error.json",
         live.post("/api/analyze", data={"text": "chair", "language": "fr"}), "ErrorResponse", 422)
    down = client(FakeLLM(normalize=LLMUnavailable("down")))
    save("error_503_llm_unavailable.json",
         down.post("/api/analyze", data={"text": "spaceship engine"}), "ErrorResponse", 503)
    demo = client(demo_mode=True)
    save("error_404_demo_no_match.json",
         demo.post("/api/analyze", data={"text": "spaceship engine"}), "ErrorResponse", 404)

    (OUT / "index.json").write_text(json.dumps(EXAMPLES, indent=2) + "\n", encoding="utf-8")
    print("wrote docs/examples/index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
