# ProcessFoundry AI: Implementation Tasks

This task list is derived from the master build brief and numbered specifications in `specs/`. Each task links to its corresponding specification requirements and acceptance criteria.

---

## Phase 0: Foundations, Architecture & Configuration

- [x] **TASK-001: Project Layout and Configuration**
  - **Spec:** `specs/00-overview.md` (SPEC-00-01, SPEC-00-02), `specs/16-visual-design.md`
  - **Outputs:** `pyproject.toml`, `.env.example`, `.streamlit/config.toml`, directory structure (`app/`, `tests/`, `scripts/`).
  - **Criteria:** AC-00-01, AC-16-01

- [x] **TASK-002: PostgreSQL Schema and Database Layer**
  - **Spec:** `specs/01-database.md` (SPEC-01-01 to SPEC-01-06)
  - **Outputs:** `schema.sql`, `app/core/config.py`, `app/repositories/base.py`, `app/repositories/database.py`, `scripts/check_db.py`.
  - **Criteria:** AC-01-01, AC-01-02, AC-01-03, AC-01-04

- [x] **TASK-003: LLM Gateway and Structured Output Service**
  - **Spec:** `specs/02-llm-service.md` (SPEC-02-01 to SPEC-02-06)
  - **Outputs:** `app/services/llm_service.py` (Gemini SDK adapter + Mock test adapter, JSON schema enforcement, bounded retries).
  - **Criteria:** AC-02-01, AC-02-02, AC-02-03, AC-02-04

- [x] **TASK-004: Core Pydantic Schemas**
  - **Spec:** `specs/04-evidence.md`, `specs/05-process-discovery.md`, `specs/06-rules.md`, `specs/07-gaps-and-questions.md`, `specs/10-requirements-documents.md`
  - **Outputs:** `app/schemas/process.py`, `app/schemas/evidence.py`, `app/schemas/rules.py`, `app/schemas/clarification.py`, `app/schemas/requirements.py`, `app/schemas/artifacts.py`, `app/schemas/team.py`.
  - **Criteria:** AC-04-01, AC-05-01, AC-06-01, AC-07-01, AC-10-01

---

## Phase 1: Ingestion, Evidence, Discovery, Gaps, Auth & UI Foundations

- [x] **TASK-005: Multi-Format Document Ingestion Service**
  - **Spec:** `specs/03-ingestion.md` (SPEC-03-01 to SPEC-03-05)
  - **Outputs:** `app/services/document_parser.py` (PDF via PyMuPDF, DOCX via python-docx, TXT, section heading detector, chunker).
  - **Criteria:** AC-03-01, AC-03-02, AC-03-03

- [x] **TASK-006: Verbatim Evidence Extraction Agent (A2)**
  - **Spec:** `specs/04-evidence.md` (SPEC-04-01 to SPEC-04-04)
  - **Outputs:** `app/agents/evidence.py`, substring verification logic, `EVD-nnn` key minting.
  - **Criteria:** AC-04-01, AC-04-02

- [x] **TASK-007: As-Is Process Discovery Agent (A3)**
  - **Spec:** `specs/05-process-discovery.md` (SPEC-05-01 to SPEC-05-04)
  - **Outputs:** `app/agents/discovery.py`, unnamed actor handling (`actor = NULL`, unknowns tracking), `STEP-nnn` keys.
  - **Criteria:** AC-05-01, AC-05-02

- [x] **TASK-008: Business Rule Analysis Agent (A4)**
  - **Spec:** `specs/06-rules.md` (SPEC-06-01 to SPEC-06-04)
  - **Outputs:** `app/agents/rules.py`, per-section rule extraction, separate conflict row retention, `BR-nnn` keys.
  - **Criteria:** AC-06-01, AC-06-02

- [x] **TASK-009: Gap & Conflict Analysis with Deterministic Detection (A5)**
  - **Spec:** `specs/07-gaps-and-questions.md` (SPEC-07-01 to SPEC-07-05)
  - **Outputs:** `app/agents/gaps.py`, deterministic detectors for missing actors, conflicting dates/rules, ambiguous terms, `Q-nnn` keys, role routing.
  - **Criteria:** AC-07-01, AC-07-02, AC-07-03

- [x] **TASK-010: Authentication, Project Membership & Permission Engine**
  - **Spec:** `specs/14-roles-and-access.md` (SPEC-14-01 to SPEC-14-06)
  - **Outputs:** `app/api/auth.py`, `app/api/team.py`, `app/services/permissions.py`, `app/repositories/users.py`, password hashing, session tokens, lockout logic, invitation lifecycle.
  - **Criteria:** AC-14-01, AC-14-02, AC-14-03, AC-14-04

- [x] **TASK-011: LangGraph Orchestrator & HITL Checkpoint Engine**
  - **Spec:** `specs/09-graph-and-routing.md` (SPEC-09-01 to SPEC-09-05), `specs/08-human-in-the-loop.md`
  - **Outputs:** `app/graph/state.py`, `app/graph/routing.py`, `app/graph/build_graph.py`, state serialization in `runs.state_json`, pause on critical questions.
  - **Criteria:** AC-08-01, AC-09-01, AC-09-02, AC-09-03

- [x] **TASK-012: FastAPI Core Endpoints**
  - **Spec:** `specs/12-api.md` (SPEC-12-01 to SPEC-12-07)
  - **Outputs:** `app/api/projects.py`, `app/api/documents.py`, `app/api/runs.py`, `app/api/questions.py`, `app/main.py`.
  - **Criteria:** AC-12-01, AC-12-02, AC-12-03

- [x] **TASK-013: Split-Screen Auth & Workspace Shell in Streamlit**
  - **Spec:** `specs/13-ui.md` (SPEC-13-01 to SPEC-13-05), `specs/16-visual-design.md`
  - **Outputs:** `app/ui/theme.py`, `app/ui/components.py`, `app/ui/streamlit_app.py`, split-screen login/register, navy sidebar, header, My Projects dashboard.
  - **Criteria:** AC-13-01, AC-16-01, AC-16-02

---

## Phase 2: Human Answers, Requirements, BRD/FRD/PRD & Traceability

- [x] **TASK-014: Human-in-the-Loop Clarification Handler (A6)**
  - **Spec:** `specs/08-human-in-the-loop.md` (SPEC-08-01 to SPEC-08-05)
  - **Outputs:** `app/agents/hitl.py`, answer validation, `verified_facts` minting (`FACT-nnn`), rule superseding, run resumption.
  - **Criteria:** AC-08-02, AC-08-03

- [x] **TASK-015: Requirements Engineering & Multi-Artifact Generator (A9)**
  - **Spec:** `specs/10-requirements-documents.md` (SPEC-10-01 to SPEC-10-06)
  - **Outputs:** `app/agents/requirements.py`, `app/services/artifact_export.py`, generating BRD, FRD, PRD, and SRS with mandatory headings.
  - **Criteria:** AC-10-01, AC-10-02

- [x] **TASK-016: Traceability Validator & Audit Event Hash Chaining (A13)**
  - **Spec:** `specs/11-traceability.md` (SPEC-11-01 to SPEC-11-05), `specs/01-database.md`
  - **Outputs:** `app/agents/quality.py`, `app/api/traceability.py`, SHA-256 event chaining for audit trail.
  - **Criteria:** AC-11-01, AC-11-02, AC-11-03, AC-11-04

---

## Phase 3: To-Be Redesign, Automation Assessment, Workflow, Tests & Complete UI

- [x] **TASK-017: Process Redesign & Automation Assessment (A7, A8)**
  - **Spec:** `specs/10-requirements-documents.md` (SPEC-10-05), `specs/00-overview.md`
  - **Outputs:** `app/agents/redesign.py`, step classification (`deterministic`, `ai_assisted`, `human`, `hybrid`), human approval endpoint.
  - **Criteria:** AC-00-02, AC-10-01

- [x] **TASK-018: Test and UAT Scenario Generator (A12)**
  - **Spec:** `specs/10-requirements-documents.md` (SPEC-10-06)
  - **Outputs:** `app/agents/testing.py`, generating positive, negative, boundary, and journey tests linked to requirement IDs.
  - **Criteria:** AC-10-03

- [x] **TASK-019: Complete Streamlit Workspace UI (All Pages & Workflows)**
  - **Spec:** `specs/13-ui.md`, `specs/16-visual-design.md`, Section 10.9
  - **Outputs:** Streamlit pages for Project Overview (first-class upload section), Waiting for Me, Sources, Discovery, Questions & Rules, Redesign & Approval, Documents (BRD/FRD/PRD), Workflow & Traceability, Team & Invitations, and Audit Log.
  - **Criteria:** AC-13-02, AC-13-03, AC-16-01

---

## Phase 4: Test Fixtures, Test Suite, Scripts & Documentation

- [x] **TASK-020: Multi-Process Test Fixtures & Seeding Scripts**
  - **Spec:** `specs/15-test-data-and-demo.md` (SPEC-15-01 to SPEC-15-04)
  - **Outputs:** `tests/fixtures/scholarship_sop.txt`, `tests/fixtures/hostel_allotment_policy.txt`, `tests/fixtures/manifest.json`, `scripts/seed_demo.py`, `scripts/check_db.py`.
  - **Criteria:** AC-15-01, AC-15-02

- [x] **TASK-021: Comprehensive Pytest Test Suite**
  - **Spec:** All specs
  - **Outputs:** `tests/test_parsing.py`, `tests/test_evidence.py`, `tests/test_rules_gaps.py`, `tests/test_auth_permissions.py`, `tests/test_graph_routing.py`, `tests/test_api.py`, `tests/test_traceability.py`.
  - **Criteria:** All ACs proven by automated tests.

- [x] **TASK-022: Production README and Run Scripts**
  - **Spec:** `specs/00-overview.md`, `DEVIATIONS.md`
  - **Outputs:** `README.md`, `scripts/run_dev.ps1` / `scripts/run_dev.sh`.
