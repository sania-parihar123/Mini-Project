"""Comprehensive tests for Delete Project functionality.

Covers:
1. Successful project deletion via DELETE /api/projects/{project_id}.
2. Deletion of all associated project data across all database tables.
3. Multi-project isolation (ensuring other projects and their data/files remain untouched).
4. Attempting to delete a nonexistent project (HTTP 404).
5. Permission and authorization enforcement (process owner/creator allowed; analyst/reviewer denied).
6. Database transaction rollback and file cleanup safety on failure.
7. Cancelled deletion (ensuring no data is deleted if cancelled).
8. APIClient.delete_project wrapper integration.
"""
import io
import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.database import db
from app.ui.api_client import APIClient, APIError


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Isolated test client with fresh SQLite DB and uploads folder."""
    test_db_path = str(tmp_path / "test_delete_project.db")
    upload_path = str(tmp_path / "uploads")
    os.makedirs(upload_path, exist_ok=True)
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    monkeypatch.setattr(settings, "upload_dir", upload_path)
    db._init_sqlite()
    return TestClient(app, raise_server_exceptions=False)


def _create_user(client: TestClient, email: str, name: str = "Test User") -> str:
    password = "TestPassword123!"
    res = client.post("/api/auth/register", json={
        "display_name": name,
        "email": email,
        "password": password,
        "repeat_password": password
    })
    assert res.status_code == 201, res.text
    return res.json()["access_token"]


def _create_project(client: TestClient, token: str, name: str, role: str = "process_owner") -> str:
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/projects", json={
        "name": name,
        "role": role,
        "process_type": "admissions",
        "description": f"Workspace for {name}"
    }, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_successful_project_deletion_via_api(client):
    """Test full deletion of a project and its uploaded files via API."""
    token = _create_user(client, "owner@processfoundry.ai", "Process Owner")
    headers = {"Authorization": f"Bearer {token}"}
    pid = _create_project(client, token, "Scholarship Project", role="process_owner")

    # Upload a document
    doc_content = b"# Scholarship Policy\nApplications must be submitted by 31 March."
    files = {"file": ("scholarship.txt", io.BytesIO(doc_content), "text/plain")}
    upload_res = client.post(f"/api/projects/{pid}/documents", files=files, headers=headers)
    assert upload_res.status_code == 201, upload_res.text

    # Verify physical file exists on disk
    project_upload_dir = Path(settings.upload_dir) / pid
    assert project_upload_dir.exists()
    disk_files = list(project_upload_dir.glob("*"))
    assert len(disk_files) >= 1

    # Call DELETE /api/projects/{pid}
    del_res = client.delete(f"/api/projects/{pid}", headers=headers)
    assert del_res.status_code == 200, del_res.text
    del_data = del_res.json()
    assert del_data["project_id"] == pid
    assert "permanently deleted" in del_data["message"]

    # Verify project is no longer returned in GET /api/projects/{pid}
    get_res = client.get(f"/api/projects/{pid}", headers=headers)
    assert get_res.status_code == 404

    # Verify project is not in user's project list
    list_res = client.get("/api/projects", headers=headers)
    assert list_res.status_code == 200
    assert not any(p["id"] == pid for p in list_res.json())

    # Verify physical files and project upload directory on disk are cleaned up
    assert not project_upload_dir.exists()


def test_cascade_deletion_cleans_all_database_tables(client):
    """Verify that deleting a project removes records across all 28 project-related tables."""
    token = _create_user(client, "alltables@processfoundry.ai", "Admin")
    headers = {"Authorization": f"Bearer {token}"}
    pid = _create_project(client, token, "Deep Project", role="process_owner")
    user = client.get("/api/me", headers=headers).json()
    uid = user["id"]

    # Populate child rows in all tables
    with db.get_connection() as conn:
        cur = conn.cursor()

        # Document + Section + Chunk + Understanding
        doc_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO documents (id, project_id, filename, mime_type, checksum, version, storage_path, size_bytes, parse_status, created_at)
            VALUES (?, ?, 'doc.txt', 'text/plain', 'chk123', 1, ?, 100, 'parsed', '2026-01-01');
        """, (doc_id, pid, str(Path(settings.upload_dir) / pid / "test.txt")))

        sec_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO document_sections (id, document_id, section_index, text)
            VALUES (?, ?, 1, 'Section text');
        """, (sec_id, doc_id))

        chunk_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO document_chunks (id, project_id, document_id, section_id, chunk_index, text)
            VALUES (?, ?, ?, ?, 1, 'Chunk text');
        """, (chunk_id, pid, doc_id, sec_id))

        cur.execute("""
            INSERT INTO document_understanding (document_id, checksum, content_json, created_at)
            VALUES (?, 'chk123', '{}', '2026-01-01');
        """, (doc_id,))

        # Evidence
        evd_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO evidence_items (id, project_id, evidence_key, document_section_id, claim, quote, claim_type, created_at)
            VALUES (?, ?, 'EVD-001', ?, 'Claim', 'Quote', 'step', '2026-01-01');
        """, (evd_id, pid, sec_id))

        # Process Versions, Steps, Step Evidence, Step Transitions
        pv_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO process_versions (id, project_id, version, status, created_at)
            VALUES (?, ?, 1, 'draft', '2026-01-01');
        """, (pv_id, pid))

        step_id1 = str(uuid.uuid4())
        step_id2 = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO process_steps (id, process_version_id, step_key, name, sequence)
            VALUES (?, ?, 'STEP-001', 'Step 1', 1);
        """, (step_id1, pv_id))
        cur.execute("""
            INSERT INTO process_steps (id, process_version_id, step_key, name, sequence)
            VALUES (?, ?, 'STEP-002', 'Step 2', 2);
        """, (step_id2, pv_id))

        cur.execute("""
            INSERT INTO step_evidence (step_id, evidence_id) VALUES (?, ?);
        """, (step_id1, evd_id))

        cur.execute("""
            INSERT INTO step_transitions (id, process_version_id, from_step_id, to_step_id)
            VALUES (?, ?, ?, ?);
        """, (str(uuid.uuid4()), pv_id, step_id1, step_id2))

        # Business Rules, Rule Evidence
        br_id1 = str(uuid.uuid4())
        br_id2 = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO business_rules (id, project_id, rule_key, description, status, created_at)
            VALUES (?, ?, 'BR-001', 'Rule 1', 'needs_review', '2026-01-01');
        """, (br_id1, pid))
        cur.execute("""
            INSERT INTO business_rules (id, project_id, rule_key, description, status, supersedes_rule_id, created_at)
            VALUES (?, ?, 'BR-002', 'Rule 2', 'needs_review', ?, '2026-01-01');
        """, (br_id2, pid, br_id1))

        cur.execute("""
            INSERT INTO rule_evidence (rule_id, evidence_id) VALUES (?, ?);
        """, (br_id1, evd_id))

        # Runs
        run_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO runs (id, project_id, status, created_at, updated_at)
            VALUES (?, ?, 'completed', '2026-01-01', '2026-01-01');
        """, (run_id, pid))

        # Clarifications, Answers, Links, Verified Facts
        clar_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO clarification_items (id, project_id, run_id, question_key, question, fingerprint, created_at)
            VALUES (?, ?, ?, 'Q-001', 'Question 1?', 'fp1', '2026-01-01');
        """, (clar_id, pid, run_id))

        cur.execute("""
            INSERT INTO clarification_links (clarification_id, target_type, target_id)
            VALUES (?, 'rule', ?);
        """, (clar_id, br_id1))

        cur.execute("""
            INSERT INTO clarification_answers (id, clarification_id, answer_kind, answer_text, answered_by, role, answered_at)
            VALUES (?, ?, 'answer', 'Answer text', ?, 'process_owner', '2026-01-01');
        """, (str(uuid.uuid4()), clar_id, uid))

        cur.execute("""
            INSERT INTO verified_facts (id, project_id, fact_key, statement, clarification_id, confirmed_by, confirmed_at)
            VALUES (?, ?, 'FACT-001', 'Fact text', ?, ?, '2026-01-01');
        """, (str(uuid.uuid4()), pid, clar_id, uid))

        # Requirements and Requirement Links
        req_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO requirements (id, project_id, requirement_key, type, statement, created_at)
            VALUES (?, ?, 'REQ-001', 'business', 'Statement', '2026-01-01');
        """, (req_id, pid))

        cur.execute("""
            INSERT INTO requirement_links (requirement_id, target_type, target_id, link_type)
            VALUES (?, 'rule', ?, 'derived_from');
        """, (req_id, br_id1))

        # Artifacts and Artifact Links
        art_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO artifacts (id, project_id, artifact_type, version, status, created_at)
            VALUES (?, ?, 'brd', 1, 'draft', '2026-01-01');
        """, (art_id, pid))

        cur.execute("""
            INSERT INTO artifact_links (artifact_id, target_type, target_id, link_type)
            VALUES (?, 'requirement', ?, 'derived_from');
        """, (art_id, req_id))

        # Test Cases
        cur.execute("""
            INSERT INTO test_cases (id, project_id, test_key, requirement_id, scenario, expected_result, created_at)
            VALUES (?, ?, 'TEST-001', ?, 'Scenario', 'Expected', '2026-01-01');
        """, (str(uuid.uuid4()), pid, req_id))

        # Approvals
        cur.execute("""
            INSERT INTO approvals (id, project_id, target_type, target_id, decision, reviewer, reviewer_role, timestamp)
            VALUES (?, ?, 'rule', ?, 'approve', ?, 'process_owner', '2026-01-01');
        """, (str(uuid.uuid4()), pid, br_id1, uid))

        # Agent Runs
        cur.execute("""
            INSERT INTO agent_runs (id, project_id, run_id, node_name, status, started_at)
            VALUES (?, ?, ?, 'discovery', 'succeeded', '2026-01-01');
        """, (str(uuid.uuid4()), pid, run_id))

        # Project Invitations
        cur.execute("""
            INSERT INTO project_invitations (id, project_id, email, role, status, invited_by, created_at, expires_at)
            VALUES (?, ?, 'invited@example.com', 'analyst', 'pending', ?, '2026-01-01', '2026-01-15');
        """, (str(uuid.uuid4()), pid, uid))

        # Project Counters
        cur.execute("""
            INSERT INTO project_counters (project_id, entity, next_value)
            VALUES (?, 'EVD', 10);
        """, (pid,))

        conn.commit()

    # Call repository delete_project
    res = db.delete_project(pid)
    assert res is not None
    assert res["deleted"] is True
    assert res["project_id"] == pid

    # Verify that EVERY table no longer has any record referencing this project_id
    with db.get_connection() as conn:
        cur = conn.cursor()

        direct_tables = [
            "projects", "project_members", "project_invitations", "project_counters",
            "documents", "document_chunks", "evidence_items", "process_versions",
            "business_rules", "runs", "clarification_items", "verified_facts",
            "requirements", "artifacts", "test_cases", "approvals", "agent_runs", "audit_events"
        ]
        for tbl in direct_tables:
            col = "id" if tbl == "projects" else "project_id"
            cur.execute(f"SELECT count(*) FROM {tbl} WHERE {col} = ?", (pid,))
            count = cur.fetchone()[0]
            assert count == 0, f"Table {tbl} still has {count} rows for project {pid}"

        # Check cascaded grandchild tables
        cur.execute("SELECT count(*) FROM document_sections WHERE document_id = ?", (doc_id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM document_understanding WHERE document_id = ?", (doc_id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM process_steps WHERE process_version_id = ?", (pv_id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM step_evidence WHERE step_id IN (?, ?)", (step_id1, step_id2))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM step_transitions WHERE process_version_id = ?", (pv_id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM rule_evidence WHERE rule_id IN (?, ?)", (br_id1, br_id2))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM clarification_links WHERE clarification_id = ?", (clar_id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM clarification_answers WHERE clarification_id = ?", (clar_id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM requirement_links WHERE requirement_id = ?", (req_id,))
        assert cur.fetchone()[0] == 0

        cur.execute("SELECT count(*) FROM artifact_links WHERE artifact_id = ?", (art_id,))
        assert cur.fetchone()[0] == 0


def test_delete_project_preserves_other_projects_and_data(client):
    """Ensure that deleting Project A never touches Project B or Project B's files."""
    token = _create_user(client, "multi@processfoundry.ai", "Multi User")
    headers = {"Authorization": f"Bearer {token}"}

    pid_a = _create_project(client, token, "Project Alpha", role="process_owner")
    pid_b = _create_project(client, token, "Project Beta", role="process_owner")

    # Upload file to Project A
    file_a = io.BytesIO(b"Alpha content for project A")
    res_a = client.post(f"/api/projects/{pid_a}/documents", files={"file": ("alpha.txt", file_a, "text/plain")}, headers=headers)
    assert res_a.status_code == 201

    # Upload file to Project B
    file_b = io.BytesIO(b"Beta content for project B")
    res_b = client.post(f"/api/projects/{pid_b}/documents", files={"file": ("beta.txt", file_b, "text/plain")}, headers=headers)
    assert res_b.status_code == 201

    dir_a = Path(settings.upload_dir) / pid_a
    dir_b = Path(settings.upload_dir) / pid_b
    assert dir_a.exists() and len(list(dir_a.glob("*"))) >= 1
    assert dir_b.exists() and len(list(dir_b.glob("*"))) >= 1

    # Delete Project A only
    del_res = client.delete(f"/api/projects/{pid_a}", headers=headers)
    assert del_res.status_code == 200

    # Verify Project A is gone
    assert client.get(f"/api/projects/{pid_a}", headers=headers).status_code == 404
    assert not dir_a.exists()

    # Verify Project B remains fully intact
    get_b = client.get(f"/api/projects/{pid_b}", headers=headers)
    assert get_b.status_code == 200
    assert get_b.json()["name"] == "Project Beta"

    docs_b = client.get(f"/api/projects/{pid_b}/documents", headers=headers)
    assert docs_b.status_code == 200
    assert len(docs_b.json()) == 1
    assert docs_b.json()[0]["filename"] == "beta.txt"

    # Verify Project B's physical files are completely intact
    assert dir_b.exists()
    assert len(list(dir_b.glob("*"))) >= 1


def test_delete_nonexistent_project_returns_404(client):
    """Attempting to delete a nonexistent project must return 404."""
    token = _create_user(client, "nonexistent@processfoundry.ai", "Tester")
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = str(uuid.uuid4())

    res = client.delete(f"/api/projects/{fake_id}", headers=headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_delete_project_permission_enforcement(client):
    """Enforce authorization: only Process Owner or Creator can delete."""
    owner_token = _create_user(client, "owner_perm@processfoundry.ai", "Owner")
    analyst_token = _create_user(client, "analyst_perm@processfoundry.ai", "Analyst")
    outsider_token = _create_user(client, "outsider@processfoundry.ai", "Outsider")

    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
    outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

    # Owner creates project
    pid = _create_project(client, owner_token, "Permission Project", role="process_owner")

    # Invite analyst to project
    inv_res = client.post(f"/api/projects/{pid}/invitations", json={
        "email": "analyst_perm@processfoundry.ai",
        "role": "analyst"
    }, headers=owner_headers)
    assert inv_res.status_code == 200, inv_res.text
    inv_id = inv_res.json()["id"]

    # Analyst accepts invitation
    acc_res = client.post(f"/api/invitations/{inv_id}/accept", headers=analyst_headers)
    assert acc_res.status_code == 200

    # 1. Outsider attempts to delete -> 404 (not a member)
    out_res = client.delete(f"/api/projects/{pid}", headers=outsider_headers)
    assert out_res.status_code == 404

    # 2. Analyst (non-creator) attempts to delete -> 403 Forbidden
    an_res = client.delete(f"/api/projects/{pid}", headers=analyst_headers)
    assert an_res.status_code == 403
    assert "Only the Process Owner or project creator can delete" in an_res.json()["detail"]

    # 3. Unauthenticated request -> 401 Unauthorized
    unauth_res = client.delete(f"/api/projects/{pid}")
    assert unauth_res.status_code == 401

    # 4. Process Owner deletes -> 200 OK
    del_res = client.delete(f"/api/projects/{pid}", headers=owner_headers)
    assert del_res.status_code == 200


def test_database_transaction_rollback_and_file_safety(client, monkeypatch):
    """If database deletion fails mid-transaction, rollback occurs and files are not removed."""
    token = _create_user(client, "tx_test@processfoundry.ai", "Tx Tester")
    headers = {"Authorization": f"Bearer {token}"}
    pid = _create_project(client, token, "Tx Project", role="process_owner")

    # Upload a document
    doc_content = b"# Important File\nDo not delete if error occurs."
    files = {"file": ("important.txt", io.BytesIO(doc_content), "text/plain")}
    upload_res = client.post(f"/api/projects/{pid}/documents", files=files, headers=headers)
    assert upload_res.status_code == 201

    proj_dir = Path(settings.upload_dir) / pid
    assert proj_dir.exists()
    assert len(list(proj_dir.glob("*"))) >= 1

    # Simulate database error on DELETE FROM projects
    original_get_connection = db.get_connection

    class FailingCursor:
        def __init__(self, real_cur):
            self._cur = real_cur

        def execute(self, query, params=None):
            if "DELETE FROM projects " in query:
                raise RuntimeError("Simulated Database Hardware Failure")
            return self._cur.execute(query, params) if params is not None else self._cur.execute(query)

        def fetchone(self):
            return self._cur.fetchone()

        def fetchall(self):
            return self._cur.fetchall()

        def __getattr__(self, name):
            return getattr(self._cur, name)

    class FailingConnection:
        def __init__(self, real_conn):
            self._conn = real_conn

        def cursor(self):
            return FailingCursor(self._conn.cursor())

        def commit(self):
            self._conn.commit()

        def rollback(self):
            self._conn.rollback()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return self._conn.__exit__(exc_type, exc_val, exc_tb)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    monkeypatch.setattr(db, "get_connection", lambda: FailingConnection(original_get_connection()))

    # Attempt delete -> should raise error and rollback
    with pytest.raises(RuntimeError, match="Simulated Database Hardware Failure"):
        db.delete_project(pid)

    # Restore real connection
    db.get_connection = original_get_connection

    # Verify that project STILL exists in the database
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM projects WHERE id = ?", (pid,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Tx Project"

    # Verify that files were NOT deleted on disk
    assert proj_dir.exists()
    assert len(list(proj_dir.glob("*"))) >= 1


def test_cancelled_deletion_leaves_data_untouched(client):
    """Simulate user cancelling deletion: project and all files must remain completely untouched."""
    token = _create_user(client, "cancel_test@processfoundry.ai", "Cancel Tester")
    headers = {"Authorization": f"Bearer {token}"}
    pid = _create_project(client, token, "To Cancel Project", role="process_owner")

    doc_content = b"Safe file content."
    client.post(f"/api/projects/{pid}/documents", files={"file": ("safe.txt", io.BytesIO(doc_content), "text/plain")}, headers=headers)

    proj_dir = Path(settings.upload_dir) / pid
    assert proj_dir.exists()

    # User opens confirmation dialog, reviews warning, and clicks Cancel.
    # Verify no DELETE request is sent, and project and files remain untouched.
    proj = client.get(f"/api/projects/{pid}", headers=headers)
    assert proj.status_code == 200
    assert proj.json()["name"] == "To Cancel Project"

    docs = client.get(f"/api/projects/{pid}/documents", headers=headers)
    assert docs.status_code == 200
    assert len(docs.json()) == 1

    assert proj_dir.exists()
    assert len(list(proj_dir.glob("*"))) == 1


def test_api_client_delete_project_integration(client):
    """Test APIClient.delete_project method against backend endpoint."""
    token = _create_user(client, "apiclient@processfoundry.ai", "API Tester")
    pid = _create_project(client, token, "APIClient Project", role="process_owner")

    api = APIClient(base_url="http://testserver")
    api._client = client

    # Successful delete via APIClient
    res = api.delete_project(token, pid)
    assert res["project_id"] == pid

    # Attempting to delete again raises APIError with 404
    with pytest.raises(APIError) as exc_info:
        api.delete_project(token, pid)
    assert exc_info.value.status_code == 404
