"""ProcessFoundry AI: LangGraph Workflow Construction and Execution Engine.

The pipeline is built as three compiled segments rather than one, because the
brief requires the run to stop twice and be continued by a person:

    segment 1  ingest -> evidence -> as_is -> rules -> gaps -> [pause]
    segment 2  gaps_recheck -> to_be -> [pause for To-Be approval]
    segment 3  requirements -> testing -> quality -> (bounded repair) -> complete

Resuming re-enters at the start of the next segment. It never re-enters at
`ingest`: finding F3 of REVIEW_REPORT.md was that answering a question created a
brand-new run from `ingest`, which re-extracted everything, regenerated the same
gap as a new question and paused again, for ever, so no downstream document was
ever produced.
"""
import logging
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END

from app.graph.state import ProcessFoundryState
from app.graph.routing import check_critical_gaps_router, quality_repair_router
from app.repositories.database import db
from app.agents.evidence import evidence_agent
from app.agents.discovery import discovery_agent
from app.agents.rules import business_rule_agent
from app.agents.gaps import gap_analysis_agent
from app.agents.redesign import redesign_agent
from app.agents.requirements import requirements_agent
from app.agents.testing import testing_agent
from app.agents.quality import quality_agent

logger = logging.getLogger("processfoundry.graph")

CRITICAL_KINDS = ("conflicting_rules", "missing_actor")

# Node name stored in runs.current_node while the run waits for the Process
# Owner to decide on the To-Be. runs.status stays 'waiting_for_human', which is
# the only status the schema allows for "a person must act" and is accurate.
NODE_WAITING_FOR_CLARIFICATION = "waiting_for_human"
NODE_WAITING_FOR_TO_BE_APPROVAL = "waiting_for_to_be_approval"


def is_run_cancelled(run_id: Optional[str]) -> bool:
    """Check if the given run has been marked as cancelled by a user."""
    if not run_id:
        return False
    r = db.get_run(run_id)
    return bool(r and r.get("status") == "cancelled")


def _open_critical_questions(project_id: str):
    """Open questions of a kind the brief calls critical (7.11 item 3)."""
    return [
        q for q in db.list_project_clarification_items(project_id, status="open")
        if q["kind"] in CRITICAL_KINDS
    ]


# ---------------------------------------------------------------------------
# Segment 1 nodes: extraction
# ---------------------------------------------------------------------------
def ingest_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} cancelled. Halting ingest_node.")
        return state

    logger.info(f"Executing ingest_node for project {pid}")
    db.update_run_state(rid, status="running", current_node="ingest")

    docs = db.list_project_documents(pid)
    sections = []
    for d in docs:
        d_secs = db.list_document_sections(d["id"])
        sections.extend(d_secs)

    state["source_document_ids"] = [d["id"] for d in docs]
    state["extracted_sections"] = sections
    return state


def evidence_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} cancelled. Halting evidence_node.")
        return state

    logger.info(f"Executing evidence_node for project {pid}")
    db.update_run_state(rid, status="running", current_node="evidence")

    sections = state.get("extracted_sections", [])
    evidence = evidence_agent.run_evidence_pipeline(pid, sections)
    state["evidence_items"] = evidence
    return state


def as_is_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} cancelled. Halting as_is_node.")
        return state

    logger.info(f"Executing as_is_node for project {pid}")
    db.update_run_state(rid, status="running", current_node="as_is")

    evidence = state.get("evidence_items", [])
    p_desc = state.get("process_description", "")
    as_is = discovery_agent.discover_as_is(pid, evidence, p_desc)
    state["as_is_process"] = as_is
    return state


def rules_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} cancelled. Halting rules_node.")
        return state

    logger.info(f"Executing rules_node for project {pid}")
    db.update_run_state(rid, status="running", current_node="rules")

    sections = state.get("extracted_sections", [])
    evidence = state.get("evidence_items", [])
    rules = business_rule_agent.run_rules_pipeline(pid, sections, evidence)
    state["candidate_rules"] = rules
    return state


def gaps_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} cancelled. Halting gaps_node.")
        return state

    logger.info(f"Executing gaps_node for project {pid}")
    db.update_run_state(rid, status="running", current_node="gaps")

    steps = state.get("as_is_process", {}).get("steps", [])
    rules = state.get("candidate_rules", [])
    evidence = state.get("evidence_items", [])

    gap_analysis_agent.detect_gaps_and_conflicts(pid, steps, rules, evidence, run_id=rid)
    state["issues"] = db.list_project_clarification_items(pid, status="open")
    return state


def gaps_recheck_node(state: ProcessFoundryState) -> ProcessFoundryState:
    """Segment 2 entry: reload open questions only.

    No extraction, no model call. This is the whole point of resuming after the
    gap step rather than at `ingest`.
    """
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        return state
    logger.info(f"Re-checking open questions for project {pid} before resuming")
    db.update_run_state(rid, status="running", current_node="gaps_recheck")
    state["issues"] = db.list_project_clarification_items(pid, status="open")
    return state


def pause_node(state: ProcessFoundryState) -> ProcessFoundryState:
    """Persist the checkpoint and stop until a person answers (brief 3.6, 7.11)."""
    pid = state["project_id"]
    rid = state.get("run_id")
    logger.info(f"Pausing graph execution for human clarification on project {pid}")
    state["is_paused"] = True
    state["next_action"] = "await_human_clarification"
    db.update_run_state(
        rid,
        status="waiting_for_human",
        current_node=NODE_WAITING_FOR_CLARIFICATION,
        state_json=_checkpoint(state),
    )
    return state


# ---------------------------------------------------------------------------
# Segment 2 nodes: To-Be proposal, then the approval gate
# ---------------------------------------------------------------------------
def to_be_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} cancelled. Halting to_be_node.")
        return state

    logger.info(f"Executing to_be_node for project {pid}")
    db.update_run_state(rid, status="running", current_node="redesign")

    steps = state.get("as_is_process", {}).get("steps", [])
    if not steps:
        latest = db.get_latest_process_version(pid)
        if latest:
            steps = db.list_process_steps(latest["id"])
    rules = db.list_project_business_rules(pid)
    facts = db.list_verified_facts(pid)

    to_be = redesign_agent.redesign_process(pid, steps, rules, facts)
    state["to_be_process"] = to_be
    state["automation_assessment"] = (to_be or {}).get("steps", [])
    return state


def await_to_be_approval_node(state: ProcessFoundryState) -> ProcessFoundryState:
    """Stop until a Process Owner approves the To-Be (brief 3.5 and 7.11 step 5).

    Brief 3.5: "To-Be not approved -> do not generate final/approved downstream
    artifacts." The run therefore waits here; `POST /api/process-versions/{id}/
    decision` continues it. The AI never sets the approval itself.
    """
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        return state

    owners = [
        m for m in db.list_project_members(pid)
        if m.get("role") == "process_owner" and m.get("status", "active") == "active"
    ]
    if not owners:
        logger.info(f"Project {pid} has no active Process Owner; To-Be cannot be approved yet.")

    state["is_paused"] = True
    state["approval_status"] = "awaiting_to_be_approval"
    state["next_action"] = "await_to_be_approval"
    db.update_run_state(
        rid,
        status="waiting_for_human",
        current_node=NODE_WAITING_FOR_TO_BE_APPROVAL,
        state_json=_checkpoint(state),
    )
    return state


# ---------------------------------------------------------------------------
# Segment 3 nodes: downstream generation, bounded repair, completion
# ---------------------------------------------------------------------------
def requirements_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} cancelled. Halting requirements_node.")
        return state

    logger.info(f"Executing requirements_node for project {pid}")
    db.update_run_state(rid, status="running", current_node="requirements")

    steps = state.get("as_is_process", {}).get("steps", [])
    if not steps:
        latest = db.get_latest_process_version(pid)
        if latest:
            steps = db.list_process_steps(latest["id"])
    rules = db.list_project_business_rules(pid)
    facts = db.list_verified_facts(pid)
    to_be = state.get("to_be_process")

    reqs = requirements_agent.synthesize_requirements(pid, steps, rules, facts, to_be)
    artifacts = requirements_agent.generate_all_artifacts(pid)
    state["requirements"] = reqs
    state["artifacts"] = artifacts
    return state


def testing_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} cancelled. Halting testing_node.")
        return state

    logger.info(f"Executing testing_node for project {pid}")
    db.update_run_state(rid, status="running", current_node="testing")

    reqs = db.list_project_requirements(pid)
    tests = testing_agent.generate_tests_and_uat(pid, reqs)
    state.setdefault("artifacts", [])
    state["artifacts"].append({"type": "test_cases", "count": len(tests)})
    return state


def quality_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} cancelled. Halting quality_node.")
        return state

    logger.info(f"Executing quality_node for project {pid}")
    db.update_run_state(rid, status="running", current_node="quality")

    report = quality_agent.generate_quality_artifacts(pid)
    state["validation_errors"] = report.get("orphan_requirements", [])
    state["validation_report"] = report
    return state


def repair_node(state: ProcessFoundryState) -> ProcessFoundryState:
    """One bounded repair attempt (SPEC-09-04: at most two, then stop).

    Repair is deterministic: requirements with no supporting link are marked
    `needs_clarification` with the brief's wording, rather than being silently
    accepted or endlessly regenerated.
    """
    pid = state["project_id"]
    rid = state.get("run_id")
    attempt = state.get("retry_count", 0) + 1
    state["retry_count"] = attempt
    logger.info(f"Quality repair attempt {attempt} of 2 for project {pid}")
    db.update_run_state(rid, status="running", current_node=f"repair_{attempt}")

    repaired = quality_agent.repair_orphan_requirements(pid, state.get("validation_errors", []))
    logger.info(f"Repair attempt {attempt} adjusted {repaired} requirement(s)")
    return state


def needs_review_node(state: ProcessFoundryState) -> ProcessFoundryState:
    """Repair budget exhausted: save the error report and stop (SPEC-09-04)."""
    pid = state["project_id"]
    rid = state.get("run_id")
    errors = state.get("validation_errors", [])
    logger.warning(
        f"Project {pid}: {len(errors)} validation error(s) remain after 2 repair attempts; "
        "marking Needs Review."
    )
    state["approval_status"] = "needs_review"
    state["next_action"] = "needs_review"
    state["is_paused"] = False
    db.update_run_state(
        rid,
        status="completed",
        current_node="needs_review",
        state_json=_checkpoint(state),
        last_error=(
            f"{len(errors)} traceability problem(s) could not be repaired automatically "
            "after 2 attempts. The generated documents are marked Needs Review."
        ),
    )
    db.log_audit_event(
        pid, "run_marked_needs_review", actor="system",
        subject=str(rid), details={"validation_errors": len(errors)},
    )
    return state


def complete_node(state: ProcessFoundryState) -> ProcessFoundryState:
    pid = state["project_id"]
    rid = state.get("run_id")
    if is_run_cancelled(rid):
        logger.info(f"Run {rid} was cancelled before complete_node.")
        return state

    logger.info(f"Workflow completed successfully for project {pid}")
    state["is_paused"] = False
    state["next_action"] = "completed"
    db.update_run_state(
        rid, status="completed", current_node="completed", state_json=_checkpoint(state)
    )
    return state


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------
# Keys that are cheap to reload from the database on resume. Leaving them out of
# runs.state_json keeps the checkpoint small without losing anything.
_BULKY_STATE_KEYS = ("extracted_sections", "evidence_items", "candidate_rules", "issues")


def _checkpoint(state: ProcessFoundryState) -> Dict[str, Any]:
    """The part of the state worth persisting (brief 3.3: no secrets in state)."""
    return {k: v for k, v in dict(state).items() if k not in _BULKY_STATE_KEYS}


def _restore_state(run: Dict[str, Any], project_id: str) -> ProcessFoundryState:
    """Rebuild a resumable state from the saved checkpoint plus stored records."""
    saved = run.get("state_json") or {}
    if isinstance(saved, str):
        import json
        try:
            saved = json.loads(saved)
        except Exception:
            saved = {}

    state: ProcessFoundryState = dict(_initial_state(run["id"], project_id))
    state.update({k: v for k, v in saved.items() if v is not None})
    state["project_id"] = project_id
    state["run_id"] = run["id"]

    # Reload what the checkpoint deliberately omits.
    latest = db.get_latest_process_version(project_id)
    if latest and not (state.get("as_is_process") or {}).get("steps"):
        as_is = dict(latest)
        as_is["steps"] = db.list_process_steps(latest["id"])
        state["as_is_process"] = as_is
    state["candidate_rules"] = db.list_project_business_rules(project_id)
    state["issues"] = db.list_project_clarification_items(project_id, status="open")
    state["verified_facts"] = db.list_verified_facts(project_id)
    state["is_paused"] = False
    return state


def _initial_state(run_id: str, project_id: str) -> ProcessFoundryState:
    project = db.get_project(project_id)
    return {
        "project_id": project_id,
        "run_id": run_id,
        "process_description": project.get("description", "") if project else "",
        "source_document_ids": [],
        "extracted_sections": [],
        "evidence_items": [],
        "as_is_process": {},
        "candidate_rules": [],
        "issues": [],
        "clarification_answers": [],
        "verified_facts": [],
        "to_be_process": {},
        "automation_assessment": [],
        "requirements": [],
        "artifacts": [],
        "validation_errors": [],
        "approval_status": "draft",
        "next_action": "start",
        "retry_count": 0,
        "is_paused": False,
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
def _add_downstream_segment(workflow: StateGraph) -> None:
    """requirements -> testing -> quality -> bounded repair -> complete.

    Wires `quality_repair_router`, which existed and was unit-tested but was
    never attached to the graph (finding F11).
    """
    workflow.add_node("requirements", requirements_node)
    workflow.add_node("testing", testing_node)
    workflow.add_node("quality", quality_node)
    workflow.add_node("repair", repair_node)
    workflow.add_node("needs_review", needs_review_node)
    workflow.add_node("complete", complete_node)

    workflow.add_edge("requirements", "testing")
    workflow.add_edge("testing", "quality")
    workflow.add_conditional_edges(
        "quality",
        quality_repair_router,
        {
            "complete": "complete",
            "repair_and_retry": "repair",
            "mark_needs_review": "needs_review",
        },
    )
    workflow.add_edge("repair", "quality")
    workflow.add_edge("needs_review", END)
    workflow.add_edge("complete", END)


def build_workflow_graph() -> Any:
    """Segment 1: extraction up to the clarification pause."""
    workflow = StateGraph(ProcessFoundryState)
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("evidence", evidence_node)
    workflow.add_node("as_is", as_is_node)
    workflow.add_node("rules", rules_node)
    workflow.add_node("gaps", gaps_node)
    workflow.add_node("pause", pause_node)
    workflow.add_node("to_be", to_be_node)
    workflow.add_node("await_to_be_approval", await_to_be_approval_node)

    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "evidence")
    workflow.add_edge("evidence", "as_is")
    workflow.add_edge("as_is", "rules")
    workflow.add_edge("rules", "gaps")
    workflow.add_conditional_edges(
        "gaps",
        check_critical_gaps_router,
        {"pause_for_human": "pause", "proceed_to_redesign": "to_be"},
    )
    workflow.add_edge("pause", END)
    # The To-Be is proposed, then a human must approve it before anything
    # downstream is generated (brief 3.5).
    workflow.add_edge("to_be", "await_to_be_approval")
    workflow.add_edge("await_to_be_approval", END)
    return workflow.compile()


def build_resume_after_gaps_graph() -> Any:
    """Segment 2: re-enter after the gap step, never at ingest (finding F3)."""
    workflow = StateGraph(ProcessFoundryState)
    workflow.add_node("gaps_recheck", gaps_recheck_node)
    workflow.add_node("pause", pause_node)
    workflow.add_node("to_be", to_be_node)
    workflow.add_node("await_to_be_approval", await_to_be_approval_node)

    workflow.set_entry_point("gaps_recheck")
    workflow.add_conditional_edges(
        "gaps_recheck",
        check_critical_gaps_router,
        {"pause_for_human": "pause", "proceed_to_redesign": "to_be"},
    )
    workflow.add_edge("pause", END)
    workflow.add_edge("to_be", "await_to_be_approval")
    workflow.add_edge("await_to_be_approval", END)
    return workflow.compile()


def build_resume_after_approval_graph() -> Any:
    """Segment 3: downstream generation after the Process Owner approved the To-Be."""
    workflow = StateGraph(ProcessFoundryState)
    _add_downstream_segment(workflow)
    workflow.set_entry_point("requirements")
    return workflow.compile()


workflow_runner = build_workflow_graph()
resume_after_gaps_runner = build_resume_after_gaps_graph()
resume_after_approval_runner = build_resume_after_approval_graph()


# ---------------------------------------------------------------------------
# Execution entry points (all safe to hand to a BackgroundTask)
# ---------------------------------------------------------------------------
def _run_segment(runner, state: ProcessFoundryState, run_id: str, label: str) -> None:
    try:
        if is_run_cancelled(run_id):
            logger.info(f"Run {run_id} was cancelled before {label} started.")
            return
        runner.invoke(state)
    except Exception as e:
        logger.error(f"Run {run_id} failed during {label}: {e}")
        current = db.get_run(run_id)
        if current and current.get("status") != "cancelled":
            db.update_run_state(run_id, status="failed", last_error=str(e))


def execute_project_run_background(run_id: str, project_id: str, user_id: str = "system"):
    """Segment 1, from the start. Used by POST /api/projects/{id}/runs."""
    logger.info(f"Starting background workflow execution for run {run_id} on project {project_id}")
    _run_segment(workflow_runner, _initial_state(run_id, project_id), run_id, "extraction")


def resume_run_after_clarification(run_id: str, project_id: str):
    """Segment 2. Continues the SAME run; never re-extracts (finding F3)."""
    run = db.get_run(run_id)
    if not run:
        logger.warning(f"Cannot resume run {run_id}: it no longer exists.")
        return
    logger.info(f"Resuming run {run_id} after clarification (no re-extraction)")
    _run_segment(
        resume_after_gaps_runner, _restore_state(run, project_id), run_id, "resume after clarification"
    )


def resume_run_after_to_be_approval(run_id: str, project_id: str):
    """Segment 3. Runs only once a human has approved the To-Be (brief 3.5)."""
    run = db.get_run(run_id)
    if not run:
        logger.warning(f"Cannot resume run {run_id}: it no longer exists.")
        return
    logger.info(f"Resuming run {run_id} after To-Be approval")
    state = _restore_state(run, project_id)
    state["approval_status"] = "approved"
    state["retry_count"] = 0
    _run_segment(
        resume_after_approval_runner, state, run_id, "resume after To-Be approval"
    )


def start_or_resume_project_run(project_id: str, user_id: str) -> Dict[str, Any]:
    """Synchronous full run. Kept for tests and scripts only.

    Nothing in the request path calls this: it used to be what the answer
    endpoint invoked, which is how finding F3 arose.
    """
    run = db.create_run(project_id, started_by=user_id)
    execute_project_run_background(run["id"], project_id, user_id)
    return db.get_run(run["id"])
