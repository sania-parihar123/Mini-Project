"""End-to-end HTTP tests for the clarification question endpoints.

Covers AC-07-01, AC-07-02 (SPEC-07-01..05) and brief 7.12.
Finding F1 of REVIEW_REPORT.md: `GET /api/projects/{id}/questions` and
`GET /api/me/questions` returned HTTP 500 as soon as one `ambiguous_term`
question existed, because the repository put bare id strings into
`linked_evidence` while the response model declared `List[Dict]`. The UI then
turned the 500 into an empty list, so the Process Owner saw "no questions".
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.database import db

# Deliberately contains all three triggers: two different dates (conflict),
# a sentence with no actor, and the vague term "eligible".
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


def _signed_in(client, role="process_owner"):
    email = f"q_{uuid.uuid4().hex[:8]}@example.com"
    password = "QuestionPass123!"
    reg = client.post("/api/auth/register", json={
        "display_name": "Question Tester",
        "email": email,
        "password": password,
        "repeat_password": password,
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}, email


def _project_with_questions(client, headers, name="Question Flow"):
    pid = client.post("/api/projects", headers=headers,
                      json={"name": name, "role": "process_owner"}).json()["id"]
    up = client.post(f"/api/projects/{pid}/documents", headers=headers,
                     files={"file": ("policy.txt", DOC, "text/plain")})
    assert up.status_code == 201, up.text
    run = client.post(f"/api/projects/{pid}/runs", headers=headers)
    assert run.status_code == 200, run.text
    return pid


def test_an_ambiguous_term_question_is_created(client):
    """AC-07-01: the vague term in the fixture must produce an ambiguous_term question.

    This is the precondition that used to break both list endpoints.

    Covers SPEC-07-01.
    """
    headers, _ = _signed_in(client)
    pid = _project_with_questions(client, headers)
    kinds = {q["kind"] for q in db.list_project_clarification_items(pid)}
    assert "ambiguous_term" in kinds, f"no ambiguous_term question was created: {kinds}"


def test_list_project_questions_returns_200_with_evidence_linked_questions(client):
    """AC-07-01 / F1: the project question list must be HTTP 200, not 500.

    Covers SPEC-12-05, SPEC-07-03.
    """
    headers, _ = _signed_in(client)
    pid = _project_with_questions(client, headers)

    resp = client.get(f"/api/projects/{pid}/questions", headers=headers)
    assert resp.status_code == 200, resp.text
    questions = resp.json()
    assert questions, "the endpoint returned no questions"

    ambiguous = [q for q in questions if q["kind"] == "ambiguous_term"]
    assert ambiguous, "the ambiguous_term question is missing from the response"
    sources = ambiguous[0]["linked_evidence"]
    assert sources, "an ambiguous_term question must carry its source evidence"
    assert isinstance(sources[0], dict), "linked_evidence entries must be objects, not ids"
    assert sources[0]["quote"], "the source block must carry the exact quote"


def test_waiting_for_me_returns_200_with_evidence_linked_questions(client):
    """AC-07-02 / F1: the "Waiting for me" inbox must be HTTP 200, not 500.

    Covers SPEC-12-05, SPEC-07-05.
    """
    headers, _ = _signed_in(client)
    _project_with_questions(client, headers)

    resp = client.get("/api/me/questions", headers=headers)
    assert resp.status_code == 200, resp.text
    inbox = resp.json()
    assert inbox, "the inbox returned nothing while critical questions are open"
    assert all(isinstance(q["linked_evidence"], list) for q in inbox)
    with_sources = [q for q in inbox if q["linked_evidence"]]
    assert with_sources, "no inbox question carried a source block"
    assert with_sources[0]["linked_evidence"][0]["quote"]


def test_the_evidence_quote_is_findable_in_the_response(client):
    """AC-04-02 / F1: a verbatim sentence from the document must reach the client.

    Covers SPEC-07-03, SPEC-04-02.
    """
    headers, _ = _signed_in(client)
    pid = _project_with_questions(client, headers)

    resp = client.get(f"/api/projects/{pid}/questions", headers=headers)
    assert resp.status_code == 200, resp.text
    all_quotes = " ".join(
        src["quote"] or ""
        for q in resp.json()
        for src in q["linked_evidence"]
    )
    assert "Eligible students receive a confirmation notice" in all_quotes


def test_every_question_carries_the_context_brief_7_12_requires(client):
    """Brief 7.12 / F12: project name, key, reason, consequence and a source block.

    Covers SPEC-07-03, SPEC-07-04.
    """
    headers, _ = _signed_in(client)
    pid = _project_with_questions(client, headers, name="Context Check")

    questions = client.get(f"/api/projects/{pid}/questions", headers=headers).json()
    assert questions

    for q in questions:
        assert q["project_name"] == "Context Check", "item 1: the project name"
        assert q["question_key"].startswith("Q-"), "item 1: the question key"
        assert q["question"], "item 2: a plain question"
        assert q["reason"], "item 3: why it matters"
        assert q["consequence_summary"], "item 6: what happens after the answer"
        # Item 5: the AI suggestion is optional, but when present it must be labelled.
        if q["ai_suggestion"]:
            assert q["ai_suggestion"].startswith("AI suggestion, not a fact"), \
                "an AI suggestion must be labelled as one"

    # Item 4: every kind must be answerable without opening the document.
    for kind in ("conflicting_rules", "missing_actor", "ambiguous_term"):
        of_kind = [q for q in questions if q["kind"] == kind]
        if not of_kind:
            continue
        sources = of_kind[0]["linked_evidence"]
        assert sources, f"a {kind} question carried no source block"
        src = sources[0]
        assert src["quote"], f"{kind}: exact quote"
        assert src["document_name"], f"{kind}: document file name"
        assert src["section_title"], f"{kind}: section title"
        assert src["section_index"] is not None, f"{kind}: section number"


def test_conflicting_rules_question_shows_both_passages_with_letters(client):
    """Brief 7.12 items 4 and 5: one lettered option per conflicting passage.

    Covers SPEC-07-04, SPEC-07-03.
    """
    headers, _ = _signed_in(client)
    pid = _project_with_questions(client, headers)

    questions = client.get(f"/api/projects/{pid}/questions", headers=headers).json()
    conflicts = [q for q in questions if q["kind"] == "conflicting_rules"]
    assert conflicts, "the planted date conflict was not detected"

    options = conflicts[0]["options"]
    lettered = [o for o in options if o.get("letter")]
    assert len(lettered) >= 2, "a conflict needs one lettered option per source"
    assert {o["letter"] for o in lettered} >= {"A", "B"}
    for opt in lettered:
        assert opt["quote"], "each option must carry its verbatim quote"
        assert opt["document_name"], "each option must name its document"
    assert any("Another" in o["label"] for o in options), "the 'Other' choice is required"
    assert conflicts[0]["consequence_summary"]
    assert "superseded" in conflicts[0]["consequence_summary"]


def test_conflict_question_wording_is_not_process_specific(client):
    """Appendix rule 4 / F10: templates must not assert a process-specific subject.

    Covers SPEC-00-01.
    """
    headers, _ = _signed_in(client)
    pid = _project_with_questions(client, headers)

    questions = client.get(f"/api/projects/{pid}/questions", headers=headers).json()
    for q in [x for x in questions if x["kind"] == "conflicting_rules"]:
        assert "submission deadline" not in q["question"].lower(), \
            "the question asserts a subject the source may not support"


def test_question_list_costs_one_query_regardless_of_question_count(client):
    """F1/N+1: 1 + 2-per-question became a single JOINed query.

    Covers SPEC-01-01.
    """
    headers, _ = _signed_in(client)
    pid = _project_with_questions(client, headers)

    queries = []
    real_get_connection = db.get_connection

    class CountingCursor:
        def __init__(self, cur):
            self._cur = cur

        def execute(self, sql, params=None):
            queries.append(sql)
            return self._cur.execute(sql, params) if params is not None else self._cur.execute(sql)

        def __getattr__(self, name):
            return getattr(self._cur, name)

    class CountingConnection:
        def __init__(self, conn):
            self._conn = conn

        def cursor(self, *a, **k):
            return CountingCursor(self._conn.cursor(*a, **k))

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def __enter__(self):
            self._conn.__enter__()
            return self

        def __exit__(self, *a):
            return self._conn.__exit__(*a)

    db.get_connection = lambda: CountingConnection(real_get_connection())
    try:
        items = db.list_project_clarification_items(pid)
    finally:
        db.get_connection = real_get_connection

    assert len(items) >= 3, f"expected several questions, got {len(items)}"
    assert len(queries) == 1, (
        f"{len(items)} questions cost {len(queries)} queries; expected exactly 1. "
        f"Queries: {queries}"
    )
