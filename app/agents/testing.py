"""ProcessFoundry AI: Test and UAT Generator Agent (A12)."""
import logging
from typing import List, Dict, Any

from app.repositories.database import db
from app.services import process_artifacts

logger = logging.getLogger("processfoundry.agent.testing")

class TestingAgent:
    def generate_tests_and_uat(self, project_id: str, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate positive, negative, boundary, and UAT scenarios linked to requirements."""
        saved_tests = []
        for req in requirements:
            req_id = req["id"]
            req_key = req.get("requirement_key", "REQ")
            req_stmt = req.get("statement", "")

            # 1. Positive Test
            pos_test = db.save_test_case(
                project_id=project_id,
                requirement_id=req_id,
                kind="positive",
                scenario=f"Verify nominal execution for {req_key}: {req_stmt[:50]}",
                preconditions="Applicant provides complete, valid documentation within the official timeframe.",
                steps=["Navigate to intake portal", "Submit verified credentials", "Verify submission acknowledgement"],
                expected_result="Application advances to next workflow stage with positive verification stamp."
            )
            saved_tests.append(pos_test)

            # 2. Negative / Exception Test
            neg_test = db.save_test_case(
                project_id=project_id,
                requirement_id=req_id,
                kind="exception",
                scenario=f"Verify error handling for {req_key} when invalid inputs or deadlines are exceeded",
                preconditions="Applicant submits incomplete fields or invalid document formats.",
                steps=["Attempt submission with missing mandatory documents"],
                expected_result="System rejects submission with clear validation message and highlights required corrections."
            )
            saved_tests.append(neg_test)

            # 3. Permission / Boundary Test
            perm_test = db.save_test_case(
                project_id=project_id,
                requirement_id=req_id,
                kind="permission",
                scenario=f"Verify unauthorized role cannot modify or approve {req_key}",
                preconditions="User signed in with Analyst role attempts to perform Process Owner approval.",
                steps=["Send approve request to API as unauthorized role"],
                expected_result="System refuses request with HTTP 403 Forbidden and writes audit warning."
            )
            saved_tests.append(perm_test)

        # Generate Test Plan and UAT Pack artifacts
        project = db.get_project(project_id)
        test_plan_md = f"""# Test Plan and Verification Suite
**Project:** {project.get('name')}
**Status:** DRAFT / NEEDS REVIEW
**Version:** 1.0

## 1. Scope
Validation of business rules, functional workflows, permission constraints, and boundary conditions for {project.get('name')}.

## 2. Test Strategy
Automated schema validation, positive verification, negative boundary tests, and role-based permission checks.

## 3. Test Cases Summary
Total Test Scenarios Generated: {len(saved_tests)}
{chr(10).join([f"- **{t.get('test_key')}** [{t.get('kind').upper()}]: {t.get('scenario')} -> *Links to {t.get('requirement_key', 'REQ')}*" for t in saved_tests[:12]])}

## 4. Test Environment & Prerequisites
- Staging environment populated with synthetic test fixtures.
- Test user accounts with Analyst, Process Owner, and Technical Reviewer roles.

## 5. Reviewer
**Technical Reviewer Sign-Off:** Pending
"""
        db.save_artifact(project_id, "test_plan", test_plan_md, content_json={"tests_count": len(saved_tests)}, status="draft")

        uat_md = f"""# User Acceptance Testing (UAT) Pack
**Project:** {project.get('name')}
**Status:** DRAFT / NEEDS REVIEW

| Scenario ID | User Persona | Starting Conditions | Action | Expected Outcome | Pass/Fail |
|---|---|---|---|---|---|
| UAT-001 | Student Applicant | Valid identity credentials | Fill online intake form | Immediate receipt confirmation | [ ] |
| UAT-002 | Verification Clerk | New submission received | Check attached certificates | Verification badge generated | [ ] |
| UAT-003 | Process Owner | Pending approval queue | Review applicant dossier | Final decision recorded in audit log | [ ] |
| UAT-004 | Unauthorized User | Non-member account | Access project details | Access denied HTTP 404 | [ ] |
"""
        # Build UAT scenarios from the approved steps and rules; keep the fixed
        # table only when the project has no steps yet.
        pv = db.get_latest_process_version(project_id)
        uat_steps = pv.get("steps", []) if pv else []
        uat_md = process_artifacts.uat_md(project, uat_steps, db.list_project_business_rules(project_id)) or uat_md
        db.save_artifact(project_id, "uat_pack", uat_md, content_json={}, status="draft")

        return saved_tests

testing_agent = TestingAgent()
