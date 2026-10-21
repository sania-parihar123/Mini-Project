"""Tests for FastAPI backend REST endpoints using TestClient (SPEC-01 to SPEC-13)."""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.repositories.database import db

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_api.db")
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    db._init_sqlite()

def test_health_check_endpoint():
    """Verify system health endpoint returns 200 OK.

    Covers SPEC-12-01.
    """
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "ProcessFoundry AI"

def test_auth_and_project_lifecycle_e2e():
    """End-to-end test of register, login, project creation, document upload, and audit logging.

    Covers SPEC-12-01, SPEC-12-02, SPEC-12-03, SPEC-12-04, SPEC-14-01, SPEC-14-03.
    """
    client = TestClient(app)

    # 1. Register new user
    reg_payload = {
        "display_name": "Dean Winchester",
        "email": "dean@processfoundry.ai",
        "password": "Password123!",
        "repeat_password": "Password123!"
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    auth_data = reg_res.json()
    token = auth_data["access_token"]
    assert token is not None
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Login
    login_res = client.post("/api/auth/login", json={
        "email": "dean@processfoundry.ai",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    assert login_res.json()["access_token"] is not None

    # 3. Create Project
    proj_payload = {
        "name": "Fee Waiver Workflow",
        "role": "process_owner",
        "process_type": "finance",
        "description": "Streamlining fee waiver evaluations.",
        "department": "Finance",
        "goals": "Cut turnaround to 2 days.",
        "constraints": "Strict verification of income certificates."
    }
    proj_res = client.post("/api/projects", json=proj_payload, headers=headers)
    assert proj_res.status_code == 201
    project = proj_res.json()
    pid = project["id"]
    assert project["name"] == "Fee Waiver Workflow"
    assert project["my_role"] == "process_owner"

    # 4. List Projects
    list_res = client.get("/api/projects", headers=headers)
    assert list_res.status_code == 200
    projects = list_res.json()
    assert len(projects) == 1
    assert projects[0]["id"] == pid

    # 5. Upload Document
    doc_content = b"""# FEE WAIVER SOP
1. SUBMISSION
Student submits fee waiver form along with family income certificate.

2. VERIFICATION
Financial aid officer verifies the certificate within 3 working days.
"""
    files = {"file": ("fee_waiver_sop.txt", io.BytesIO(doc_content), "text/plain")}
    upload_res = client.post(f"/api/projects/{pid}/documents", files=files, headers=headers)
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["filename"] == "fee_waiver_sop.txt"
    assert doc_data["parse_status"] == "parsed"

    # 6. Trigger Run
    run_res = client.post(f"/api/projects/{pid}/runs", headers=headers)
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["id"] is not None
    assert run_data["status"] in ("completed", "waiting_for_human", "running")

    # 7. Check Audit Events
    audit_res = client.get(f"/api/projects/{pid}/audit", headers=headers)
    assert audit_res.status_code == 200
    events = audit_res.json()
    assert len(events) >= 1
    event_types = [e["event_type"] for e in events]
    assert "document_uploaded" in event_types


def test_team_invitation_revocation_and_member_removal():
    """Verify team invitation lifecycle: create, revoke, accept, and member removal.

    Covers SPEC-12-07, SPEC-14-04, SPEC-14-05.
    """
    client = TestClient(app)

    # 1. Register project owner
    owner_res = client.post("/api/auth/register", json={
        "display_name": "Dean Winchester",
        "email": "dean_team@processfoundry.ai",
        "password": "Password123!",
        "repeat_password": "Password123!"
    })
    assert owner_res.status_code == 201
    owner_token = owner_res.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Create project
    proj_res = client.post("/api/projects", json={
        "name": "Team Collab Project",
        "role": "process_owner"
    }, headers=owner_headers)
    assert proj_res.status_code == 201
    pid = proj_res.json()["id"]

    # 3. Create invitation and then revoke it
    inv_res = client.post(f"/api/projects/{pid}/invitations", json={
        "email": "revoked_user@college.edu",
        "role": "analyst"
    }, headers=owner_headers)
    assert inv_res.status_code == 200
    inv_id = inv_res.json()["id"]

    revoke_res = client.post(f"/api/invitations/{inv_id}/revoke", headers=owner_headers)
    assert revoke_res.status_code == 200
    assert revoke_res.json()["message"] == "Invitation revoked."

    # 4. Invite member who accepts
    member_res = client.post("/api/auth/register", json={
        "display_name": "Sam Winchester",
        "email": "sam_team@college.edu",
        "password": "Password123!",
        "repeat_password": "Password123!"
    })
    assert member_res.status_code == 201
    member_data = member_res.json()
    member_id = member_data["user"]["id"]
    member_headers = {"Authorization": f"Bearer {member_data['access_token']}"}

    inv2_res = client.post(f"/api/projects/{pid}/invitations", json={
        "email": "sam_team@college.edu",
        "role": "technical_reviewer"
    }, headers=owner_headers)
    assert inv2_res.status_code == 200
    inv2_id = inv2_res.json()["id"]

    accept_res = client.post(f"/api/invitations/{inv2_id}/accept", headers=member_headers)
    assert accept_res.status_code == 200

    # Verify member is in team
    team_res = client.get(f"/api/projects/{pid}/members", headers=owner_headers)
    assert team_res.status_code == 200
    members = team_res.json()["members"]
    assert any(m["user_id"] == member_id for m in members)

    # 5. Remove member
    remove_res = client.delete(f"/api/projects/{pid}/members/{member_id}", headers=owner_headers)
    assert remove_res.status_code == 200

    # Verify member is removed
    team_after = client.get(f"/api/projects/{pid}/members", headers=owner_headers)
    assert team_after.status_code == 200
    members_after = team_after.json()["members"]
    assert not any(m["user_id"] == member_id for m in members_after)


def test_srs_artifact_generation():
    """Verify SRS artifact generation, mandatory sections, and database persistence.

    Covers SPEC-10-01, SPEC-10-04, SPEC-12-06.
    """
    from app.agents.requirements import requirements_agent

    client = TestClient(app)
    reg_res = client.post("/api/auth/register", json={
        "display_name": "SRS Tester",
        "email": "srs_tester@processfoundry.ai",
        "password": "Password123!",
        "repeat_password": "Password123!"
    })
    tok = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {tok}"}

    proj_res = client.post("/api/projects", json={
        "name": "SRS Verification Process",
        "role": "process_owner",
        "description": "Validation of full SRS export."
    }, headers=headers)
    pid = proj_res.json()["id"]

    artifacts = requirements_agent.generate_all_artifacts(pid)
    art_map = {a["artifact_type"]: a for a in artifacts}

    assert "srs" in art_map, "SRS artifact must be generated by requirements agent"
    srs_art = art_map["srs"]
    assert srs_art["status"] == "draft"
    md = srs_art.get("markdown") or ""

    # Check mandatory sections per build brief Part 3.5
    mandatory_sections = [
        "1. Purpose",
        "2. Scope",
        "3. Definitions and Abbreviations",
        "4. System Context",
        "5. Functional Requirements",
        "6. External Interfaces",
        "7. Performance and Availability Requirements",
        "8. Security and Privacy Requirements",
        "9. Data Requirements",
        "10. Business Rules Applied",
        "11. Constraints",
        "12. Assumptions",
        "13. Verification Criteria"
    ]
    for sec in mandatory_sections:
        assert sec in md, f"Missing mandatory SRS section: {sec}"

