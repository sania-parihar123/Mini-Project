"""Tests for Traceability Matrix and Quote Audit (SPEC-12)."""
import pytest
from app.repositories.database import db
from app.agents.quality import QualityAgent

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_traceability.db")
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    db._init_sqlite()

def test_quote_audit_zero_mismatches_on_valid_evidence():
    """SPEC-12: Verbatim quote audit must report 0 violations when quotes match source text.

    Covers SPEC-11-04, SPEC-11-01, SPEC-11-05.
    """
    agent = QualityAgent()
    user = db.create_user("Admin", "admin@processfoundry.ai", "HashedPass123!")
    project = db.create_project("Admissions Review", user["id"])
    doc = db.save_document(
        project_id=project["id"],
        filename="admissions.txt",
        mime_type="text/plain",
        checksum="cs_adm",
        storage_path="path/admissions.txt",
        size_bytes=200,
        uploaded_by=user["id"]
    )
    secs = db.save_document_sections(doc["id"], [{
        "section_title": "Eligibility",
        "text": "Students must have completed 12 years of formal schooling."
    }])
    ev = db.save_evidence_item(
        project_id=project["id"],
        section_id=secs[0]["id"],
        claim="12 years formal schooling required",
        quote="Students must have completed 12 years of formal schooling.",
        claim_type="rule",
        confidence=0.95
    )

    # AC-11-04: validation is read-only and must write nothing (finding F8).
    report = agent.validate_traceability(project["id"])
    assert report.get("quote_mismatches") == 0
    assert db.list_project_artifacts(project["id"]) == [], \
        "validate_traceability must not write artifacts; a GET used to reset approvals"

    # The run's quality step is what persists them.
    report = agent.generate_quality_artifacts(project["id"])
    assert report.get("quote_mismatches") == 0
    art_types = [a["artifact_type"] for a in db.list_project_artifacts(project["id"])]
    assert "traceability_matrix" in art_types

def test_orphan_requirement_detected():
    """SPEC-12: Requirements lacking supporting evidence or rules must be flagged as orphans.

    Covers SPEC-11-02, SPEC-10-02.
    """
    agent = QualityAgent()
    user = db.create_user("Admin 2", "admin2@processfoundry.ai", "HashedPass123!")
    project = db.create_project("Hostel System", user["id"])

    # Create requirement with no supporting rules or evidence
    req = db.save_requirement(
        project_id=project["id"],
        req_type="functional",
        statement="Students must check in via biometrics.",
        title="Automated biometric check-in",
        links=[]
    )

    report = agent.validate_traceability(project["id"])
    orphan_reqs = report.get("orphan_requirements", [])
    assert req["requirement_key"] in orphan_reqs
