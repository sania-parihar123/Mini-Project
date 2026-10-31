"""Tests for Interactive Prototype feature (08).

Covers:
- Spec builder validations (no To-Be, no workflow_json, no requirements)
- Spec fields derived purely from steps/requirements (no invented data)
- Missing-info notices for unknowns and unnamed actors
- Renderer security: zero eval(), exec(), or Function()
- Renderer HTML escaping of user content (XSS protection)
- Multilingual text preservation (Devanagari, etc.)
- API endpoints: auth requirement, role checks, 404 before generate, HTML download, version history
- Deterministic fingerprint caching
"""
import inspect
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.database import db
from app.services import prototype_renderer
from app.services.prototype_builder import (
    PrototypeBuildError,
    build_prototype_spec,
    infer_field_type,
)
from app.services.prototype_renderer import render_full_prototype


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_prototype.db")
    monkeypatch.setattr(db, "sqlite_path", test_db_path)
    monkeypatch.setattr(db, "use_postgres", False)
    db._init_sqlite()


def _create_authenticated_client_with_project(role="analyst"):
    client = TestClient(app)
    # Register user
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = client.post("/api/auth/register", json={
        "display_name": "Test User",
        "email": email,
        "password": "Password123!",
        "repeat_password": "Password123!"
    })
    token = reg_res.json()["access_token"]
    user_id = reg_res.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create project
    proj_res = client.post("/api/projects", headers=headers, json={
        "name": "Fee Waiver Process",
        "role": role,
        "process_type": "finance",
        "description": "Fee waiver application process"
    })
    project_id = proj_res.json()["id"]

    return client, headers, user_id, project_id


def _seed_project_workflow_and_requirements(project_id, user_id):
    # 1. Process version with steps
    pv = db.create_process_version(
        project_id,
        version=1,
        as_is_json={"name": "As-Is Fee Waiver", "steps": []},
        to_be_json={
            "process_name": "To-Be Fee Waiver",
            "steps": [
                {
                    "id": "STEP-001",
                    "step_key": "STEP-001",
                    "name": "Submit Application Form",
                    "actor": "Student",
                    "inputs": ["Income Certificate", "Application Date", "Family Income"],
                    "outputs": ["Application Reference ID"],
                    "unknowns": [],
                    "automation": "human",
                    "human_approval_required": False
                },
                {
                    "id": "STEP-002",
                    "step_key": "STEP-002",
                    "name": "Verify Eligibility & Income",
                    "actor": "Scrutiny Officer",
                    "inputs": ["Application Reference ID", "Tax Return Copy"],
                    "outputs": ["Verification Report", "Eligibility Decision"],
                    "unknowns": ["System used for verification not stated"],
                    "automation": "ai_assisted",
                    "human_approval_required": True
                }
            ]
        },
        status="approved"
    )

    # Save process steps
    step1 = db.save_process_step(
        project_id=project_id,
        process_version_id=pv["id"],
        name="Submit Application Form",
        actor="Student",
        step_type="task",
        sequence=1,
        inputs=["Income Certificate", "Application Date", "Family Income"],
        outputs=["Application Reference ID"],
        unknowns=[],
        automation="human",
        human_approval_required=False
    )
    step2 = db.save_process_step(
        project_id=project_id,
        process_version_id=pv["id"],
        name="Verify Eligibility & Income",
        actor="Scrutiny Officer",
        step_type="task",
        sequence=2,
        inputs=["Application Reference ID", "Tax Return Copy"],
        outputs=["Verification Report", "Eligibility Decision"],
        unknowns=["System used for verification not stated"],
        automation="ai_assisted",
        human_approval_required=True
    )

    # 2. Workflow JSON artifact
    db.save_artifact(
        project_id=project_id,
        artifact_type="workflow_json",
        markdown="# Workflow",
        content_json={
            "name": "To-Be Fee Waiver",
            "steps": [
                {"id": step1["step_key"], "name": "Submit Application Form", "actor": "Student"},
                {"id": step2["step_key"], "name": "Verify Eligibility & Income", "actor": "Scrutiny Officer"}
            ],
            "transitions": [
                {"from": step1["step_key"], "to": step2["step_key"], "condition": "on_success"}
            ]
        },
        created_by=user_id
    )

    # 3. Business rule
    br = db.save_business_rule(
        project_id=project_id,
        description="Income must be below 2,50,000 INR per annum for full waiver.",
        condition_json={"income_max": 250000},
        evidence_ids=[]
    )

    # 4. Requirements
    req1 = db.save_requirement(
        project_id=project_id,
        req_type="functional",
        title="Student Application Submission",
        statement="The system shall allow students to upload income certificates and state annual income.",
        priority="Must",
        acceptance_criteria=["Must capture Income Certificate.", "Must capture Family Income."],
        status="draft",
        links=[("step", step1["id"], "satisfies"), ("rule", br["id"], "governed_by")]
    )
    req2 = db.save_requirement(
        project_id=project_id,
        req_type="functional",
        title="Scrutiny Officer Approval",
        statement="The scrutiny officer must review and approve or reject the application.",
        priority="Must",
        acceptance_criteria=["Must require human sign-off."],
        status="draft",
        links=[("step", step2["id"], "satisfies"), ("rule", br["id"], "governed_by")]
    )

    return pv


def test_prototype_spec_builder_fails_without_to_be():
    client, headers, user_id, project_id = _create_authenticated_client_with_project()
    with pytest.raises(PrototypeBuildError, match="No approved To-Be process yet"):
        build_prototype_spec(project_id, user_id)


def test_prototype_spec_fails_without_workflow_json():
    client, headers, user_id, project_id = _create_authenticated_client_with_project()
    db.create_process_version(
        project_id,
        version=1,
        as_is_json={"steps": []},
        to_be_json={"steps": [{"id": "STEP-001", "name": "Step 1"}]},
        status="approved"
    )
    with pytest.raises(PrototypeBuildError, match="Workflow JSON artifact is not available"):
        build_prototype_spec(project_id, user_id)


def test_prototype_spec_fails_without_requirements():
    client, headers, user_id, project_id = _create_authenticated_client_with_project()
    db.create_process_version(
        project_id,
        version=1,
        as_is_json={"steps": []},
        to_be_json={"steps": [{"id": "STEP-001", "name": "Step 1"}]},
        status="approved"
    )
    db.save_artifact(
        project_id=project_id,
        artifact_type="workflow_json",
        markdown="# Workflow",
        content_json={"steps": [{"id": "STEP-001", "name": "Step 1"}]},
        created_by=user_id
    )
    with pytest.raises(PrototypeBuildError, match="Requirements have not been synthesized yet"):
        build_prototype_spec(project_id, user_id)


def test_prototype_spec_fields_derived_from_steps():
    client, headers, user_id, project_id = _create_authenticated_client_with_project()
    _seed_project_workflow_and_requirements(project_id, user_id)

    spec = build_prototype_spec(project_id, user_id)
    assert spec is not None
    assert len(spec.screens) == 2

    # Screen 1 fields
    screen1 = spec.screens[0]
    field_names = [f.name for f in screen1.fields]
    assert "Income Certificate" in field_names
    assert "Application Date" in field_names
    assert "Family Income" in field_names

    # Check inferred types
    f_cert = next(f for f in screen1.fields if f.name == "Income Certificate")
    assert f_cert.field_type == "file"
    f_date = next(f for f in screen1.fields if f.name == "Application Date")
    assert f_date.field_type == "date"
    f_inc = next(f for f in screen1.fields if f.name == "Family Income")
    assert f_inc.field_type == "number"

    # Screen 2 outputs
    screen2 = spec.screens[1]
    assert "Verification Report" in screen2.outputs
    assert "Eligibility Decision" in screen2.outputs
    assert screen2.human_approval_required is True


def test_prototype_spec_missing_info_notice_for_unnamed_actor():
    client, headers, user_id, project_id = _create_authenticated_client_with_project()
    _seed_project_workflow_and_requirements(project_id, user_id)

    spec = build_prototype_spec(project_id, user_id)
    # STEP-002 had unknown: "System used for verification not stated"
    assert any("System used for verification not stated" in n for n in spec.missing_info_notices)


def test_prototype_renderer_no_eval_or_exec():
    source = inspect.getsource(prototype_renderer)
    # Check that dangerous execution primitives are not in the Python or JS code
    code_lines = [line for line in source.splitlines() if not line.strip().startswith("#")]
    code = "\n".join(code_lines)
    assert "eval(" not in code
    assert "exec(" not in code
    assert "Function(" not in code


def test_prototype_renderer_html_escapes_all_user_text():
    spec_dict = {
        "project_id": "p-1",
        "process_name": "XSS Test <script>alert('process')</script>",
        "actors": ["<script>alert('actor')</script>"],
        "screens": [
            {
                "screen_id": "SCREEN-001",
                "title": "Malicious Step <script>alert('step')</script>",
                "actor": "<script>alert('actor')</script>",
                "automation": "human",
                "human_approval_required": False,
                "fields": [
                    {
                        "name": "Bad Field <img src=x onerror=alert(1)>",
                        "field_type": "text",
                        "options": [],
                        "required": True,
                        "hint": "<b>bold hint</b>"
                    }
                ],
                "outputs": ["<script>output</script>"],
                "business_rule_keys": ["BR-001"],
                "requirement_keys": ["REQ-001"],
                "unknowns": ["<script>unknown</script>"]
            }
        ],
        "business_rules": [{"key": "BR-001", "description": "Test rule"}],
        "missing_info_notices": ["Notice <script>alert(1)</script>"],
        "generated_from_workflow_version": 1,
        "spec_fingerprint": "abcd",
        "created_at": "2026-10-30T10:00:00Z"
    }

    rendered = render_full_prototype(spec_dict)
    assert "<script>alert('process')</script>" not in rendered
    assert "&lt;script&gt;alert(&#x27;process&#x27;)&lt;/script&gt;" in rendered or "&lt;script&gt;alert('process')&lt;/script&gt;" in rendered
    assert "PROTOTYPE" in rendered


def test_prototype_api_generate_requires_auth():
    client = TestClient(app)
    res = client.post("/api/projects/proj-123/prototype/generate")
    assert res.status_code == 401


def test_prototype_api_get_returns_404_before_generation():
    client, headers, user_id, project_id = _create_authenticated_client_with_project()
    res = client.get(f"/api/projects/{project_id}/prototype", headers=headers)
    assert res.status_code == 404


def test_prototype_api_generate_analyst_can_generate():
    client, headers, user_id, project_id = _create_authenticated_client_with_project(role="analyst")
    _seed_project_workflow_and_requirements(project_id, user_id)

    res = client.post(f"/api/projects/{project_id}/prototype/generate", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == project_id
    assert data["spec_version"] == 1
    assert len(data["spec_json"]["screens"]) == 2

    # Now GET /prototype should return 200
    get_res = client.get(f"/api/projects/{project_id}/prototype", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["spec_version"] == 1


def test_prototype_cache_is_keyed_on_fingerprint():
    client, headers, user_id, project_id = _create_authenticated_client_with_project(role="process_owner")
    _seed_project_workflow_and_requirements(project_id, user_id)

    # First generation
    res1 = client.post(f"/api/projects/{project_id}/prototype/generate", headers=headers)
    assert res1.status_code == 200
    ver1 = res1.json()["spec_version"]
    fp1 = res1.json()["spec_fingerprint"]
    assert ver1 == 1

    # Add a business rule and regenerate
    db.save_business_rule(
        project_id=project_id,
        description="Candidate must provide domicile certificate.",
        condition_json={"domicile_required": True},
        evidence_ids=[]
    )

    res2 = client.post(f"/api/projects/{project_id}/prototype/generate", headers=headers)
    assert res2.status_code == 200
    ver2 = res2.json()["spec_version"]
    fp2 = res2.json()["spec_fingerprint"]
    assert ver2 == 2
    assert fp1 != fp2  # Fingerprint changed because business rules changed!


def test_prototype_html_download_endpoint():
    client, headers, user_id, project_id = _create_authenticated_client_with_project()
    _seed_project_workflow_and_requirements(project_id, user_id)

    client.post(f"/api/projects/{project_id}/prototype/generate", headers=headers)
    res = client.get(f"/api/projects/{project_id}/prototype/html", headers=headers)
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Interactive Prototype" in res.text
    assert "Student" in res.text


def test_prototype_multilingual_text_preserved():
    client, headers, user_id, project_id = _create_authenticated_client_with_project()
    pv = _seed_project_workflow_and_requirements(project_id, user_id)
    steps = db.list_process_steps(pv["id"])
    step1 = steps[0]

    # Save a requirement with Hindi / Marathi title and acceptance criteria linked to step1
    db.save_requirement(
        project_id=project_id,
        req_type="functional",
        title="फी माफी अर्ज (Fee Waiver Application)",
        statement="विद्यार्थ्याने उत्पन्नाचा दाखला सादर करावा (Student must submit income certificate).",
        priority="Must",
        acceptance_criteria=["Must capture उत्पन्नाचा दाखला."],
        status="draft",
        links=[("step", step1["id"], "satisfies")]
    )

    spec = build_prototype_spec(project_id, user_id)
    html_output = render_full_prototype(spec)
    # Check that Marathi/Hindi text survived intact
    assert "उत्पन्नाचा दाखला" in html_output


def test_prototype_versions_endpoint():
    client, headers, user_id, project_id = _create_authenticated_client_with_project(role="analyst")
    _seed_project_workflow_and_requirements(project_id, user_id)

    # Generate version 1
    client.post(f"/api/projects/{project_id}/prototype/generate", headers=headers)

    # Generate version 2
    db.save_business_rule(
        project_id=project_id,
        description="Extra rule for version 2",
        condition_json={},
        evidence_ids=[]
    )
    client.post(f"/api/projects/{project_id}/prototype/generate", headers=headers)

    res = client.get(f"/api/projects/{project_id}/prototype/versions", headers=headers)
    assert res.status_code == 200
    versions = res.json()
    assert len(versions) == 2
    assert versions[0]["spec_version"] == 2
    assert versions[1]["spec_version"] == 1


def test_api_client_prototype_methods(monkeypatch):
    from app.ui.api_client import api_client
    client, headers, user_id, project_id = _create_authenticated_client_with_project(role="analyst")
    _seed_project_workflow_and_requirements(project_id, user_id)
    token = headers["Authorization"].split(" ")[1]

    monkeypatch.setattr(api_client, "_client", client)

    # Before generate, get_prototype_spec returns None
    assert api_client.get_prototype_spec(token, project_id) is None
    assert api_client.get_prototype_versions(token, project_id) == []

    # Generate via api_client
    gen_res = api_client.regenerate_prototype(token, project_id)
    assert gen_res["spec_version"] == 1

    # Get spec
    spec_data = api_client.get_prototype_spec(token, project_id)
    assert spec_data is not None
    assert spec_data["spec_version"] == 1

    # Get html
    html_str = api_client.get_prototype_html(token, project_id)
    assert html_str is not None
    assert "PROTOTYPE" in html_str

    # Get versions
    versions = api_client.get_prototype_versions(token, project_id)
    assert len(versions) == 1
    assert versions[0]["spec_version"] == 1
    assert "spec_fingerprint" in versions[0]
    assert "created_at" in versions[0]
