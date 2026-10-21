"""Tests for the model gateway guard, pacing and quote verification.

Covers SPEC-02-02, SPEC-02-03, SPEC-02-05 and AC-04-02.
Finding F5 of REVIEW_REPORT.md: `.env` shipped with LLM_PROVIDER=mock, so the
running application invented document content and To-Be processes and presented
them as extracted fact, with nothing on screen saying so.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.database import db
from app.services.llm_service import LLMService, llm_service

DOC = b"""1. ELIGIBILITY
Applications must be submitted before 31 March of each year.
The scholarship clerk verifies the income certificate.
"""


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _signed_in(client):
    email = f"llm_{uuid.uuid4().hex[:8]}@example.com"
    password = "LlmPass12345!"
    resp = client.post("/api/auth/register", json={
        "display_name": "LLM Tester", "email": email,
        "password": password, "repeat_password": password,
    })
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# The mock provider must be unreachable outside a test environment
# ---------------------------------------------------------------------------
def test_mock_provider_is_refused_outside_a_test_environment(monkeypatch):
    """SPEC-02-03 / F5: provider 'mock' must not start in a normal run."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ALLOW_SQLITE", raising=False)
    # The same flags are also readable from .env, so clear those too.
    monkeypatch.setattr(settings, "app_env", "", raising=False)
    monkeypatch.setattr(settings, "environment", "", raising=False)
    monkeypatch.setattr(settings, "allow_sqlite", "", raising=False)
    monkeypatch.setattr(settings, "llm_provider", "mock")

    service = LLMService()
    with pytest.raises(RuntimeError) as exc:
        service.validate_configuration()
    assert "LLM_PROVIDER is 'mock'" in str(exc.value)
    assert "invented text" in str(exc.value)


def test_mock_provider_is_allowed_in_a_test_environment(monkeypatch):
    """SPEC-02-03: the offline provider stays available for tests and dev."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setattr(settings, "llm_provider", "mock")
    LLMService().validate_configuration()


def test_gemini_without_a_key_is_refused_at_startup(monkeypatch):
    """SPEC-02-02: a provider that cannot work must fail fast, not at first use."""
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_api_key", "")
    with pytest.raises(RuntimeError, match="LLM_API_KEY is empty"):
        LLMService().validate_configuration()


def test_an_unknown_provider_is_refused(monkeypatch):
    """SPEC-02-02: only the adapters that exist may be selected.

    Covers SPEC-02-01, SPEC-02-02.
    """
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    with pytest.raises(RuntimeError, match="unknown LLM_PROVIDER"):
        LLMService().validate_configuration()


def test_there_is_no_silent_fallback_from_gemini_to_mock(monkeypatch):
    """SPEC-02-02: a missing key must raise, never quietly invent output."""
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_api_key", "")
    service = LLMService()
    from app.schemas.documents import DocumentUnderstandingResponse
    with pytest.raises(Exception) as exc:
        service.complete_json("anything", DocumentUnderstandingResponse)
    assert "LLM_API_KEY" in str(exc.value)


def test_health_endpoint_reports_whether_output_is_invented(client):
    """F5: the UI needs a machine-readable signal to warn the user."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_provider"] == "mock"
    assert body["model_is_mock"] is True


def test_mock_ocr_output_says_it_is_not_from_the_document():
    """F5: invented OCR text must not look like a transcription of the page.

    Covers SPEC-02-03.
    """
    text = llm_service.extract_text_from_image(b"not-a-real-png")
    assert "NOT READ FROM YOUR DOCUMENT" in text
    # The old placeholder invented a plausible fee and deadline.
    assert "$50" not in text
    assert "15th of the month" not in text


# ---------------------------------------------------------------------------
# Pacing and concurrency (brief Phase 0 step 3)
# ---------------------------------------------------------------------------
def test_the_gateway_caps_concurrent_calls_and_paces_them(monkeypatch):
    """SPEC-02-05: at most 2 calls at once, with a gap between them."""
    monkeypatch.setattr(settings, "llm_max_concurrent_calls", 2)
    monkeypatch.setattr(settings, "llm_call_delay_seconds", 0.05)
    service = LLMService()
    assert service._call_slots._initial_value == 2
    assert service.call_delay_seconds == 0.05


def test_the_configured_timeout_is_not_ignored():
    """F14: LLM_TIMEOUT_SECONDS was read into self.timeout and never used.

    Covers SPEC-02-05.
    """
    import inspect
    source = inspect.getsource(LLMService.complete_json)
    assert "http_options" in source, "no timeout is passed to the Gemini client"
    assert "self.timeout" in source
    ocr_source = inspect.getsource(LLMService.extract_text_from_image)
    assert "self.timeout" in ocr_source, "the OCR call has no timeout either"


# ---------------------------------------------------------------------------
# "What I understood": quote verification and caching
# ---------------------------------------------------------------------------
def test_understanding_quotes_are_verified_against_the_source(client):
    """AC-04-02 applied to the understanding view: no unverifiable quote survives.

    Covers SPEC-04-02, SPEC-02-06.
    """
    headers = _signed_in(client)
    pid = client.post("/api/projects", headers=headers,
                      json={"name": "Understanding", "role": "process_owner"}).json()["id"]
    doc = client.post(f"/api/projects/{pid}/documents", headers=headers,
                      files={"file": ("sop.txt", DOC, "text/plain")}).json()

    resp = client.get(f"/api/documents/{doc['id']}/understanding", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    source_text = DOC.decode()
    for field in ("required_documents", "process_steps", "fees",
                  "dates_and_deadlines", "people_roles_responsibilities"):
        for fact in body[field]:
            if fact["exact_quote"]:
                assert fact["exact_quote"] in source_text, (
                    f"{field}: quote not verbatim in the source: {fact['exact_quote']!r}"
                )
                assert fact["quote_verified"] is True


def test_a_fabricated_understanding_quote_is_dropped(client, monkeypatch):
    """The model proposes, code validates: an invented quote must not be shown.

    Covers SPEC-04-02.
    """
    headers = _signed_in(client)
    pid = client.post("/api/projects", headers=headers,
                      json={"name": "Fabrication", "role": "process_owner"}).json()["id"]
    doc = client.post(f"/api/projects/{pid}/documents", headers=headers,
                      files={"file": ("sop.txt", DOC, "text/plain")}).json()

    from app.schemas.documents import DocumentUnderstandingResponse, UnderstandingFact

    def fabricating_model(prompt, schema, system_instruction=None):
        return DocumentUnderstandingResponse(
            document_id="x", filename="x",
            document_type=UnderstandingFact(statement="Policy", exact_quote="1. ELIGIBILITY"),
            summary=UnderstandingFact(statement="Summary", exact_quote="1. ELIGIBILITY"),
            fees=[UnderstandingFact(
                statement="A fee of 9999 rupees applies",
                exact_quote="A fee of 9999 rupees applies to all applicants.",
                page_number=1, is_extracted_fact=True,
            )],
        )

    from app.services import llm_service as llm_module
    monkeypatch.setattr(llm_module.llm_service, "complete_json", fabricating_model)

    resp = client.get(f"/api/documents/{doc['id']}/understanding", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["fees"] == [], "a fabricated quote was presented as an extracted fact"
    assert body["unverified_quotes_dropped"] >= 1
    assert any("discarded" in m for m in body["missing_or_uncertain_information"])


def test_understanding_is_computed_once_per_document_content(client):
    """Item 6: the panel must not fire a model call on every page render.

    Covers SPEC-02-01.
    """
    headers = _signed_in(client)
    pid = client.post("/api/projects", headers=headers,
                      json={"name": "Cached", "role": "process_owner"}).json()["id"]
    doc = client.post(f"/api/projects/{pid}/documents", headers=headers,
                      files={"file": ("sop.txt", DOC, "text/plain")}).json()

    first = client.get(f"/api/documents/{doc['id']}/understanding", headers=headers)
    assert first.status_code == 200

    calls = []
    from app.services import llm_service as llm_module
    real = llm_module.llm_service.complete_json
    llm_module.llm_service.complete_json = lambda *a, **k: (calls.append(1), real(*a, **k))[1]
    try:
        for _ in range(3):
            again = client.get(f"/api/documents/{doc['id']}/understanding", headers=headers)
            assert again.status_code == 200
    finally:
        llm_module.llm_service.complete_json = real

    assert calls == [], f"{len(calls)} extra model call(s) for an unchanged document"


def test_understanding_cache_is_keyed_on_the_content_checksum(client):
    """A different checksum must not be served a stale summary.

    Covers SPEC-03-04.
    """
    headers = _signed_in(client)
    pid = client.post("/api/projects", headers=headers,
                      json={"name": "Checksum", "role": "process_owner"}).json()["id"]
    doc = client.post(f"/api/projects/{pid}/documents", headers=headers,
                      files={"file": ("sop.txt", DOC, "text/plain")}).json()

    client.get(f"/api/documents/{doc['id']}/understanding", headers=headers)
    assert db.get_document_understanding(doc["id"], doc["checksum"]) is not None
    assert db.get_document_understanding(doc["id"], "a-different-checksum") is None


def test_an_empty_document_is_an_error_not_a_summary(client):
    """Item 5: a document that yields nothing must never be shown as parsed.

    Covers SPEC-03-02.
    """
    headers = _signed_in(client)
    pid = client.post("/api/projects", headers=headers,
                      json={"name": "Empty", "role": "process_owner"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/documents", headers=headers,
                       files={"file": ("empty.txt", b"", "text/plain")})
    assert resp.status_code == 400
    assert "is empty" in resp.json()["detail"]
    assert client.get(f"/api/projects/{pid}/documents", headers=headers).json() == []


def test_a_whitespace_only_document_is_rejected_by_the_parser(client):
    """Item 5: content that reaches the parser but yields no section is an error.

    Covers SPEC-03-02.
    """
    headers = _signed_in(client)
    pid = client.post("/api/projects", headers=headers,
                      json={"name": "Blank", "role": "process_owner"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/documents", headers=headers,
                       files={"file": ("blank.txt", b"   \n\n  \t  \n", "text/plain")})
    assert resp.status_code == 400
    assert "zero usable text sections" in resp.json()["detail"]
    assert client.get(f"/api/projects/{pid}/documents", headers=headers).json() == []
