# 10 Requirements and Documents Engineering
Status: agreed
Source: Part 3.1 (A7, A8, A9, A11, A12), Part 4.1, Part 4.5 [BASELINE]

## Purpose
Synthesize verified process models and rules into structured requirements (BRD, FRD, PRD, SRS) and engineering deliverables (workflow JSON, test scenarios, UAT pack) from a single shared relational data model.

## Requirements
- SPEC-10-01 Requirements shall be stored as distinct records in `requirements` with keys `REQ-nnn` and types `business`, `functional`, `non_functional`, `workflow`.
- SPEC-10-02 Every requirement shall be linked to supporting evidence, rules, steps, or verified facts in `requirement_links`.
- SPEC-10-03 Requirements affected by unanswered or unknown questions shall be marked `needs_clarification` and clearly state "Not stated in the source documents. Needs clarification."
- SPEC-10-04 Downstream specification documents (BRD, FRD, PRD) shall be compiled from the structured requirement records using standard required headings:
  - BRD: Purpose, Business Problem, Goals, Scope, Stakeholders, Current Process, Business Needs, Business Rules, Constraints, Assumptions, Risks, Success Measures, Approvals.
  - PRD: Product Goal, Personas, User Problems, Features, User Stories, Priorities, Acceptance Criteria, Dependencies, Non-Functional Needs, Open Questions.
  - FRD: System Overview, Actors/Roles, Functional Requirements, Workflow, Decision Rules, Validations, Exceptions, Notifications, Permissions, Audit Events, External Interfaces, Acceptance Criteria.
- SPEC-10-05 Workflow JSON shall define steps, actors, automation classifications (`deterministic`, `ai_assisted`, `human`, `hybrid`), rules, inputs, outputs, and transitions.
- SPEC-10-06 Test cases (`TEST-nnn`) and UAT scenarios shall be generated from requirements, with every test linked to a specific requirement (`requirement_id`).

## Acceptance criteria
- AC-10-01 (covers SPEC-10-01/02) Given an automated generation run, all generated requirements in `requirements` have valid links in `requirement_links` to supporting rules or steps.
- AC-10-02 (covers SPEC-10-04) Given generated BRD, FRD, and PRD artifacts, each document includes the standard required headings and carries a Draft / Needs Review status.
- AC-10-03 (covers SPEC-10-06) Given generated test cases, each test case has a non-null `requirement_id` referencing a requirement record.

## Design notes
- Files: `app/agents/requirements.py`, `app/agents/redesign.py`, `app/agents/testing.py`, `app/services/artifact_export.py`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-10-01
  - `test_srs_artifact_generation` (`tests/test_api.py`)
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
- SPEC-10-02
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
  - `test_orphan_requirement_detected` (`tests/test_traceability.py`)
- SPEC-10-03
  - `test_mark_unknown_unblocks_the_run` (`tests/test_full_loop_e2e.py`)
- SPEC-10-04
  - `test_srs_artifact_generation` (`tests/test_api.py`)
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
- SPEC-10-05
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
- SPEC-10-06
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
