"""Every planted defect in both fixtures must be found, and nothing invented.

Covers AC-15-01 (SPEC-15-01, SPEC-15-02) and brief 9.1: "the planted problems
are found and not silently fixed; no extra problems are invented; exact quotes
are reproducible; and the same code ran with no process-specific branch".

Finding F10 of REVIEW_REPORT.md: only 3 of the 5 planted defect classes were
detected. There was no `missing_info` detector, no duplicate-step detector and
no missing-piece detector, conflict detection worked on dates only and asserted
"submission deadline", and the pairwise sweep invented conflicts between
unrelated numbers.
"""
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.database import db

FIXTURES = Path(__file__).parent / "fixtures"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["fixtures"]


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _analyse(client, fixture_file, project_name):
    """Upload one fixture and run the real pipeline over HTTP."""
    email = f"fx_{uuid.uuid4().hex[:8]}@example.com"
    password = "FixturePass123!"
    reg = client.post("/api/auth/register", json={
        "display_name": "Fixture Tester", "email": email,
        "password": password, "repeat_password": password,
    })
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    pid = client.post("/api/projects", headers=headers,
                      json={"name": project_name, "role": "process_owner"}).json()["id"]
    content = (FIXTURES / fixture_file).read_bytes()
    up = client.post(f"/api/projects/{pid}/documents", headers=headers,
                     files={"file": (fixture_file, content, "text/plain")})
    assert up.status_code == 201, up.text
    run = client.post(f"/api/projects/{pid}/runs", headers=headers)
    assert run.status_code == 200, run.text

    listed = client.get(f"/api/projects/{pid}/questions", headers=headers)
    assert listed.status_code == 200, listed.text
    return headers, pid, listed.json(), content.decode()


ALL_FIXTURES = [(key, data["file"]) for key, data in MANIFEST.items()]


@pytest.mark.parametrize("fixture_key,fixture_file", ALL_FIXTURES)
def test_planted_conflicting_values_are_found(client, fixture_key, fixture_file):
    """AC-15-01 defect 1: the two different values for the same thing.

    Covers SPEC-06-02, SPEC-06-03, SPEC-07-01.
    """
    planted = MANIFEST[fixture_key]["planted_defects"]["conflicting_values"]
    _, _, questions, _ = _analyse(client, fixture_file, f"Conflict {fixture_key}")

    conflicts = [q for q in questions if q["kind"] == "conflicting_rules"]
    assert conflicts, "the planted conflict was not detected"

    text = " ".join(q["question"] + " " + " ".join(o["label"] for o in q["options"])
                    for q in conflicts)
    assert planted["value_a"] in text, f"{planted['value_a']} missing from the question"
    assert planted["value_b"] in text, f"{planted['value_b']} missing from the question"


@pytest.mark.parametrize("fixture_key,fixture_file", ALL_FIXTURES)
def test_planted_unnamed_actor_is_found(client, fixture_key, fixture_file):
    """AC-15-01 defect 2 / AC-05-01: the step whose sentence names no actor.

    Covers SPEC-05-02, SPEC-07-01.
    """
    _, pid, questions, _ = _analyse(client, fixture_file, f"Actor {fixture_key}")

    actor_qs = [q for q in questions if q["kind"] == "missing_actor"]
    assert actor_qs, "the step with no named actor was not flagged"

    # And the actor must still be NULL in the stored model: never guessed.
    pv = db.get_latest_process_version(pid)
    steps = db.list_process_steps(pv["id"])
    unnamed = [s for s in steps if s["actor"] is None]
    assert unnamed, "no step was left with actor = NULL"
    assert any("actor not stated" in (s.get("unknowns") or []) for s in unnamed)


@pytest.mark.parametrize("fixture_key,fixture_file", ALL_FIXTURES)
def test_planted_vague_term_is_found(client, fixture_key, fixture_file):
    """AC-15-01 defect 3: the vague term.

    Covers SPEC-07-01.
    """
    planted = MANIFEST[fixture_key]["planted_defects"]["vague_term"]["term"]
    _, _, questions, _ = _analyse(client, fixture_file, f"Vague {fixture_key}")

    vague_qs = [q for q in questions if q["kind"] == "ambiguous_term"]
    assert vague_qs, "the vague term was not flagged"
    # The manifest records "eligible students"; the detector flags the word.
    head = planted.split()[0].lower()
    assert any(head in q["question"].lower() for q in vague_qs), \
        f"no question mentions '{head}'"


@pytest.mark.parametrize("fixture_key,fixture_file", ALL_FIXTURES)
def test_planted_repeated_step_is_found(client, fixture_key, fixture_file):
    """AC-15-01 defect 4 / F10: the repeated step, with the "Repeats step N" note.

    Covers SPEC-07-01.
    """
    _, _, questions, _ = _analyse(client, fixture_file, f"Repeat {fixture_key}")

    dupes = [q for q in questions if q["kind"] == "duplicate_step"]
    assert dupes, "the repeated step was not detected"
    joined = " ".join(q["question"] + " " + (q["reason"] or "") for q in dupes)
    assert "Repeats step" in joined, "brief 10.5 asks for a 'Repeats step N' note"


@pytest.mark.parametrize("fixture_key,fixture_file", ALL_FIXTURES)
def test_planted_missing_piece_is_found(client, fixture_key, fixture_file):
    """AC-15-01 defect 5 / F10: the missing appeal or notification path.

    Covers SPEC-07-01.
    """
    planted = MANIFEST[fixture_key]["planted_defects"]["missing_piece"].lower()
    _, _, questions, _ = _analyse(client, fixture_file, f"Missing {fixture_key}")

    missing = [q for q in questions if q["kind"] == "missing_info"]
    assert missing, "no missing_info question was raised at all"

    joined = " ".join(q["question"] + " " + (q["reason"] or "") for q in missing).lower()
    # Both fixtures plant a missing appeal path.
    if "appeal" in planted:
        assert "appeal" in joined, (
            f"the planted missing piece ({planted!r}) was not reported"
        )


@pytest.mark.parametrize("fixture_key,fixture_file", ALL_FIXTURES)
def test_clear_facts_are_not_flagged(client, fixture_key, fixture_file):
    """Brief 9.1: facts stated once and clearly must NOT be flagged.

    Covers SPEC-06-03.
    """
    clear_facts = MANIFEST[fixture_key]["clear_facts"]
    _, _, questions, _ = _analyse(client, fixture_file, f"Clear {fixture_key}")

    conflicts = [q for q in questions if q["kind"] == "conflicting_rules"]
    for fact in clear_facts:
        # A value stated once cannot be the subject of a disagreement.
        for q in conflicts:
            labels = [str(o.get("label", "")).lower() for o in q["options"]]
            assert fact.lower() not in labels, (
                f"the clear fact {fact!r} was raised as a conflict"
            )


@pytest.mark.parametrize("fixture_key,fixture_file", ALL_FIXTURES)
def test_no_extra_conflicts_are_invented(client, fixture_key, fixture_file):
    """Brief 9.1 / F10: the question count must not grow with the square of the rules.

    Each fixture plants exactly one conflicting pair. The old pairwise sweep
    produced a question for every differing pair of date-bearing rules.

    Covers SPEC-07-02.
    """
    _, pid, questions, _ = _analyse(client, fixture_file, f"NoExtra {fixture_key}")

    conflicts = [q for q in questions if q["kind"] == "conflicting_rules"]
    rules = db.list_project_business_rules(pid)
    assert len(conflicts) <= 2, (
        f"{len(rules)} rules produced {len(conflicts)} conflict questions; "
        "one planted conflict should produce about one question"
    )
    # No duplicate questions of any kind.
    fingerprints = [q["fingerprint"] for q in questions]
    assert len(fingerprints) == len(set(fingerprints)), "duplicate fingerprints"


@pytest.mark.parametrize("fixture_key,fixture_file", ALL_FIXTURES)
def test_quotes_are_reproducible_from_the_source(client, fixture_key, fixture_file):
    """Brief 9.1 / SPEC-04-02: every stored quote is verbatim in the document."""
    _, pid, questions, source_text = _analyse(client, fixture_file, f"Quotes {fixture_key}")

    evidence = db.list_project_evidence(pid)
    assert evidence, "no evidence was extracted"
    for ev in evidence:
        assert ev["quote"] in source_text, f"quote not verbatim: {ev['quote']!r}"

    for q in questions:
        for src in q["linked_evidence"]:
            if src.get("quote"):
                assert src["quote"] in source_text, \
                    f"a question shows a quote that is not in the document: {src['quote']!r}"


def test_the_same_code_handles_both_processes_with_no_branch():
    """AC-00-01 / Appendix rule 4: no fixture-specific or process-specific logic.

    Covers SPEC-00-01.
    """
    import re
    banned = (
        "scholarship", "hostel", "admission", "revaluation", "merit",
        "stipend", "warden", "caretaker",
    )
    for path in ("app/agents/gaps.py", "app/agents/rules.py", "app/agents/discovery.py",
                 "app/agents/evidence.py", "app/services/document_parser.py"):
        source = open(path, encoding="utf-8").read()
        code = "\n".join(
            line for line in source.splitlines()
            if not line.lstrip().startswith("#")
        )
        code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
        for word in banned:
            assert word not in code.lower(), (
                f"{path} mentions '{word}': process-specific logic is forbidden "
                "outside tests/fixtures/"
            )


@pytest.mark.parametrize("fixture_key,fixture_file", ALL_FIXTURES)
def test_every_planted_defect_class_is_covered(client, fixture_key, fixture_file):
    """AC-15-01: all five planted classes produce a question on the same run.

    Covers SPEC-15-01, SPEC-15-02, SPEC-07-01.
    """
    _, _, questions, _ = _analyse(client, fixture_file, f"All {fixture_key}")
    kinds = {q["kind"] for q in questions}

    expected = {
        "conflicting_rules": "two different values for the same thing",
        "missing_actor": "a step with no named actor",
        "ambiguous_term": "a vague term",
        "duplicate_step": "a repeated step",
        "missing_info": "a missing piece (no appeal path)",
    }
    missing = {k: why for k, why in expected.items() if k not in kinds}
    assert not missing, f"not detected for {fixture_key}: {missing}"
