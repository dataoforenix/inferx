"""/api/analyze and /api/analyze/confirm with a mocked LLM (no API key needed)."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from starlette.formparsers import MultiPartParser

from app.data_store import load_categories
from app.explanation import fallback_explanation
from app.image_utils import PreparedImage
from app.llm import LLMInvalidOutput, LLMRefused, LLMUnavailable
from app.factory import create_app
from app.schemas import AnalyzeResponse, ErrorResponse, ExplanationLLMOutput
from app.scoring import compute_report
from tests.conftest import TEST_CSV, FakeLLM, grounded_explanation, norm_output

STORE = load_categories(TEST_CSV)


def client_with(make_settings, llm, **settings):
    return TestClient(create_app(make_settings(**settings), llm=llm))


def png_bytes(size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (0, 128, 255)).save(buf, format="PNG")
    return buf.getvalue()


def ok(r) -> AnalyzeResponse:
    assert r.status_code == 200, r.text
    body = AnalyzeResponse.model_validate(r.json())
    assert body.request_id == r.headers["X-Request-ID"]
    return body


def err(r, status, code):
    assert r.status_code == status, r.text
    assert ErrorResponse.model_validate(r.json()).error.code == code


# --- happy path ---------------------------------------------------------------------

def test_text_analysis_complete(llm_client, fake_llm):
    body = ok(llm_client.post("/api/analyze", data={"text": "plastic lunch box", "language": "en"}))
    assert body.status == "complete" and not body.needs_confirmation
    assert body.report == compute_report(STORE.get("plastic_kitchenware"))  # Python's numbers, untouched
    assert body.explanation_source == "llm" and body.explanation.language == "en"
    assert body.product.category_id == "plastic_kitchenware" and body.product.name_ar
    assert fake_llm.ops() == ["normalize", "explain"]
    _, image, text, ids = fake_llm.calls[0]
    assert image is None and text == "plastic lunch box" and ids == STORE.ids


def test_explain_receives_python_report(llm_client, fake_llm):
    body = ok(llm_client.post("/api/analyze", data={"text": "cup", "language": "ar"}))
    _, product, facts, language, feedback = fake_llm.calls[1]
    assert feedback is None
    assert language == "ar" and body.language == "ar"
    assert facts["key_figures"]["score_out_of_10"] == body.report.score
    assert set(product) == {"name_en", "name_ar", "description"}


def test_image_upload_is_sanitised_before_llm(llm_client, fake_llm):
    files = {"image": ("photo.png", png_bytes(), "image/png")}
    body = ok(llm_client.post("/api/analyze", files=files, data={"language": "en"}))
    assert body.status == "complete"
    image = fake_llm.calls[0][1]
    assert isinstance(image, PreparedImage) and image.media_type == "image/jpeg"
    assert fake_llm.calls[0][2] is None


def test_image_and_text_together(llm_client, fake_llm):
    files = {"image": ("photo.png", png_bytes(), "image/png")}
    ok(llm_client.post("/api/analyze", files=files, data={"text": "  lunch box  "}))
    assert fake_llm.calls[0][1] is not None and fake_llm.calls[0][2] == "lunch box"


# --- confirmation / unsupported -------------------------------------------------------

def test_low_confidence_needs_confirmation(make_settings):
    llm = FakeLLM(normalize=norm_output("toilet_tissue", 0.55, alternatives=[("plastic_kitchenware", 0.3),
                                                                              ("toilet_tissue", 0.2)]))
    body = ok(client_with(make_settings, llm).post("/api/analyze", data={"text": "paper thing"}))
    assert body.status == "needs_confirmation" and body.needs_confirmation
    assert [c.category_id for c in body.candidates] == ["toilet_tissue", "plastic_kitchenware"]
    assert body.candidates[0].name_ar and body.candidates[0].confidence == 0.55
    assert body.report is None and body.explanation is None
    assert llm.ops() == ["normalize"]  # no explanation spent on an unconfirmed category


def test_confidence_threshold_is_configurable(make_settings):
    llm = FakeLLM(normalize=norm_output(confidence=0.55))
    body = ok(client_with(make_settings, llm, confirm_confidence_threshold=0.5).post(
        "/api/analyze", data={"text": "cup"}))
    assert body.status == "complete"


@pytest.mark.parametrize(
    "norm",
    [norm_output("unsupported", 0.9), norm_output("plastic_kitchenware", 0.9, physical=False)],
)
def test_unsupported(make_settings, norm):
    llm = FakeLLM(normalize=norm)
    body = ok(client_with(make_settings, llm).post("/api/analyze", data={"text": "a mobile app"}))
    assert body.status == "unsupported" and body.report is None and body.product.category_id is None
    assert llm.ops() == ["normalize"]


def test_confirm_endpoint(llm_client, fake_llm):
    payload = {"category_id": "glass_containers", "language": "ar",
               "product": {"name_en": "Jam jar", "name_ar": "مرطبان", "description": "Glass jar"}}
    body = ok(llm_client.post("/api/analyze/confirm", json=payload))
    assert body.status == "complete" and body.report.category_id == "glass_containers"
    assert body.report.verdict == "DONT" and body.product.name_en == "Jam jar"
    assert fake_llm.ops() == ["explain"] and fake_llm.calls[0][3] == "ar"


def test_confirm_without_product_uses_category_names(llm_client):
    body = ok(llm_client.post("/api/analyze/confirm", json={"category_id": "led_lamps"}))
    assert body.product.name_en == STORE.get("led_lamps").name_en


def test_confirm_works_without_llm_using_template(client):
    body = ok(client.post("/api/analyze/confirm", json={"category_id": "led_lamps", "language": "ar"}))
    assert body.explanation_source == "fallback" and body.warnings
    assert body.explanation == fallback_explanation(body.report, "ar")


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        ({"category_id": "spaceships"}, 404, "unknown_category"),
        ({"category_id": "led_lamps", "language": "fr"}, 422, "validation_error"),
        ({"category_id": "led_lamps", "product": {"name_en": "x" * 201}}, 422, "validation_error"),
        ({"category_id": "led_lamps", "score": 10}, 422, "validation_error"),
        ({}, 422, "validation_error"),
    ],
)
def test_confirm_validation(llm_client, payload, status, code):
    err(llm_client.post("/api/analyze/confirm", json=payload), status, code)


# --- grounding guard / explanation fallback --------------------------------------------

def test_fabricated_numbers_trigger_template_fallback(make_settings):
    def fabricated(facts):
        return ExplanationLLMOutput(
            summary="Imports will triple to 999 million USD by 2030.",
            reasons_for=["a", "b", "c"], concerns=["d", "e", "f"], next_steps=["g", "h", "i"], caveats=[],
        )

    body = ok(client_with(make_settings, FakeLLM(explain=fabricated)).post("/api/analyze", data={"text": "cup"}))
    assert body.explanation_source == "fallback"
    assert body.explanation == fallback_explanation(body.report, "en")
    assert "999" not in body.explanation.model_dump_json()  # not the whole body: request_id hex may contain 999
    assert any("numbers not found" in w for w in body.warnings)


@pytest.mark.parametrize("error", [LLMUnavailable("down"), LLMInvalidOutput("bad"), LLMRefused("no")])
def test_explanation_failure_uses_template(make_settings, error):
    body = ok(client_with(make_settings, FakeLLM(explain=error)).post("/api/analyze", data={"text": "cup"}))
    assert body.status == "complete" and body.explanation_source == "fallback" and body.warnings


# --- LLM failures on normalisation ------------------------------------------------------

@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (LLMUnavailable("down"), 503, "llm_unavailable"),
        (LLMInvalidOutput("bad"), 502, "llm_invalid_output"),
        (LLMRefused("no"), 422, "input_refused"),
    ],
)
def test_normalize_failures_return_clear_errors(make_settings, error, status, code):
    r = client_with(make_settings, FakeLLM(normalize=error)).post("/api/analyze", data={"text": "cup"})
    err(r, status, code)


def test_no_llm_configured(client):
    err(client.post("/api/analyze", data={"text": "cup"}), 503, "llm_not_configured")


# --- input validation ------------------------------------------------------------------

@pytest.mark.parametrize(
    ("kwargs", "status", "code"),
    [
        ({"data": {}}, 400, "empty_input"),
        ({"data": {"text": "   "}}, 400, "empty_input"),
        ({"data": {"text": "x" * 1001}}, 400, "text_too_long"),
        ({"data": {"text": "cup", "language": "fr"}}, 422, "validation_error"),
        ({"files": {"image": ("a.gif", b"GIF89a....", "image/gif")}}, 415, "unsupported_image_type"),
        ({"files": {"image": ("a.png", b"garbage", "image/png")}}, 400, "invalid_image"),
    ],
)
def test_analyze_input_validation(llm_client, fake_llm, kwargs, status, code):
    err(llm_client.post("/api/analyze", **kwargs), status, code)
    assert fake_llm.calls == []  # invalid input never reaches the LLM


def test_image_over_limit_rejected(make_settings, fake_llm):
    c = client_with(make_settings, fake_llm, max_upload_bytes=1024)
    err(c.post("/api/analyze", files={"image": ("a.png", png_bytes((200, 200)) + b"\0" * 2048, "image/png")}),
        413, "image_too_large")


def test_request_body_over_limit_rejected_before_parsing(make_settings, fake_llm):
    c = client_with(make_settings, fake_llm, max_upload_bytes=1024)
    big = b"\0" * (400 * 1024)
    err(c.post("/api/analyze", files={"image": ("a.png", big, "image/png")}), 413, "payload_too_large")
    assert fake_llm.calls == []


def test_chunked_upload_without_length_rejected(llm_client, fake_llm):
    def chunks():
        yield b"--x\r\nContent-Disposition: form-data; name=\"text\"\r\n\r\ncup\r\n--x--\r\n"

    r = llm_client.post("/api/analyze", content=chunks(),
                        headers={"Content-Type": "multipart/form-data; boundary=x"})
    err(r, 411, "length_required")
    assert fake_llm.calls == []


def test_uploads_stay_in_memory(make_settings):
    settings = make_settings()
    create_app(settings, llm=FakeLLM())
    assert MultiPartParser.spool_max_size > settings.max_upload_bytes


# --- grounding retry ------------------------------------------------------------------

def _fabricated(facts):
    return ExplanationLLMOutput(
        summary="Imports will triple to 999 million USD by 2030.",
        reasons_for=["a", "b", "c"], concerns=["d", "e", "f"], next_steps=["g", "h", "i"], caveats=[],
    )


def test_grounding_retry_second_answer_passes(make_settings):
    llm = FakeLLM(explain=[_fabricated, grounded_explanation])
    body = ok(client_with(make_settings, llm).post("/api/analyze", data={"text": "cup"}))
    assert body.explanation_source == "llm" and body.warnings == []
    explains = [c for c in llm.calls if c[0] == "explain"]
    assert len(explains) == 2
    assert explains[0][4] is None
    feedback = explains[1][4]
    assert "999" in feedback and "2030" in feedback
    assert feedback.startswith("Your previous answer used numbers that are not in the report: [")
    assert feedback.endswith("Rewrite using only numbers from <key_figures>, <report> or <data_notes>.")


def test_grounding_retry_both_fail_uses_template(make_settings):
    llm = FakeLLM(explain=[_fabricated, _fabricated])
    body = ok(client_with(make_settings, llm).post("/api/analyze", data={"text": "cup"}))
    assert body.explanation_source == "fallback"
    assert body.explanation == fallback_explanation(body.report, "en")
    assert any("even after a retry" in w for w in body.warnings)
    assert llm.ops() == ["normalize", "explain", "explain"]


def test_grounded_first_answer_makes_one_call(llm_client, fake_llm):
    ok(llm_client.post("/api/analyze", data={"text": "cup"}))
    assert fake_llm.ops() == ["normalize", "explain"]


def test_retry_failing_with_llm_error_uses_template(make_settings):
    llm = FakeLLM(explain=[_fabricated, LLMUnavailable("down")])
    body = ok(client_with(make_settings, llm).post("/api/analyze", data={"text": "cup"}))
    assert body.explanation_source == "fallback" and len([c for c in llm.calls if c[0] == "explain"]) == 2


# --- timings ------------------------------------------------------------------------

def test_timings_on_complete(llm_client):
    t = ok(llm_client.post("/api/analyze", data={"text": "cup"})).timings_ms
    assert None not in (t.normalize, t.score, t.explain)
    assert t.total >= t.normalize + t.score + t.explain - 1  # rounding slack


def test_timings_on_needs_confirmation(make_settings):
    body = ok(client_with(make_settings, FakeLLM(normalize=norm_output(confidence=0.4))).post(
        "/api/analyze", data={"text": "cup"}))
    assert body.timings_ms.normalize is not None
    assert body.timings_ms.score is None and body.timings_ms.explain is None and body.timings_ms.total > 0


def test_timings_on_confirm(llm_client):
    t = ok(llm_client.post("/api/analyze/confirm", json={"category_id": "led_lamps"})).timings_ms
    assert t.normalize is None and t.score is not None and t.explain is not None
