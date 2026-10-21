"""Comprehensive test suite for ProcessFoundry AI improvements:
- Pool lifecycle and connection reuse
- SQLite restriction and fail-fast configuration validation
- Background analysis tasks, duplicate prevention, and run cancellation
- Scanned PDF image OCR fallback, read_from_image flag, and empty document rejection
- 'What I understood' document view endpoint with citations
- Strict Gemini error handling (no silent mock fallback)
"""
import io
import os
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.database import db
from app.services.document_parser import document_parser, DocumentParserError
from app.services.llm_service import LLMService, LLMServiceError
from app.schemas.evidence import SectionEvidenceExtraction
from app.graph.build_graph import is_run_cancelled, execute_project_run_background
import pymupdf

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_new.db")
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    db._init_sqlite()

def get_auth_token_and_project(client):
    reg = client.post("/api/auth/register", json={
        "display_name": "Test Engineer",
        "email": "engineer@processfoundry.ai",
        "password": "Password123!",
        "repeat_password": "Password123!"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    proj = client.post("/api/projects", json={
        "name": "Hostel Fee Waiver",
        "role": "process_owner",
        "process_type": "student_affairs",
        "description": "Hostel allotment and fee waiver review."
    }, headers=headers)
    project_id = proj.json()["id"]
    return headers, project_id

# -------------------------------------------------------------------------
# 1. Database Configuration & SQLite Restrictions
# -------------------------------------------------------------------------
def test_sqlite_fallback_fails_fast_in_production(monkeypatch):
    """When DATABASE_URL is empty in normal production, fail fast with a clear error.

    Covers SPEC-01-06.
    """
    monkeypatch.setattr(db, "use_postgres", False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ALLOW_SQLITE", raising=False)
    # The same flags are also readable from .env, so clear those too.
    from app.core.config import settings as _settings
    monkeypatch.setattr(_settings, "app_env", "", raising=False)
    monkeypatch.setattr(_settings, "environment", "", raising=False)
    monkeypatch.setattr(_settings, "allow_sqlite", "", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        db.validate_configuration()
    assert "DATABASE_URL is missing or empty" in str(exc_info.value)
    assert "SQLite is restricted" in str(exc_info.value)

def test_sqlite_allowed_with_explicit_flag(monkeypatch):
    """When ALLOW_SQLITE=true, validation passes for local test environments.

    Covers SPEC-01-06.
    """
    monkeypatch.setattr(db, "use_postgres", False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("ALLOW_SQLITE", "true")
    # Should not raise
    db.validate_configuration()

# -------------------------------------------------------------------------
# 2. Database Connection Pool Lifecycle
# -------------------------------------------------------------------------
def test_pool_lifecycle_cleanup():
    """Verify close_pool safely closes pool and resets state.

    Covers SPEC-01-06.
    """
    db.close_pool()
    assert db._pool is None

# -------------------------------------------------------------------------
# 3. Scanned PDFs & Image-Based Extraction
# -------------------------------------------------------------------------
def test_scanned_pdf_triggers_image_extraction_and_warning():
    """A PDF with scanned image page renders, marks read_from_image, and adds warning.

    Covers SPEC-03-01.
    """
    # Create a synthetic PDF with empty text layer (simulating scanned page)
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(pymupdf.Rect(50, 50, 200, 200), color=(0, 0, 0))
    pdf_bytes = doc.tobytes()
    doc.close()

    sections, warnings = document_parser.parse("scanned_fee_guidelines.pdf", pdf_bytes)
    assert len(sections) > 0
    # Provenance flag must be True
    assert any(s.get("read_from_image") is True for s in sections)
    # Required user warning must be present verbatim
    assert "Read from images, check the wording." in warnings

def test_empty_document_rejection():
    """Never mark an empty document as successfully parsed.

    Covers SPEC-03-02.
    """
    # Completely empty text file
    with pytest.raises(DocumentParserError) as exc_info:
        document_parser.parse("empty.txt", b"   \n  \t  ")
    assert "zero usable" in str(exc_info.value).lower()

    # Upload empty file via API
    client = TestClient(app)
    headers, project_id = get_auth_token_and_project(client)
    res = client.post(
        f"/api/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("blank.txt", b"   ", "text/plain")}
    )
    assert res.status_code == 400
    assert "zero usable" in res.json()["detail"].lower()

# -------------------------------------------------------------------------
# 4. 'What I understood' Document View Endpoint
# -------------------------------------------------------------------------
def test_document_understanding_view_endpoint():
    """GET /documents/{id}/understanding returns structured facts, exact quotes, and page refs.

    Covers SPEC-12-03, SPEC-13-05.
    """
    client = TestClient(app)
    headers, project_id = get_auth_token_and_project(client)

    # Upload valid document
    doc_content = (
        "1. OVERVIEW AND APPLICABILITY\n"
        "This policy governs all undergraduate hostel fee waivers for students.\n\n"
        "2. REQUIRED DOCUMENTS\n"
        "Students must submit an official Income Certificate issued by the Tahsildar.\n"
        "A copy of the previous semester Grade Sheet must be attached.\n\n"
        "3. APPLICATION PROCESS\n"
        "The applicant submits Form HW-1 to the Warden before the 15th of August.\n"
        "The Warden verifies the documents and forwards the dossier to the Dean of Student Affairs.\n\n"
        "4. FEES AND CONCESSIONS\n"
        "A waiver of 50 percent of the hostel seat rent is granted to eligible candidates.\n"
        "An application processing charge of $20 is non-refundable.\n"
    ).encode("utf-8")

    upload_res = client.post(
        f"/api/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("fee_waiver_policy.txt", doc_content, "text/plain")}
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Retrieve 'What I understood' view
    und_res = client.get(f"/api/documents/{doc_id}/understanding", headers=headers)
    assert und_res.status_code == 200
    data = und_res.json()

    assert data["document_id"] == doc_id
    assert "document_type" in data
    assert "summary" in data
    assert "required_documents" in data
    assert "process_steps" in data
    assert "fees" in data
    assert "dates_and_deadlines" in data
    assert "people_roles_responsibilities" in data
    assert "missing_or_uncertain_information" in data

    # Verify fact structure
    summary = data["summary"]
    assert "statement" in summary
    assert "is_extracted_fact" in summary

# -------------------------------------------------------------------------
# 5. Background Analysis, Duplicate Prevention & Cancellation
# -------------------------------------------------------------------------
def test_background_run_execution_and_cancellation():
    """POST /runs returns promptly, progress is tracked, and cancellation stops execution.

    Covers SPEC-12-04, SPEC-09-05.
    """
    client = TestClient(app)
    headers, project_id = get_auth_token_and_project(client)

    # Upload source doc
    doc_content = (
        "1. ELIGIBILITY\nStudents with family income below 2 lakhs are eligible.\n"
        "2. PROCEDURE\nSubmit application to Warden.\n"
    ).encode("utf-8")
    client.post(
        f"/api/projects/{project_id}/documents",
        headers=headers,
        files={"file": ("sop.txt", doc_content, "text/plain")}
    )

    # 1. Trigger run
    run_res = client.post(f"/api/projects/{project_id}/runs", headers=headers)
    assert run_res.status_code == 200
    run_data = run_res.json()
    run_id = run_data["id"]
    assert run_id is not None
    assert "status" in run_data
    assert "progress" in run_data

    # 2. Duplicate trigger while active returns the active run
    # Emulate an active run
    active_run = db.create_run(project_id)
    dup_res = client.post(f"/api/projects/{project_id}/runs", headers=headers)
    assert dup_res.status_code == 200
    assert dup_res.json()["id"] == active_run["id"]

    # 3. Status endpoint GET /runs/{id}
    status_res = client.get(f"/api/runs/{active_run['id']}", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["id"] == active_run["id"]
    assert "stage" in status_res.json()
    assert "progress" in status_res.json()

    # 4. Cancel run
    cancel_res = client.post(f"/api/runs/{active_run['id']}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert is_run_cancelled(active_run["id"]) is True

    # 5. Check run status reflects cancelled
    updated_run = client.get(f"/api/runs/{active_run['id']}", headers=headers).json()
    assert updated_run["status"] == "cancelled"

# -------------------------------------------------------------------------
# 6. Strict Gemini Errors (No Silent Mock Fallback)
# -------------------------------------------------------------------------
def test_gemini_provider_fails_without_silent_mock_fallback(monkeypatch):
    """When LLM_PROVIDER=gemini, missing key or API failure must raise LLMServiceError.

    Covers SPEC-02-02.
    """
    monkeypatch.setattr("app.core.config.settings.llm_provider", "gemini")
    monkeypatch.setattr("app.core.config.settings.llm_api_key", "")

    svc = LLMService()
    with pytest.raises(LLMServiceError) as exc_info:
        svc.complete_json("Extract claims", SectionEvidenceExtraction)

    assert "LLM_PROVIDER is configured as 'gemini' but LLM_API_KEY is not set" in str(exc_info.value)
