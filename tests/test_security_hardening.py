"""Security and safe-read tests.

Covers SPEC-14-03, SPEC-14-06, AC-14-03, AC-14-04, AC-11-04 and brief 8.4.
Findings addressed: F7 (hardcoded default signing key), F8 (a GET that wrote and
discarded an approval), and the F14 items: open CORS, a fail-open permission
matrix, an unbounded user cache, an unlocked audit chain, invented rule-evidence
links and the missing invitation resend endpoint.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import (
    RETIRED_DEFAULT_SECRET_KEY,
    settings,
    validate_security_configuration,
)
from app.main import app, _allowed_origins
from app.repositories.database import db
from app.services.permissions import (
    _USER_CACHE_MAX,
    _USER_CACHE_TTL,
    _user_cache,
    check_permission,
    require_project_member,
)

DOC = b"""1. ELIGIBILITY
Applications must be submitted before 31 March of each year.
The scholarship clerk verifies the income certificate.
"""


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _register(client, name="user"):
    email = f"{name}_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass123!"
    resp = client.post("/api/auth/register", json={
        "display_name": f"{name.title()} Person", "email": email,
        "password": password, "repeat_password": password,
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, email, body["user"]["id"]


# ---------------------------------------------------------------------------
# F7: the signing key
# ---------------------------------------------------------------------------
def test_there_is_no_hardcoded_default_secret_key():
    """F7: config.py must not ship a usable signing key."""
    source = open("app/core/config.py", encoding="utf-8").read()
    # The retired value may appear once, as the constant that is refused.
    assert source.count(RETIRED_DEFAULT_SECRET_KEY) == 1
    assert 'secret_key: str = ""' in source, "secret_key must default to empty, not to a key"


def test_startup_refuses_an_unset_secret_key(monkeypatch):
    """F7: no key means no start, rather than a silently forgeable one."""
    monkeypatch.setattr(settings, "secret_key", "")
    with pytest.raises(RuntimeError, match="SECRET_KEY is not set"):
        validate_security_configuration()


def test_startup_refuses_the_retired_default_secret_key(monkeypatch):
    """F7: the published default must be refused explicitly."""
    monkeypatch.setattr(settings, "secret_key", RETIRED_DEFAULT_SECRET_KEY)
    with pytest.raises(RuntimeError, match="old\\s+hardcoded default"):
        validate_security_configuration()


def test_startup_refuses_a_short_secret_key(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "tooshort")
    with pytest.raises(RuntimeError, match="too short"):
        validate_security_configuration()


def test_a_real_secret_key_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "a-perfectly-ordinary-32-character-key")
    validate_security_configuration()


# ---------------------------------------------------------------------------
# F14: CORS
# ---------------------------------------------------------------------------
def test_cors_is_not_open_to_every_origin():
    """F14: allow_origins=["*"] with credentials let any site call this API."""
    origins = _allowed_origins()
    assert "*" not in origins
    assert origins, "at least the app's own front end must be allowed"
    assert all(o.startswith("http") for o in origins)


def test_cors_allows_the_configured_front_end(monkeypatch):
    monkeypatch.setattr(settings, "app_base_url", "https://processfoundry.example.edu")
    assert _allowed_origins() == ["https://processfoundry.example.edu"]


# ---------------------------------------------------------------------------
# F14: the permission matrix fails closed
# ---------------------------------------------------------------------------
def test_an_unknown_action_is_denied_for_every_role():
    """F14: the matrix ended in a bare `return`, allowing anything unlisted.

    Covers SPEC-14-06.
    """
    from fastapi import HTTPException
    for role in ("process_owner", "analyst", "technical_reviewer"):
        with pytest.raises(HTTPException) as exc:
            check_permission("delete_entire_project", role)
        assert exc.value.status_code == 403


def test_an_unclassified_artifact_type_cannot_be_approved():
    """F14: approve_artifact with an unknown type was allowed for every role.

    Covers SPEC-14-06.
    """
    from fastapi import HTTPException
    for role in ("process_owner", "analyst", "technical_reviewer"):
        with pytest.raises(HTTPException) as exc:
            check_permission("approve_artifact", role, artifact_type="some_new_document")
        assert exc.value.status_code == 403
        assert "no approval rule" in exc.value.detail


def test_approve_artifact_with_no_type_is_denied():
    """Covers SPEC-14-06."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        check_permission("approve_artifact", "process_owner", artifact_type=None)


def test_every_generated_artifact_type_is_classified():
    """The fail-closed rule must not block the documents the app really makes.

    Covers SPEC-14-06.
    """
    from app.services.permissions import BUSINESS_ARTIFACTS, TECHNICAL_ARTIFACTS
    generated = {
        "brd", "prd", "frd", "srs", "hld", "data_model", "test_plan",
        "uat_pack", "traceability_matrix", "rules_catalogue", "roles_matrix",
        "workflow_json",
    }
    unclassified = generated - BUSINESS_ARTIFACTS - TECHNICAL_ARTIFACTS
    assert unclassified == set(), f"these generated types cannot be approved: {unclassified}"


def test_the_permission_matrix_still_enforces_the_brief(client):
    """AC-14-03 / AC-14-04: the roles from brief 7.9 are unchanged.

    Covers SPEC-14-06, SPEC-00-04.
    """
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        check_permission("approve_business_rule", "analyst")
    with pytest.raises(HTTPException):
        check_permission("approve_artifact", "analyst", artifact_type="brd")
    with pytest.raises(HTTPException):
        check_permission("approve_artifact", "process_owner", artifact_type="test_plan")
    check_permission("approve_artifact", "process_owner", artifact_type="brd")
    check_permission("approve_artifact", "technical_reviewer", artifact_type="test_plan")
    check_permission("view", "technical_reviewer")


# ---------------------------------------------------------------------------
# F14: the user cache is bounded, and membership is never cached
# ---------------------------------------------------------------------------
def test_the_user_cache_is_bounded_and_short_lived():
    """F14: the cache was TTL-only and never evicted."""
    assert _USER_CACHE_MAX <= 1024
    assert _USER_CACHE_TTL <= 60.0


def test_the_user_cache_evicts_the_oldest_entry(client):
    """F14: more distinct users than the cap must not grow memory without limit."""
    from app.services.permissions import cache_user
    _user_cache.clear()
    for i in range(_USER_CACHE_MAX + 25):
        cache_user({"id": f"user-{i}", "email": f"u{i}@example.com"})
    assert len(_user_cache) == _USER_CACHE_MAX
    assert "user-0" not in _user_cache, "the oldest entry should have been evicted"
    assert f"user-{_USER_CACHE_MAX + 24}" in _user_cache


def test_membership_and_role_are_read_fresh_on_every_request(client):
    """SPEC-14-03: a removed member loses access on the very next request."""
    po, _, _ = _register(client, "owner")
    analyst, analyst_email, analyst_id = _register(client, "analyst")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Fresh Role", "role": "process_owner"}).json()["id"]
    inv = client.post(f"/api/projects/{pid}/invitations", headers=po,
                      json={"email": analyst_email, "role": "analyst"}).json()
    client.post(f"/api/invitations/{inv['id']}/accept", headers=analyst)

    assert client.get(f"/api/projects/{pid}", headers=analyst).status_code == 200
    assert client.delete(f"/api/projects/{pid}/members/{analyst_id}", headers=po).status_code == 200
    # No sleep: the cache holds only the user row, never the membership.
    assert client.get(f"/api/projects/{pid}", headers=analyst).status_code == 404
    assert client.post(f"/api/projects/{pid}/documents", headers=analyst,
                       files={"file": ("x.txt", DOC, "text/plain")}).status_code == 404


def test_a_role_change_takes_effect_immediately(client):
    """SPEC-14-03: the role comes from project_members on every request."""
    po, _, po_id = _register(client, "owner")
    other, other_email, other_id = _register(client, "member")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Role Change", "role": "process_owner"}).json()["id"]
    inv = client.post(f"/api/projects/{pid}/invitations", headers=po,
                      json={"email": other_email, "role": "technical_reviewer"}).json()
    client.post(f"/api/invitations/{inv['id']}/accept", headers=other)

    # A Technical Reviewer may not upload.
    assert client.post(f"/api/projects/{pid}/documents", headers=other,
                       files={"file": ("a.txt", DOC, "text/plain")}).status_code == 403
    assert require_project_member(pid, {"id": other_id}) == "technical_reviewer"

    # Change the role directly; the next request must see it.
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE project_members SET role = 'analyst' WHERE project_id = ? AND user_id = ?",
                    (pid, other_id))
        conn.commit()

    assert require_project_member(pid, {"id": other_id}) == "analyst"
    assert client.post(f"/api/projects/{pid}/documents", headers=other,
                       files={"file": ("a.txt", DOC, "text/plain")}).status_code == 201


# ---------------------------------------------------------------------------
# F8: reads must not write, and must never discard an approval
# ---------------------------------------------------------------------------
def test_the_traceability_get_writes_nothing(client):
    """F8: this GET used to write three artifacts on every page view.

    Covers SPEC-11-05.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Read Only", "role": "process_owner"}).json()["id"]
    client.post(f"/api/projects/{pid}/documents", headers=po,
                files={"file": ("sop.txt", DOC, "text/plain")})

    before = len(db.list_project_artifacts(pid))
    for _ in range(3):
        resp = client.get(f"/api/projects/{pid}/traceability", headers=po)
        assert resp.status_code == 200, resp.text
    assert len(db.list_project_artifacts(pid)) == before, \
        "a read-only endpoint created or replaced artifacts"


def test_regenerating_does_not_discard_an_approval(client):
    """F8: save_artifact reset `status` to draft, throwing the approval away.

    Covers SPEC-01-04, SPEC-00-03.
    """
    po, _, po_id = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Keep Approval", "role": "process_owner"}).json()["id"]

    art = db.save_artifact(pid, "brd", "# BRD v1", content_json={}, status="draft")
    db.update_artifact_status(art["id"], "approved", approved_by=po_id)
    approved = db.get_artifact(art["id"])
    assert approved["status"] == "approved"
    approved_version = approved["version"]

    # Regenerate, exactly as a later run would.
    regenerated = db.save_artifact(pid, "brd", "# BRD regenerated", content_json={}, status="draft")

    still_approved = db.get_artifact(art["id"])
    assert still_approved["status"] == "approved", "the approval was silently discarded"
    assert still_approved["approved_by"] == po_id
    assert still_approved["markdown"] == "# BRD v1", "the approved content was overwritten"
    assert regenerated["version"] == approved_version + 1, \
        "regeneration should create the next version, not overwrite"


def test_an_unapproved_draft_is_still_updated_in_place(client):
    """Repeated generation inside one run should not pile up versions.

    Covers SPEC-01-04.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Draft Update", "role": "process_owner"}).json()["id"]
    first = db.save_artifact(pid, "frd", "# FRD a", content_json={}, status="draft")
    second = db.save_artifact(pid, "frd", "# FRD b", content_json={}, status="draft")
    assert first["version"] == second["version"] == 1
    assert db.get_artifact_by_type(pid, "frd")["markdown"] == "# FRD b"


def test_ai_can_never_set_approved(client):
    """AC-00-02 / brief 8.3 rule 3: approval requires a named human.

    Covers SPEC-01-04, SPEC-00-02, SPEC-00-03.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "No Self Approval", "role": "process_owner"}).json()["id"]
    art = db.save_artifact(pid, "prd", "# PRD", content_json={}, status="draft")
    with pytest.raises(ValueError, match="approved_by"):
        db.update_artifact_status(art["id"], "approved", approved_by=None)


# ---------------------------------------------------------------------------
# brief 8.4: the audit chain
# ---------------------------------------------------------------------------
def test_the_audit_chain_locks_the_previous_event_on_postgres():
    """Brief 8.4: "Insert inside a transaction that locks the project's latest event".

    Covers SPEC-01-01.
    """
    source = open("app/repositories/database.py", encoding="utf-8").read()
    assert "FOR UPDATE" in source, "the audit chain read takes no row lock"
    chain_fn = source[source.index("def _log_audit_event_tx"):]
    chain_fn = chain_fn[: chain_fn.index("def log_audit_event")]
    assert "FOR UPDATE" in chain_fn, "the lock is not in the audit chain insert"


def test_the_audit_chain_is_continuous(client):
    """Brief 8.3 rule 8: each event links to the previous one by hash.

    Covers SPEC-01-01.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Audit Chain", "role": "process_owner"}).json()["id"]
    client.post(f"/api/projects/{pid}/documents", headers=po,
                files={"file": ("sop.txt", DOC, "text/plain")})

    events = client.get(f"/api/projects/{pid}/audit", headers=po).json()
    assert len(events) >= 2
    ordered = sorted(events, key=lambda e: e["id"])
    assert ordered[0]["prev_hash"] == "0" * 64
    for earlier, later in zip(ordered, ordered[1:]):
        assert later["prev_hash"] == earlier["hash"], "the hash chain is broken"


# ---------------------------------------------------------------------------
# F14: rules are never linked to unrelated evidence
# ---------------------------------------------------------------------------
def test_rules_are_never_linked_to_unrelated_evidence():
    """F14: an unmatched quote fell back to sec_evidence[0], asserting false support.

    Covers SPEC-06-04, SPEC-04-02.
    """
    import re
    source = open("app/agents/rules.py", encoding="utf-8").read()
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert not re.search(r"matched_eids\.append\(sec_evidence\[0\]", code), \
        "a rule can still be attached to whichever evidence item happens to be first"
    assert "_raise_unlinked_rule_question" in code, \
        "an ungrounded rule should raise a question for the Analyst"


# ---------------------------------------------------------------------------
# brief 7.4: invitation resend
# ---------------------------------------------------------------------------
def test_invitation_can_be_resent_within_the_limit(client):
    """Brief 7.4 / 5.2a: the resend endpoint exists, capped at 5 per invitation.

    Covers SPEC-12-07, SPEC-14-04.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Resend", "role": "process_owner"}).json()["id"]
    inv = client.post(f"/api/projects/{pid}/invitations", headers=po,
                      json={"email": "invitee@example.com", "role": "analyst"}).json()

    for expected in range(1, 6):
        resp = client.post(f"/api/invitations/{inv['id']}/resend", headers=po)
        assert resp.status_code == 200, resp.text
        assert resp.json()["resend_count"] == expected

    sixth = client.post(f"/api/invitations/{inv['id']}/resend", headers=po)
    assert sixth.status_code == 429
    assert "limit of 5" in sixth.json()["detail"]


def test_only_someone_who_may_invite_can_resend(client):
    """Brief 7.9: resending is an invitation action, not a viewing one.

    Covers SPEC-14-06.
    """
    po, _, _ = _register(client, "owner")
    tr, tr_email, _ = _register(client, "techrev")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Resend Perm", "role": "process_owner"}).json()["id"]
    tr_inv = client.post(f"/api/projects/{pid}/invitations", headers=po,
                         json={"email": tr_email, "role": "technical_reviewer"}).json()
    client.post(f"/api/invitations/{tr_inv['id']}/accept", headers=tr)

    other = client.post(f"/api/projects/{pid}/invitations", headers=po,
                        json={"email": "someone@example.com", "role": "analyst"}).json()
    assert client.post(f"/api/invitations/{other['id']}/resend", headers=tr).status_code == 403


def test_the_daily_invitation_cap_is_enforced(client):
    """Brief 7.4: at most 20 invitations per project per day.

    Covers SPEC-14-04.
    """
    po, _, _ = _register(client, "owner")
    pid = client.post("/api/projects", headers=po,
                      json={"name": "Daily Cap", "role": "process_owner"}).json()["id"]
    for i in range(20):
        resp = client.post(f"/api/projects/{pid}/invitations", headers=po,
                           json={"email": f"p{i}@example.com", "role": "analyst"})
        assert resp.status_code == 200, resp.text

    blocked = client.post(f"/api/projects/{pid}/invitations", headers=po,
                          json={"email": "one-too-many@example.com", "role": "analyst"})
    assert blocked.status_code == 429
    assert "daily limit" in blocked.json()["detail"]


def test_invitation_email_failures_are_logged_without_the_password(caplog, client):
    """Brief 7.4: "Log the error without the password"."""
    import logging
    from app.api import team as team_api

    with caplog.at_level(logging.WARNING, logger="processfoundry.api.team"):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(settings, "smtp_host", "smtp.invalid.example")
            mp.setattr(settings, "smtp_password", "super-secret-app-password")
            sent = team_api.send_invitation_email("Owner", "Project", "analyst", "x@example.com")

    assert sent is False
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "could not be sent" in logged
    assert "super-secret-app-password" not in logged


def test_streamlit_xsrf_protection_is_enabled():
    """F14: XSRF protection had been switched off with no reason given."""
    config = open(".streamlit/config.toml", encoding="utf-8").read()
    assert "enableXsrfProtection = true" in config
