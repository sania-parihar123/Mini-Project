"""Tests for Business Rules and Gap/Conflict Detection (SPEC-05, SPEC-06)."""
import pytest
from app.repositories.database import db
from app.agents.rules import BusinessRuleAgent
from app.agents.gaps import GapAnalysisAgent, route_question_to_role

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_rules_gaps.db")
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    db._init_sqlite()

def test_conflicting_rules_preserved_as_separate_rows():
    """SPEC-05: Conflicting rules must be saved as distinct rows rather than overwritten.

    Covers SPEC-06-02, SPEC-06-04, SPEC-01-02.
    """
    user = db.create_user("Analyst", "analyst@example.com", "HashedPass123!")
    project = db.create_project(name="Scholarship", user_id=user["id"])
    
    rule1 = db.save_business_rule(
        project_id=project["id"],
        description="Application deadline is 31 March.",
        condition_json={"deadline": "31 March", "quote": "All applications must be submitted by 31 March."},
        evidence_ids=[]
    )
    rule2 = db.save_business_rule(
        project_id=project["id"],
        description="Application deadline is 15 April.",
        condition_json={"deadline": "15 April", "quote": "All applications must be submitted by 15 April."},
        evidence_ids=[]
    )
    
    rules = db.list_project_business_rules(project["id"])
    assert len(rules) == 2
    keys = [r["rule_key"] for r in rules]
    assert "BR-001" in keys
    assert "BR-002" in keys
    assert rule1["id"] != rule2["id"]

def test_gap_detection_missing_actor():
    """SPEC-06: Process steps with no actor must trigger a missing_actor clarification question.

    Covers SPEC-07-01, SPEC-07-05, SPEC-05-02.
    """
    agent = GapAnalysisAgent()
    user = db.create_user("Owner", "owner@example.com", "HashedPass123!")
    project = db.create_project(name="Admissions", user_id=user["id"])
    pv = db.create_process_version(project["id"], version=1)
    
    step = db.save_process_step(
        project_id=project["id"],
        process_version_id=pv["id"],
        name="Verify High School Transcripts",
        actor=None,  # Missing actor!
        step_type="task",
        sequence=1,
        inputs=["Transcripts"],
        outputs=["Verification Report"],
        unknowns=["actor not stated"]
    )
    
    questions = agent.detect_gaps_and_conflicts(
        project_id=project["id"],
        process_steps=[step],
        business_rules=[],
        evidence_items=[]
    )
    
    # The agent also reports a process with no appeal or notification path
    # (brief 9.1 "one missing piece"), so there is more than one question now.
    actor_qs = [q for q in questions if q["kind"] == "missing_actor"]
    assert len(actor_qs) == 1, f"expected exactly one missing_actor question, got {len(actor_qs)}"
    q = actor_qs[0]
    assert q["assigned_role"] == "process_owner"
    assert "Verify High School Transcripts" in q["question"]

def test_gap_detection_conflicting_dates():
    """SPEC-06: Two rules with conflicting dates must generate a conflicting_rules clarification.

    Covers SPEC-06-01, SPEC-06-03, SPEC-07-01, SPEC-07-04.
    """
    agent = GapAnalysisAgent()
    user = db.create_user("Owner", "owner2@example.com", "HashedPass123!")
    project = db.create_project(name="Admissions 2", user_id=user["id"])
    
    r1 = db.save_business_rule(
        project_id=project["id"],
        description="Applications must be submitted by 31 March",
        condition_json={},
        evidence_ids=[]
    )
    r2 = db.save_business_rule(
        project_id=project["id"],
        description="Late forms accepted until 15 April",
        condition_json={},
        evidence_ids=[]
    )
    
    questions = agent.detect_gaps_and_conflicts(
        project_id=project["id"],
        process_steps=[],
        business_rules=[r1, r2],
        evidence_items=[]
    )
    
    conflict_qs = [q for q in questions if q["kind"] == "conflicting_rules"]
    assert len(conflict_qs) == 1, (
        "one subject must produce one question, not one per pair of rules"
    )
    q = conflict_qs[0]
    assert "31 March" in q["question"]
    assert "15 April" in q["question"]
    assert q["assigned_role"] == "process_owner"
    # Appendix rule 4: the wording must not assert a process-specific subject.
    assert "submission deadline" not in q["question"].lower()
    labels = [o["label"] for o in q["options"]]
    assert "31 March" in labels and "15 April" in labels
    assert any(o.get("letter") == "A" for o in q["options"])

def test_gap_detection_vague_terms():
    """SPEC-06: Vague terms like 'appropriate' or 'timely' must generate ambiguous_term question.

    Covers SPEC-07-01.
    """
    agent = GapAnalysisAgent()
    user = db.create_user("Owner", "owner3@example.com", "HashedPass123!")
    project = db.create_project(name="Admissions 3", user_id=user["id"])
    doc = db.save_document(
        project_id=project["id"],
        filename="policy.txt",
        mime_type="text/plain",
        checksum="cs123",
        storage_path="path/policy.txt",
        size_bytes=100,
        uploaded_by=user["id"]
    )
    sec = db.save_document_sections(doc["id"], [{
        "section_title": "Rules",
        "text": "Applicant must submit timely documentation for admission."
    }])[0]
    ev = db.save_evidence_item(
        project_id=project["id"],
        section_id=sec["id"],
        claim="Submit timely documentation",
        quote="Applicant must submit timely documentation for admission.",
        claim_type="rule",
        confidence=0.9
    )
    
    questions = agent.detect_gaps_and_conflicts(
        project_id=project["id"],
        process_steps=[],
        business_rules=[],
        evidence_items=[ev]
    )
    
    vague_qs = [q for q in questions if q["kind"] == "ambiguous_term"]
    assert len(vague_qs) == 1
    assert "timely" in vague_qs[0]["question"]

def test_question_fingerprint_uniqueness():
    """SPEC-06: Running gap detection twice must not duplicate questions with the same fingerprint.

    Covers SPEC-07-02, SPEC-01-05.
    """
    agent = GapAnalysisAgent()
    user = db.create_user("Owner", "owner4@example.com", "HashedPass123!")
    project = db.create_project(name="Admissions 4", user_id=user["id"])
    pv = db.create_process_version(project["id"], version=1)
    step = db.save_process_step(
        project_id=project["id"],
        process_version_id=pv["id"],
        name="Submit Form",
        actor=None,
        step_type="task",
        sequence=1,
        inputs=[],
        outputs=[],
        unknowns=["actor not stated"]
    )
    
    q_pass1 = agent.detect_gaps_and_conflicts(project["id"], [step], [], [])
    first_count = len(db.list_project_clarification_items(project["id"]))
    assert first_count == len(q_pass1) >= 1

    # Second pass with the same inputs must add nothing (AC-07-03).
    agent.detect_gaps_and_conflicts(project["id"], [step], [], [])
    all_qs = db.list_project_clarification_items(project["id"])
    assert len(all_qs) == first_count, (
        f"re-running created {len(all_qs) - first_count} duplicate question(s)"
    )
    assert len({q["fingerprint"] for q in all_qs}) == len(all_qs)
