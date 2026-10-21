"""Tests for LangGraph StateGraph Routing, Pause on Critical Questions, and Resumption (SPEC-07)."""
import pytest
from app.graph.state import ProcessFoundryState
from app.graph.routing import check_critical_gaps_router, quality_repair_router
from app.repositories.database import db
from app.graph.build_graph import start_or_resume_project_run

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_routing.db")
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    db._init_sqlite()

def test_router_pauses_on_critical_conflicting_rules():
    """SPEC-07: check_critical_gaps_router must route to pause_for_human when conflicting_rules are open.

    Covers SPEC-09-02, SPEC-08-01.
    """
    state: ProcessFoundryState = {
        "project_id": "p1",
        "run_id": "r1",
        "process_description": "",
        "source_document_ids": [],
        "extracted_sections": [],
        "evidence_items": [],
        "as_is_process": {},
        "candidate_rules": [],
        "issues": [
            {"id": "q1", "status": "open", "kind": "conflicting_rules", "question": "Deadline conflict"}
        ],
        "clarification_answers": [],
        "verified_facts": [],
        "to_be_process": {},
        "automation_assessment": [],
        "requirements": [],
        "artifacts": [],
        "validation_errors": [],
        "approval_status": "draft",
        "next_action": "",
        "retry_count": 0,
        "is_paused": False
    }
    route = check_critical_gaps_router(state)
    assert route == "pause_for_human"

def test_router_pauses_on_critical_missing_actor():
    """SPEC-07: check_critical_gaps_router must route to pause_for_human when missing_actor questions are open.

    Covers SPEC-09-02, SPEC-08-01.
    """
    state: ProcessFoundryState = {
        "project_id": "p1",
        "run_id": "r1",
        "process_description": "",
        "source_document_ids": [],
        "extracted_sections": [],
        "evidence_items": [],
        "as_is_process": {},
        "candidate_rules": [],
        "issues": [
            {"id": "q2", "status": "open", "kind": "missing_actor", "question": "Who performs step?"}
        ],
        "clarification_answers": [],
        "verified_facts": [],
        "to_be_process": {},
        "automation_assessment": [],
        "requirements": [],
        "artifacts": [],
        "validation_errors": [],
        "approval_status": "draft",
        "next_action": "",
        "retry_count": 0,
        "is_paused": False
    }
    route = check_critical_gaps_router(state)
    assert route == "pause_for_human"

def test_router_proceeds_when_critical_questions_resolved():
    """SPEC-07: check_critical_gaps_router must route to proceed_to_redesign when questions are answered.

    Covers SPEC-09-02, SPEC-09-03.
    """
    state: ProcessFoundryState = {
        "project_id": "p1",
        "run_id": "r1",
        "process_description": "",
        "source_document_ids": [],
        "extracted_sections": [],
        "evidence_items": [],
        "as_is_process": {},
        "candidate_rules": [],
        "issues": [
            {"id": "q1", "status": "resolved", "kind": "conflicting_rules", "question": "Resolved"}
        ],
        "clarification_answers": [{"question_id": "q1", "answer": "31 March"}],
        "verified_facts": [],
        "to_be_process": {},
        "automation_assessment": [],
        "requirements": [],
        "artifacts": [],
        "validation_errors": [],
        "approval_status": "draft",
        "next_action": "",
        "retry_count": 0,
        "is_paused": False
    }
    route = check_critical_gaps_router(state)
    assert route == "proceed_to_redesign"

def test_quality_repair_router_bounded_iterations():
    """SPEC-07: Quality repair loop must be strictly bounded (at most 2 retries before marking review).

    Covers SPEC-09-04.
    """
    # 0 retries with errors -> retry
    state_0: ProcessFoundryState = {"validation_errors": ["orphan_req_1"], "retry_count": 0}  # type: ignore
    assert quality_repair_router(state_0) == "repair_and_retry"

    # 1 retry with errors -> retry
    state_1: ProcessFoundryState = {"validation_errors": ["orphan_req_1"], "retry_count": 1}  # type: ignore
    assert quality_repair_router(state_1) == "repair_and_retry"

    # 2 retries (exceeded) -> mark_needs_review
    state_2: ProcessFoundryState = {"validation_errors": ["orphan_req_1"], "retry_count": 2}  # type: ignore
    assert quality_repair_router(state_2) == "mark_needs_review"

    # No errors -> complete
    state_ok: ProcessFoundryState = {"validation_errors": [], "retry_count": 1}  # type: ignore
    assert quality_repair_router(state_ok) == "complete"
