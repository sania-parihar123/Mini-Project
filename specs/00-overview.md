# 00 Overview
Status: agreed
Source: Part 1 (Summary, Core Principle, Scope, Definition of Done), Part 5.3 (Roles) [BASELINE]

## Purpose
ProcessFoundry AI helps college teams discover, analyze, and redesign any college administrative or academic process from unstructured evidence, producing verified As-Is flows, resolving ambiguities through human-in-the-loop clarification, assessing automation potential, and generating linked engineering specifications.

## Requirements
- SPEC-00-01 The system shall support any college administrative or academic process (e.g. scholarships, admissions, hostel allotment, revaluation, NOCs) with no process-specific hardcoded branching.
- SPEC-00-02 The model shall propose outputs; deterministic application code shall validate; authorized human roles shall approve critical business changes.
- SPEC-00-03 The system shall never auto-approve AI generated models, rules, or requirements. All AI outputs start in `draft`, `needs_review`, or `needs_clarification`.
- SPEC-00-04 The system shall support three distinct project roles: Process Owner (domain authority), Analyst (project manager/discovery lead), and Technical Reviewer (architecture/engineering verifier).
- SPEC-00-05 The system shall maintain an end-to-end traceability chain connecting source documents, evidence items, business rules, process steps, requirements, and test cases.

## Acceptance criteria
- AC-00-01 (covers SPEC-00-01) Given documents from two distinct college processes (e.g. scholarship vs hostel allotment), when ingested and processed by the pipeline, then the same code and prompts extract and structure both without process-specific conditions.
- AC-00-02 (covers SPEC-00-02/03) Given an automated analysis run, when the run finishes, then all candidate rules and requirements have `status = 'draft'` or `'needs_review'` and `approved_by = NULL`.
- AC-00-03 (covers SPEC-00-04) Given a project workspace, when members join, each member has an assigned project role with distinct permission boundaries.

## Design notes
- Files: `app/main.py`, `app/schemas/process.py`, `app/core/config.py`.
- Out of scope: Direct production SIS/ERP/payment gateway writes, autonomous student acceptance/rejection, OCR of illegible handwriting.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-00-01
  - `test_the_same_code_handles_both_processes_with_no_branch` (`tests/test_fixture_defect_coverage.py`)
  - `test_conflict_question_wording_is_not_process_specific` (`tests/test_questions_endpoint.py`)
- SPEC-00-02
  - `test_ai_can_never_set_approved` (`tests/test_security_hardening.py`)
- SPEC-00-03
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
  - `test_ai_can_never_set_approved` (`tests/test_security_hardening.py`)
  - `test_regenerating_does_not_discard_an_approval` (`tests/test_security_hardening.py`)
- SPEC-00-04
  - `test_permission_matrix_enforcement` (`tests/test_auth_permissions.py`)
  - `test_the_permission_matrix_still_enforces_the_brief` (`tests/test_security_hardening.py`)
- SPEC-00-05
  - `test_every_spec_id_has_a_covering_test` (`tests/test_spec_coverage.py`)
  - `test_the_traceability_chain_links_source_to_test` (`tests/test_spec_coverage.py`)
