"""Tests for Evidence Extraction Agent (A2) and verbatim quote verification (SPEC-04)."""
import pytest
from app.repositories.database import db
from app.agents.evidence import EvidenceAgent
from app.schemas.evidence import SectionEvidenceExtraction, ExtractedEvidenceClaim

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Isolate DB for testing."""
    test_db_path = str(tmp_path / "test_processfoundry.db")
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    db._init_sqlite()

def test_evidence_extraction_verbatim_quote_saved():
    """Covers SPEC-04-01, SPEC-04-03, SPEC-04-04, SPEC-01-02, SPEC-01-03."""
    agent = EvidenceAgent()
    user = db.create_user("Professor", "prof@example.com", "HashedPass123!")
    project = db.create_project(name="Scholarship Review", user_id=user["id"], description="Scholarship sop test")
    doc = db.save_document(
        project_id=project["id"],
        filename="sop.txt",
        mime_type="text/plain",
        checksum="checksum123",
        storage_path="uploads/sop.txt",
        size_bytes=500,
        uploaded_by=user["id"]
    )
    secs = db.save_document_sections(doc["id"], [{
        "section_index": 1,
        "section_title": "Eligibility",
        "text": "Applicants must maintain a minimum 3.5 CGPA."
    }])
    sec = secs[0]

    evidence_items = agent.extract_section_evidence(project["id"], sec)
    assert len(evidence_items) >= 1
    item = evidence_items[0]
    assert "CGPA" in item["quote"] or "Applicants" in item["quote"]
    # Verify verbatim substring invariant
    assert item["quote"] in sec["text"]
    assert item["confidence"] > 0.0

def test_evidence_rejection_when_quote_not_verbatim(monkeypatch):
    """Covers SPEC-04-02."""
    agent = EvidenceAgent()
    user = db.create_user("Professor 2", "prof2@example.com", "HashedPass123!")
    project = db.create_project(name="Policy Review", user_id=user["id"], description="Policy test")
    doc = db.save_document(
        project_id=project["id"],
        filename="policy.txt",
        mime_type="text/plain",
        checksum="checksum456",
        storage_path="uploads/policy.txt",
        size_bytes=500,
        uploaded_by=user["id"]
    )
    secs = db.save_document_sections(doc["id"], [{
        "section_index": 1,
        "section_title": "Submission",
        "text": "Applications must be submitted by 5:00 PM."
    }])
    sec = secs[0]

    # Mock llm_service to return a fabricated quote that is NOT in sec["text"]
    class FakeLLM:
        def wrap_source(self, t): return f"<source>{t}</source>"
        def complete_json(self, prompt, schema, system_instruction):
            return SectionEvidenceExtraction(
                claims=[
                    ExtractedEvidenceClaim(
                        claim="Deadline is 6 PM",
                        quote="Applications must be submitted by 6:00 PM Sharp.", # Fabricated!
                        claim_type="deadline",
                        confidence=0.9
                    )
                ]
            )
    monkeypatch.setattr("app.agents.evidence.llm_service", FakeLLM())

    evidence_items = agent.extract_section_evidence(project["id"], sec)
    # The agent must discard this claim because "6:00 PM Sharp" is not in "Applications must be submitted by 5:00 PM."
    assert len(evidence_items) == 0
