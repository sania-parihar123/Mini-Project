"""End-to-end HTTP test of the whole human-in-the-loop cycle.

Covers AC-08-01, AC-08-02, AC-09-01, AC-09-02, AC-09-03, AC-10-01, AC-10-02,
AC-10-03, AC-11-01 and brief 7.11.

Finding F3 of REVIEW_REPORT.md: answering the last critical question called
`start_or_resume_project_run`, which created a NEW run entering at `ingest`.
That re-extracted everything, regenerated the same gap as a new question with a
new fingerprint, and paused again, so the open-critical count never reached zero
and no To-Be, requirement or document was ever generated.

Finding F6: every run duplicated all extracted rows and re-called the model.

Everything here goes over HTTP, through the real routers and the real graph.
"""
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.database import db

DOC = b"""INSTITUTIONAL PROCESS GUIDELINES

1. APPLICATION WINDOW
Applications must be submitted before 31 March of each year.
The applicant submits the completed form to the office.

2. VERIFICATION
The form is verified.
Eligible students receive a confirmation notice.

3. REVISED TIMEFRAME
Applications must be submitted before 15 April of each year.
The scholarship clerk records the outcome.
"""


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _register(client, name):
    email = f"{name}_{uuid.uuid4().hex[:8]}@example.com"
    password = "LoopPass1234!"
    resp = client.post("/api/auth/register", json={
        "display_name": f"{name.title()} User",
        "email": email,
        "password": password,
        "repeat_password": password,
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, email, body["user"]["id"]


def _counts(project_id):
    return {
        "questions": len(db.list_project_clarification_items(project_id)),
        "rules": len(db.list_project_business_rules(project_id)),
        "evidence": len(db.list_project_evidence(project_id)),
    }


def _open_critical(project_id):
    return [
        q for q in db.list_project_clarification_items(project_id, status="open")
        if q["kind"] in ("conflicting_rules", "missing_actor")
    ]


def _poll(client, headers, run_id, timeout=30.0):
    """Poll the run like the UI does, until it reaches a resting state."""
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        resp = client.get(f"/api/runs/{run_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last.get("status") in ("waiting_for_human", "completed", "failed", "cancelled"):
            return last
        time.sleep(0.05)
    return last


def test_full_loop_upload_run_answer_approve_generates_every_document(client):
    """AC-08-02 / AC-09-02 / AC-10-02 / F3: the loop closes and documents appear.

    Covers SPEC-08-01, SPEC-08-02, SPEC-08-03, SPEC-08-05, SPEC-09-01, SPEC-09-03, SPEC-10-01, SPEC-10-02, SPEC-10-04, SPEC-10-05, SPEC-10-06, SPEC-11-01, SPEC-11-05, SPEC-12-04, SPEC-12-06, SPEC-00-03.
    """
    po, _, _ = _register(client, "owner")

    # --- upload -------------------------------------------------------------
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Full Loop", "role": "process_owner"}).json()["id"]
    up = client.post(f"/api/projects/{pid}/documents", headers=po,
                     files={"file": ("policy.txt", DOC, "text/plain")})
    assert up.status_code == 201, up.text

    # --- run ----------------------------------------------------------------
    started = client.post(f"/api/projects/{pid}/runs", headers=po)
    assert started.status_code == 200, started.text
    run_id = started.json()["id"]

    # --- poll: the run must stop and wait, not auto-resolve -----------------
    run = _poll(client, po, run_id)
    assert run["status"] == "waiting_for_human", f"expected a pause, got {run}"
    assert _open_critical(pid), "nothing was flagged as critical"
    assert not client.get(f"/api/projects/{pid}/artifacts", headers=po).json(), \
        "AC-08-01: no document may be generated while a critical question is open"

    # --- read the questions over HTTP (this is what used to 500) ------------
    listed = client.get(f"/api/projects/{pid}/questions", headers=po)
    assert listed.status_code == 200, listed.text
    inbox = client.get("/api/me/questions", headers=po)
    assert inbox.status_code == 200, inbox.text

    # --- answer every critical question -------------------------------------
    for q in [x for x in inbox.json() if x["kind"] in ("conflicting_rules", "missing_actor")]:
        ans = client.post(f"/api/questions/{q['id']}/answer", headers=po,
                          json={"kind": "answer", "answer_text": "31 March"})
        assert ans.status_code == 200, ans.text

    # --- open-critical count must reach zero (F3) ---------------------------
    assert _open_critical(pid) == [], (
        "open critical questions were regenerated by the resume; the loop cannot close"
    )

    # --- poll: the run must now reach the To-Be approval gate ---------------
    run = _poll(client, po, run_id)
    assert run["status"] == "waiting_for_human", f"expected the approval gate, got {run}"
    assert run["current_node"] == "waiting_for_to_be_approval", (
        f"expected the To-Be approval gate, got current_node={run['current_node']}"
    )

    pv = db.get_latest_process_version(pid)
    assert pv and pv.get("to_be_json"), "AC-10-01: no To-Be process was proposed"
    assert pv["status"] != "approved", "the AI must never approve its own To-Be"

    # --- brief 3.5: nothing downstream before the human approves ------------
    assert not client.get(f"/api/projects/{pid}/artifacts", headers=po).json(), \
        "brief 3.5: downstream documents were generated before To-Be approval"

    # --- the Process Owner approves ----------------------------------------
    decision = client.post(f"/api/process-versions/{pv['id']}/decision", headers=po,
                           json={"decision": "approve"})
    assert decision.status_code == 200, decision.text
    assert decision.json()["downstream_generation_started"] is True

    run = _poll(client, po, run_id)
    assert run["status"] == "completed", f"the run did not finish: {run}"

    # --- every required document must exist --------------------------------
    artifacts = client.get(f"/api/projects/{pid}/artifacts", headers=po).json()
    produced = {a["artifact_type"] for a in artifacts}
    for required in ("brd", "prd", "frd", "workflow_json", "test_plan",
                     "uat_pack", "traceability_matrix", "rules_catalogue", "roles_matrix"):
        assert required in produced, f"AC-10-02: {required} was not generated. Got {sorted(produced)}"

    # AC-00-02: nothing the AI produced may be approved by the AI.
    assert all(a["status"] != "approved" for a in artifacts), \
        "AC-00-02: an artifact was marked approved without a human"

    assert db.list_project_requirements(pid), "AC-10-01: no requirements were generated"
    assert db.list_project_test_cases(pid), "AC-10-03: no test cases were generated"

    trace = client.get(f"/api/projects/{pid}/traceability", headers=po)
    assert trace.status_code == 200, trace.text
    assert trace.json()["chains"], "AC-11-01: the traceability chain is empty"


def test_answering_does_not_create_a_second_run(client):
    """F3: the answer must continue the existing run, not start a new one.

    Covers SPEC-09-05.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "One Run", "role": "process_owner"}).json()["id"]
    client.post(f"/api/projects/{pid}/documents", headers=po,
                files={"file": ("policy.txt", DOC, "text/plain")})
    run_id = client.post(f"/api/projects/{pid}/runs", headers=po).json()["id"]
    _poll(client, po, run_id)

    def run_count():
        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM runs WHERE project_id = ?", (pid,))
            return cur.fetchone()[0]

    before = run_count()
    for q in _open_critical(pid):
        client.post(f"/api/questions/{q['id']}/answer", headers=po,
                    json={"kind": "answer", "answer_text": "31 March"})
    _poll(client, po, run_id)

    assert run_count() == before, (
        f"answering created {run_count() - before} extra run(s); it must resume the same one"
    )


def test_answering_returns_immediately(client):
    """F3: the answer request must not block on the rest of the pipeline.

    Covers SPEC-12-05.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Fast Answer", "role": "process_owner"}).json()["id"]
    client.post(f"/api/projects/{pid}/documents", headers=po,
                files={"file": ("policy.txt", DOC, "text/plain")})
    run_id = client.post(f"/api/projects/{pid}/runs", headers=po).json()["id"]
    _poll(client, po, run_id)

    criticals = _open_critical(pid)
    assert criticals
    started = time.perf_counter()
    for q in criticals:
        resp = client.post(f"/api/questions/{q['id']}/answer", headers=po,
                           json={"kind": "answer", "answer_text": "31 March"})
        assert resp.status_code == 200
    elapsed = time.perf_counter() - started

    # Generous: with a mock model the whole pipeline is fast, so this asserts the
    # shape (handler returns, work happens after) rather than a wall-clock budget.
    assert elapsed < 10.0, f"answering took {elapsed:.1f}s; it should return at once"


def test_a_second_run_on_an_unchanged_document_adds_no_rows(client):
    """F6: re-running an unchanged document must not duplicate anything.

    Covers SPEC-07-02, SPEC-01-05.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Idempotent", "role": "process_owner"}).json()["id"]
    client.post(f"/api/projects/{pid}/documents", headers=po,
                files={"file": ("policy.txt", DOC, "text/plain")})

    run_id = client.post(f"/api/projects/{pid}/runs", headers=po).json()["id"]
    _poll(client, po, run_id)
    after_first = _counts(pid)
    assert after_first["evidence"] > 0, "the first run extracted nothing"

    # A second and third run over the same unchanged document.
    for _ in range(2):
        again = client.post(f"/api/projects/{pid}/runs", headers=po)
        assert again.status_code == 200, again.text
        _poll(client, po, again.json()["id"])

    after_repeat = _counts(pid)
    assert after_repeat == after_first, (
        f"re-running duplicated rows: {after_first} -> {after_repeat}"
    )


def test_unchanged_sections_cost_no_model_calls_on_a_re_run(client):
    """F6 / brief Phase 0: a re-run must not call the model for unchanged sections.

    Covers SPEC-02-01.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "No Recall", "role": "process_owner"}).json()["id"]
    client.post(f"/api/projects/{pid}/documents", headers=po,
                files={"file": ("policy.txt", DOC, "text/plain")})
    run_id = client.post(f"/api/projects/{pid}/runs", headers=po).json()["id"]
    _poll(client, po, run_id)

    from app.services import llm_service as llm_module
    calls = []
    real = llm_module.llm_service.complete_json
    llm_module.llm_service.complete_json = lambda *a, **k: (calls.append(1), real(*a, **k))[1]
    try:
        again = client.post(f"/api/projects/{pid}/runs", headers=po)
        _poll(client, po, again.json()["id"])
    finally:
        llm_module.llm_service.complete_json = real

    assert calls == [], f"the re-run made {len(calls)} model call(s) for unchanged sections"


def test_fingerprints_are_stable_across_runs(client):
    """F3: the same problem must keep the same fingerprint across runs.

    Covers SPEC-07-02, SPEC-01-05.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Stable FP", "role": "process_owner"}).json()["id"]
    client.post(f"/api/projects/{pid}/documents", headers=po,
                files={"file": ("policy.txt", DOC, "text/plain")})

    run_id = client.post(f"/api/projects/{pid}/runs", headers=po).json()["id"]
    _poll(client, po, run_id)
    first = {q["fingerprint"] for q in db.list_project_clarification_items(pid)}

    again = client.post(f"/api/projects/{pid}/runs", headers=po)
    _poll(client, po, again.json()["id"])
    second = {q["fingerprint"] for q in db.list_project_clarification_items(pid)}

    assert first == second, f"fingerprints changed between runs: {second - first}"
    for fp in first:
        assert "-" not in fp.split("|")[-1] or len(fp.split("|")[-1]) != 36, \
            f"fingerprint still embeds a row UUID: {fp}"


def test_mark_unknown_unblocks_the_run(client):
    """AC-08-04 / brief 7.11 step 4: 'unknown' no longer blocks, but stays flagged.

    Covers SPEC-08-04, SPEC-10-03.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Unknown Path", "role": "process_owner"}).json()["id"]
    client.post(f"/api/projects/{pid}/documents", headers=po,
                files={"file": ("policy.txt", DOC, "text/plain")})
    run_id = client.post(f"/api/projects/{pid}/runs", headers=po).json()["id"]
    _poll(client, po, run_id)

    for q in _open_critical(pid):
        resp = client.post(f"/api/questions/{q['id']}/answer", headers=po,
                           json={"kind": "unknown"})
        assert resp.status_code == 200, resp.text

    assert _open_critical(pid) == []
    run = _poll(client, po, run_id)
    assert run["status"] == "waiting_for_human"
    assert run["current_node"] == "waiting_for_to_be_approval", \
        "marking unknown should let the run move on to the To-Be gate"

    statuses = {q["status"] for q in db.list_project_clarification_items(pid)}
    assert "unknown" in statuses, "the question must stay recorded as unknown"


def test_interrupted_runs_are_reconciled(client):
    """F14: a run left at 'running' by a restart must be failed with a reason.

    Covers SPEC-09-05.
    """
    po, _, user_id = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Restart", "role": "process_owner"}).json()["id"]
    run = db.create_run(pid, started_by=user_id)
    db.update_run_state(run["id"], status="running", current_node="evidence")

    assert db.get_run(run["id"])["status"] == "running"
    reconciled = db.reconcile_interrupted_runs()
    assert reconciled >= 1

    after = db.get_run(run["id"])
    assert after["status"] == "failed"
    assert "restarted" in (after["last_error"] or "").lower()
