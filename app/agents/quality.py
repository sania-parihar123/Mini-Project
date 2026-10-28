"""ProcessFoundry AI: Quality and Traceability Validation Agent (A13)."""
import logging
from typing import Dict, Any, List

from app.repositories.database import db
from app.services import process_artifacts

logger = logging.getLogger("processfoundry.agent.quality")

class QualityAgent:
    def validate_traceability(self, project_id: str) -> Dict[str, Any]:
        """Read-only traceability validation. Writes nothing.

        Finding F8: this used to be called from `GET /api/projects/{id}/traceability`
        and wrote three artifacts on every page view, resetting an approved
        traceability matrix, HLD or data model back to `draft`. The GET is now
        read-only; `generate_quality_artifacts` does the writing, from the run.
        """
        return self._compute_report(project_id)

    def generate_quality_artifacts(self, project_id: str) -> Dict[str, Any]:
        """Validate and persist the traceability matrix, HLD and data model.

        Called from the run's quality node only, never from a read path.
        """
        report = self._compute_report(project_id)
        self._write_artifacts(project_id, report)
        return report

    def _compute_report(self, project_id: str) -> Dict[str, Any]:
        """Compute end-to-end traceability matrix and audit relational integrity."""
        requirements = db.list_project_requirements(project_id)
        test_cases = db.list_project_test_cases(project_id)
        evidence = db.list_project_evidence(project_id)
        questions = db.list_project_clarification_items(project_id)

        # 1. Audit quotes: verify each quote is in its section
        quote_mismatches = 0
        for ev in evidence:
            sec = db.get_section(ev["document_section_id"])
            if not sec or ev["quote"] not in sec["text"]:
                quote_mismatches += 1

        # 2. Check requirements without evidence or rules.
        # A requirement already marked `needs_clarification` has been reported
        # honestly (brief Phase 2 step 13), so it is no longer an unreported
        # defect and must not keep the bounded repair loop spinning.
        orphan_reqs = []
        for req in requirements:
            grounded = req.get("supporting_rule_keys") or req.get("supporting_evidence_keys")
            if not grounded and req.get("status") != "needs_clarification":
                orphan_reqs.append(req["requirement_key"])

        # 3. Check tests without requirements
        orphan_tests = []
        for t in test_cases:
            if not t.get("requirement_id"):
                orphan_tests.append(t["test_key"])

        open_critical_qs = [
            q["question_key"] for q in questions
            if q["status"] == "open" and q["kind"] in ("conflicting_rules", "missing_actor")
        ]

        is_valid = (quote_mismatches == 0 and len(orphan_tests) == 0 and len(open_critical_qs) == 0)

        project = db.get_project(project_id)
        matrix_md = f"""# Traceability Matrix
**Project:** {project.get('name')}
**Status:** {'VALIDATED' if is_valid else 'NEEDS REVIEW'}
**Version:** 1.0

### Relational Integrity Summary
- Total Requirements: {len(requirements)}
- Total Test Scenarios: {len(test_cases)}
- Total Verified Evidence Items: {len(evidence)}
- Verbatim Quote Audit Violations: {quote_mismatches} (Must be 0)
- Orphan Requirements: {len(orphan_reqs)}
- Open Critical Clarifications: {len(open_critical_qs)}

| Requirement ID | Type | Supporting Rules | Evidence Key | Test Scenarios | Status |
|---|---|---|---|---|---|
"""
        for req in requirements:
            rules_str = ", ".join(req.get("supporting_rule_keys", [])) or "None"
            ev_str = ", ".join(req.get("supporting_evidence_keys", [])) or "None"
            tests_for_req = [t["test_key"] for t in test_cases if t.get("requirement_id") == req["id"]]
            tests_str = ", ".join(tests_for_req) or "None"
            matrix_md += f"| {req.get('requirement_key')} | {req.get('type')} | {rules_str} | {ev_str} | {tests_str} | {req.get('status')} |\n"

        # Generate HLD / Solution Architecture Artifact
        hld_md = f"""# Solution Architecture / High-Level Design (HLD)
**Project:** {project.get('name')}
**Status:** DRAFT / NEEDS REVIEW
**Version:** 1.0

## 1. System Architecture
```mermaid
graph TD
    UI[Streamlit SaaS Frontend] -->|REST + Bearer Token| API[FastAPI Gateway]
    API --> AUTH[Authentication & Role Permission Engine]
    API --> ORCH[LangGraph State Workflow]
    ORCH --> PARSER[PyMuPDF / python-docx Parsing]
    ORCH --> LLM[Google Gemini Gateway]
    ORCH --> DB[(PostgreSQL 16 / Supabase)]
    ORCH --> AUDIT[Immutable SHA-256 Hash Chain]
```

## 2. Component Responsibilities
- **Frontend Layer:** Streamlit UI following SaaS reference design (Deep Navy #101F36, light background #F5F7FB, white cards).
- **Service Gateway:** FastAPI validating Pydantic schemas, minting project counters, and checking permissions.
- **Orchestration:** LangGraph state machine with deterministic routing, human-in-the-loop pauses, and bounded repair limits.
- **Persistence:** PostgreSQL 16 schema with strict CHECK constraints, Row Level Security, and UUID primary keys.

## 3. Security Boundaries
All document uploads stored in server-generated paths. Untrusted text wrapped in source delimiters. No raw passwords stored (bcrypt hashed).
"""
        # Generate Data Model / ERD Artifact
        erd_md = f"""# Data Model & Entity Relationship Specification
**Project:** {project.get('name')}
**Status:** DRAFT / NEEDS REVIEW

## 1. Core Relational Entities
- `users`: Registered accounts with display_name, email, bcrypt password_hash, and lockout counters.
- `projects`: Isolated project workspaces with process_type, status, and metadata.
- `project_members`: Strict mapping of users to project roles (Process Owner, Analyst, Technical Reviewer).
- `project_invitations`: Time-bounded (14-day) email invitations.
- `documents` & `document_sections`: Uploaded files with SHA-256 checksums and parsed sections.
- `evidence_items`: Verbatim quoted claims verified in code.
- `business_rules`: Structured conditions and outcomes; conflicting rules kept separate.
- `clarification_items`: Human questions with fingerprint deduplication and role assignment.
- `requirements`: Atomic requirements linked to evidence and rules.
- `test_cases`: Test scenarios linked directly to requirements.
- `audit_events`: Append-only table protected by SHA-256 hash chains.
"""
        # Process-specific HLD and data model from the approved steps. The older
        # fixed text is kept as an appendix (or used alone with no steps).
        pv = db.get_latest_process_version(project_id)
        pa_steps = pv.get("steps", []) if pv else []
        pa_rules = db.list_project_business_rules(project_id)
        hld_md = process_artifacts.hld_md(project, pa_steps, pa_rules, process_artifacts.as_appendix(hld_md)) or hld_md
        erd_md = process_artifacts.data_model_md(project, pa_steps, pa_rules, process_artifacts.as_appendix(erd_md)) or erd_md

        return {
            "documents": {
                "traceability_matrix": matrix_md,
                "hld": hld_md,
                "data_model": erd_md,
            },
            "is_valid": is_valid,
            "total_requirements": len(requirements),
            "orphan_requirements": orphan_reqs,
            "orphan_tests": orphan_tests,
            "quote_mismatches": quote_mismatches,
            "open_critical_questions": open_critical_qs
        }

    def _write_artifacts(self, project_id: str, report: Dict[str, Any]) -> None:
        """Persist the three quality documents. Only ever called from the run."""
        docs = report.get("documents", {})
        db.save_artifact(
            project_id, "traceability_matrix", docs.get("traceability_matrix", ""),
            content_json={
                "is_valid": report.get("is_valid"),
                "orphan_requirements": report.get("orphan_requirements", []),
                "quote_mismatches": report.get("quote_mismatches", 0),
            },
            status="draft",
        )
        db.save_artifact(project_id, "hld", docs.get("hld", ""), content_json={}, status="draft")
        db.save_artifact(project_id, "data_model", docs.get("data_model", ""), content_json={}, status="draft")

    def repair_orphan_requirements(self, project_id: str, orphan_keys: List[str]) -> int:
        """One deterministic repair pass over ungrounded requirements (SPEC-09-04).

        The repair is honest: a requirement with no supporting rule or evidence
        is marked `needs_clarification` and labelled, rather than being given an
        invented link. The loop that calls this is bounded to two attempts and
        then marks the run Needs Review.
        """
        repaired = 0
        for key in orphan_keys:
            if db.flag_requirement_needs_clarification(project_id, key):
                repaired += 1
                logger.info(f"Marked {key} as needs_clarification: no supporting rule or evidence.")
        return repaired


quality_agent = QualityAgent()
