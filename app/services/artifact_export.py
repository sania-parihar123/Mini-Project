"""ProcessFoundry AI: Artifact Generation and Markdown Export Service."""
import json
from typing import List, Dict, Any, Optional

def generate_brd_markdown(project: Dict[str, Any], requirements: List[Dict[str, Any]], rules: List[Dict[str, Any]], steps: List[Dict[str, Any]]) -> str:
    biz_reqs = [r for r in requirements if r.get("type") == "business"]
    return f"""# Business Requirements Document (BRD)
**Project:** {project.get('name', 'ProcessFoundry Project')}
**Status:** DRAFT / NEEDS REVIEW
**Version:** 1.0

> [!NOTE]
> This document was synthesized by ProcessFoundry AI from verified evidence and business rules. All requirements are in Draft status awaiting Process Owner sign-off.

## 1. Purpose
Define the business rationale, objectives, and operational requirements for digitalizing and modernizing the {project.get('name')} process.

## 2. Business Problem
Current college administrative processes rely on fragmented documentation, manual handoffs, and ambiguous policy guidelines leading to processing delays and student uncertainty.

## 3. Goals
- Streamline process intake and eliminate redundant manual verification.
- Enforce deterministic business rules and eliminate policy ambiguities.
- Provide end-to-end auditability and student transparency.

## 4. Scope
- **In Scope:** Digital application intake, eligibility validation, role-based review workflows, exception routing, and status notifications.
- **Out of Scope:** Direct legacy ERP database writes and external financial gateway disbursements.

## 5. Stakeholders
- Process Owner (Department Authority)
- Student / Applicant
- Administrative Staff / Verification Clerks
- Technical Reviewer / IT Systems Integrator

## 6. Current Process (As-Is)
The baseline process comprises {len(steps)} discovered sequential steps identified from source documentation:
{chr(10).join([f"- **{s.get('step_key', 'STEP')}**: {s.get('name')} (Actor: {s.get('actor') or 'Not stated'})" for s in steps])}

## 7. Business Needs
{chr(10).join([f"- **{r.get('requirement_key')}**: {r.get('statement')} (Priority: {r.get('priority', 'Must')})" for r in biz_reqs]) if biz_reqs else "- Clear, deterministic intake and verified approval routing."}

## 8. Business Rules
{chr(10).join([f"- **{br.get('rule_key')}**: {br.get('description')}" for br in rules]) if rules else "- No active business rules recorded."}

## 9. Constraints
{project.get('constraints') or "Compliance with institutional policies and non-discriminatory student access."}

## 10. Assumptions
Source policies accurately reflect authorized institutional guidelines; process participants have network access.

## 11. Risks
Policy discrepancies between legacy circulars and current handbook regulations; delays during human verification transitions.

## 12. Success Measures
- 60% reduction in processing cycle time from submission to decision.
- 100% traceability from student application to approval decision.

## 13. Approvals
- **Process Owner Approval:** Pending formal human review
- **Review Date:** Unapproved (Draft)
"""

def generate_prd_markdown(project: Dict[str, Any], requirements: List[Dict[str, Any]], to_be: Optional[Dict[str, Any]] = None) -> str:
    func_reqs = [r for r in requirements if r.get("type") in ("functional", "workflow")]
    return f"""# Product Requirements Document (PRD)
**Product:** {project.get('name')} Digital Platform
**Status:** DRAFT / NEEDS REVIEW
**Version:** 1.0

## 1. Product Goal
Deliver a responsive, role-based web application enabling students to submit requests seamlessly while providing college staff with automated validation and structured review queues.

## 2. Users and Personas
- **Student / Applicant:** Submits applications, uploads documents, tracks real-time progress.
- **Verification Officer:** Reviews student documentation and handles flagged policy exceptions.
- **Process Owner / Department Head:** Approves final candidate lists, manages rules, and reviews audit reports.

## 3. User Problems
- Students lack clarity on deadline changes and required supporting attachments.
- Staff spend excessive time manually cross-referencing criteria across disparate documents.

## 4. Features
- Multi-document evidence ingestion and automated completeness check.
- Role-based inbox for assigned clarification and exception decisions.
- Real-time status tracker and audit trail for applicants.

## 5. User Stories & Acceptance Criteria
{chr(10).join([f"### {r.get('requirement_key')}: {r.get('title') or r.get('statement')[:40]}\n**Statement:** As a user, {r.get('statement')}\n**Priority:** {r.get('priority', 'Must')}\n**Status:** {r.get('status')}\n" for r in func_reqs[:8]]) if func_reqs else "User stories are generated upon process discovery."}

## 6. Priorities
P0 (Intake & Rules Engine), P1 (Role Routing & Notifications), P2 (Export & Analytics).

## 7. Dependencies
Institution identity directory (LDAP/OAuth), secure cloud file storage, transactional email gateway.

## 8. Non-Functional Needs
Sub-second API response times, 99.9% uptime during intake windows, WCAG 2.1 AA accessibility compliance.

## 9. Open Questions
Unresolved policy questions flagged during discovery must be clarified by the Process Owner.
"""

def generate_frd_markdown(project: Dict[str, Any], requirements: List[Dict[str, Any]], rules: List[Dict[str, Any]], to_be: Optional[Dict[str, Any]] = None) -> str:
    return f"""# Functional Requirements Document (FRD)
**System:** {project.get('name')} Digital Workflow Engine
**Status:** DRAFT / NEEDS REVIEW
**Version:** 1.0

## 1. System Overview
The system coordinates student application intake, deterministic rule execution, human approval routing, and notification dispatching.

## 2. Actors and Roles
- **Process Owner:** Approves business rules, resolves conflicting policies, confirms To-Be workflow.
- **Analyst:** Sets up process workspaces, uploads source documentation, inspects extraction evidence.
- **Technical Reviewer:** Inspects architecture, data schema, and test suites.

## 3. Functional Requirements
{chr(10).join([f"- **{r.get('requirement_key')}**: {r.get('statement')} [Type: {r.get('type')}]" for r in requirements]) if requirements else "- Core workflow functional requirements."}

## 4. Workflow & Transitions
Application Submitted -> Automated Document Validation -> (If Defect: Request Clarification) -> Officer Review -> Process Owner Sign-Off -> Final Disposition.

## 5. Decision Rules
{chr(10).join([f"- **{br.get('rule_key')}**: IF {br.get('condition_json', {}).get('condition', 'standard')} THEN {br.get('condition_json', {}).get('outcome', br.get('description'))}" for br in rules[:10]]) if rules else "- Rules are derived from verified evidence."}

## 6. Validations
- Check file size (<= 25MB) and mime-type whitelist (PDF, DOCX, TXT).
- Verify mandatory fields before submission.

## 7. Exceptions
Incomplete submissions or conflicting documentary evidence route to the applicant clarification queue.

## 8. Notifications
Email alerts dispatched upon submission, clarification request, and final approval.

## 9. Permissions & Access Control
Access strictly enforced via project membership and role permission matrix (Part 7.9).

## 10. Audit Events
All state transitions, approvals, and human answers are permanently recorded in an append-only hash chain.

## 11. External Interfaces
REST APIs communicating with student portal and institutional database.

## 12. Acceptance Criteria
All functional requirements must pass automated test scenario coverage before production release.
"""

def generate_srs_markdown(project: Dict[str, Any], requirements: List[Dict[str, Any]], rules: List[Dict[str, Any]], steps: List[Dict[str, Any]]) -> str:
    """Generate a Software Requirements Specification (SRS) document.

    Mandatory sections per the build brief (Part 3.5):
    Purpose, scope, definitions, system context, functional requirements,
    interfaces, performance/availability, security/privacy, data requirements,
    constraints, assumptions, verification criteria.
    """
    func_reqs = [r for r in requirements if r.get("type") in ("functional", "workflow")]
    biz_reqs = [r for r in requirements if r.get("type") == "business"]
    project_name = project.get("name", "ProcessFoundry Project")

    return f"""# Software Requirements Specification (SRS)
**System:** {project_name} Digital Process Platform
**Status:** DRAFT / NEEDS REVIEW
**Version:** 1.0

> [!NOTE]
> Generated by ProcessFoundry AI from verified evidence, approved business rules, and process discovery. All sections require Process Owner and Technical Reviewer sign-off before engineering begins.

---

## 1. Purpose
This SRS defines the complete functional and non-functional requirements for the {project_name} digital workflow system. It is the authoritative specification for design, development, and acceptance testing.

## 2. Scope
- **System Name:** {project_name} Digital Platform
- **In Scope:** Digital intake, rule-based eligibility validation, role-based review queues, human-in-the-loop decision points, notification dispatch, and audit trail.
- **Out of Scope:** Direct writes to legacy ERP systems, external financial disbursement gateways, and student identity management infrastructure.

## 3. Definitions and Abbreviations
| Term | Definition |
|---|---|
| Process Owner | Institutional authority responsible for final rule approval and To-Be sign-off |
| Analyst | Prepares workspaces, uploads source evidence, leads discovery |
| Technical Reviewer | Inspects architecture, data model, and test coverage |
| As-Is | Current documented process state, grounded in verbatim evidence |
| To-Be | Redesigned target process approved by the Process Owner |
| HITL | Human-in-the-loop checkpoint where the AI pipeline pauses for human clarification |
| EVD | Evidence item identifier, e.g. EVD-001 |
| BR | Business rule identifier, e.g. BR-001 |
| STEP | Process step identifier, e.g. STEP-001 |

## 4. System Context
The system is a multi-tenant, role-based web application. The AI pipeline (LangGraph orchestrator) runs analysis agents sequentially: document ingestion → evidence extraction → process discovery → gap/conflict analysis → HITL pause → To-Be redesign → requirements generation → artifact export. All state is persisted to the project database with a cryptographic audit chain.

## 5. Functional Requirements

### 5.1 Business Requirements
{chr(10).join([f"- **{r.get('requirement_key')}** [{r.get('priority', 'Must')}]: {r.get('statement')}" for r in biz_reqs]) if biz_reqs else "- Enforce all verified business rules derived from official institutional documents."}

### 5.2 Functional Requirements
{chr(10).join([f"- **{r.get('requirement_key')}** [{r.get('priority', 'Must')}]: {r.get('statement')}" for r in func_reqs]) if func_reqs else "- Execute process steps in sequence with full audit logging."}

### 5.3 Process Steps Specified
{chr(10).join([f"- **{s.get('step_key', 'STEP')}**: {s.get('name')} — Actor: {s.get('actor') or 'Not stated'} — Type: {s.get('step_type', 'task')}" for s in steps]) if steps else "- Process discovery pending."}

## 6. External Interfaces
- **User Interface:** Streamlit web application accessible from any modern browser.
- **Backend API:** RESTful FastAPI service, authenticated via Bearer token.
- **LLM Gateway:** Structured-output calls to a configured AI model (Gemini or compatible).
- **Database:** PostgreSQL (production) / SQLite (development fallback), accessed via repository layer.
- **Email (Optional):** SMTP gateway for invitation notifications.

## 7. Performance and Availability Requirements
- API responses for read operations: ≤ 500 ms at p95 under normal load.
- Analysis pipeline (full run): ≤ 120 s per project when LLM responses are available.
- Target availability during operational periods: 99.5% uptime.
- Document upload: accept files up to `MAX_UPLOAD_MB` (configurable, default 25 MB).

## 8. Security and Privacy Requirements
- Passwords hashed with bcrypt ($2b$); never stored or logged in plain text.
- Session tokens signed with HMAC-SHA256 and expire after 8 hours.
- Five consecutive failed sign-in attempts trigger a 10-minute lockout.
- All project data is scoped to project membership; cross-project access is forbidden.
- Audit events are append-only with SHA-256 hash chaining to detect tampering.
- No student personal data is stored; process documents are institutional policy texts.

## 9. Data Requirements
- Every evidence item must contain a verbatim quote verified as a substring of the source section.
- Every requirement must be linked to at least one evidence item or business rule.
- Every test case must be linked to at least one requirement (enforced by database constraint).
- Process steps with no actor must be stored with `actor = NULL` and explicitly flagged.

## 10. Business Rules Applied
{chr(10).join([f"- **{br.get('rule_key')}**: {br.get('description')}" for br in rules[:15]]) if rules else "- Business rules are derived from verified evidence after the analysis run."}

## 11. Constraints
{project.get('constraints') or "Compliance with institutional regulatory frameworks and non-discriminatory student access policies."}

## 12. Assumptions
- Source policy documents accurately represent current authorized institutional guidelines.
- All project participants have reliable browser-based internet access.
- LLM responses are validated against schema and retried on malformed output; no raw LLM output is stored without validation.

## 13. Verification Criteria
- All functional requirements map to at least one passing automated test case.
- Traceability matrix shows zero orphan requirements (no requirement without linked evidence).
- Verbatim quote mismatch count in the traceability validation report must be zero.
- Process Owner has approved the To-Be model before final artifact export.
- Audit log hash chain integrity check passes without gaps.
"""


def generate_workflow_json(project: Dict[str, Any], steps: List[Dict[str, Any]], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    wf_steps = []
    transitions = []
    prev_step = None
    for idx, s in enumerate(steps):
        s_id = s.get("step_key") or f"STEP-{idx+1:03d}"
        wf_steps.append({
            "id": s_id,
            "name": s.get("name"),
            "actor": s.get("actor") or "Process Participant",
            "kind": s.get("step_type", "task"),
            "automation": s.get("automation") or "deterministic",
            "inputs": s.get("inputs", []),
            "outputs": s.get("outputs", []),
            "human_approval_required": s.get("human_approval_required", False)
        })
        if prev_step:
            transitions.append({
                "from": prev_step,
                "to": s_id,
                "condition": "on_success"
            })
        prev_step = s_id

    return {
        "process_id": project.get("id"),
        "process_name": project.get("name"),
        "version": 1,
        "status": "draft",
        "steps": wf_steps,
        "transitions": transitions
    }
