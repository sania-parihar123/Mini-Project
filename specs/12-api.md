# 12 API Endpoints
Status: agreed
Source: Part 5.2, Part 5.2a [BASELINE + PROPOSED]

## Purpose
Expose modular, authenticated FastAPI endpoints handling projects, documents, runs, questions, approvals, artifacts, members, invitations, and audit logging with strict Pydantic schemas.

## Requirements
- SPEC-12-01 All endpoints under `/api` (except `/api/auth/register` and `/api/auth/login`) shall require an `Authorization: Bearer <token>` header containing a valid signed JWT / itsdangerous session token.
- SPEC-12-02 The API shall provide project endpoints:
  - `POST /api/projects`: Create project.
  - `GET /api/projects`: List user's active projects.
  - `GET /api/projects/{id}`: Get project details.
- SPEC-12-03 The API shall provide document endpoints:
  - `POST /api/projects/{id}/documents`: Upload source document (PDF, DOCX, TXT).
  - `GET /api/projects/{id}/documents`: List documents, parse status, and sections.
- SPEC-12-04 The API shall provide execution run endpoints:
  - `POST /api/projects/{id}/runs`: Start or resume analysis run.
  - `GET /api/runs/{id}`: Retrieve run status, stage, and state.
  - `POST /api/runs/{id}/cancel`: Cancel in-progress run.
- SPEC-12-05 The API shall provide question endpoints:
  - `GET /api/projects/{id}/questions`: List all project questions.
  - `GET /api/me/questions`: List questions waiting for current user's role across projects.
  - `POST /api/questions/{id}/answer`: Submit human answer (`answer` or `unknown`).
  - `POST /api/questions/{id}/escalate`: Escalate question from Analyst to Process Owner.
- SPEC-12-06 The API shall provide artifact & decision endpoints:
  - `GET /api/projects/{id}/artifacts`: List generated artifacts.
  - `GET /api/artifacts/{id}`: Retrieve artifact details and markdown/JSON.
  - `PATCH /api/artifacts/{id}`: Human edit saved as a new version.
  - `POST /api/process-versions/{id}/decision`: Approve/request changes/reject To-Be.
  - `GET /api/projects/{id}/traceability`: Query traceability matrix.
- SPEC-12-07 The API shall provide team & invitation endpoints:
  - `POST /api/projects/{id}/invitations`: Create invitation.
  - `GET /api/projects/{id}/members`: List active members and pending invitations.
  - `GET /api/me/invitations`: List pending invitations for authenticated user's email.
  - `POST /api/invitations/{id}/accept`: Accept project invitation.
  - `POST /api/invitations/{id}/decline`: Decline invitation.
  - `POST /api/invitations/{id}/revoke`: Revoke invitation.
  - `DELETE /api/projects/{id}/members/{user_id}`: Remove member.
  - `GET /api/projects/{id}/audit`: Fetch immutable audit events.

## Acceptance criteria
- AC-12-01 (covers SPEC-12-01) Given a request to `/api/projects` without a Bearer token, the API returns HTTP 401 Unauthorized.
- AC-12-02 (covers SPEC-12-02/03) Given an authenticated user, creating a project and uploading a `.txt` file returns HTTP 200/201 with parsed metadata.
- AC-12-03 (covers SPEC-12-05/06) Given an open question, an authorized role submitting an answer receives HTTP 200 with updated question status.

## Design notes
- Files: `app/api/auth.py`, `app/api/projects.py`, `app/api/documents.py`, `app/api/runs.py`, `app/api/questions.py`, `app/api/artifacts.py`, `app/api/team.py`, `app/api/traceability.py`, `app/main.py`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-12-01
  - `test_auth_and_project_lifecycle_e2e` (`tests/test_api.py`)
  - `test_health_check_endpoint` (`tests/test_api.py`)
  - `test_token_creation_and_expiration` (`tests/test_auth_permissions.py`)
- SPEC-12-02
  - `test_auth_and_project_lifecycle_e2e` (`tests/test_api.py`)
- SPEC-12-03
  - `test_auth_and_project_lifecycle_e2e` (`tests/test_api.py`)
  - `test_document_understanding_view_endpoint` (`tests/test_new_features.py`)
  - `test_several_files_upload_at_once_with_one_result_line_each` (`tests/test_uploads.py`)
- SPEC-12-04
  - `test_auth_and_project_lifecycle_e2e` (`tests/test_api.py`)
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
  - `test_background_run_execution_and_cancellation` (`tests/test_new_features.py`)
- SPEC-12-05
  - `test_answering_returns_immediately` (`tests/test_full_loop_e2e.py`)
  - `test_list_project_questions_returns_200_with_evidence_linked_questions` (`tests/test_questions_endpoint.py`)
  - `test_waiting_for_me_returns_200_with_evidence_linked_questions` (`tests/test_questions_endpoint.py`)
- SPEC-12-06
  - `test_srs_artifact_generation` (`tests/test_api.py`)
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
- SPEC-12-07
  - `test_team_invitation_revocation_and_member_removal` (`tests/test_api.py`)
  - `test_invitation_can_be_resent_within_the_limit` (`tests/test_security_hardening.py`)
