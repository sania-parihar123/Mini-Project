# 14 Roles, Accounts, and Access Control
Status: agreed
Source: Part 7.3, Part 7.4, Part 7.9, Part 7.11 [TEAM DECISION: REQUIRED]

## Purpose
Enforce user registration, password hashing, signed sessions, project-level role assignment, invitation lifecycles, and strict permission matrix checking across all backend actions.

## Requirements
- SPEC-14-01 User registration shall validate: display name, valid email (lowercased, unique), password >= 8 chars and not equal to email. Passwords shall be hashed with `bcrypt`.
- SPEC-14-02 Sign-in shall verify credentials. Failed attempts shall be tracked: 5 sequential failures shall lock the account for 10 minutes. A generic error ("E-mail or password is incorrect") shall be returned on any bad credential.
- SPEC-14-03 The backend shall generate an 8-hour signed session token. Every protected request shall authenticate the token and load the caller's active project role from `project_members`.
- SPEC-14-04 Project creator and active Process Owners can invite teammates by email with a designated role (`process_owner`, `analyst`, `technical_reviewer`). Invitations expire in 14 days.
- SPEC-14-05 An invitation can ONLY be accepted by an account matching the invited email address. Non-members cannot view any project documents, questions, or artifacts.
- SPEC-14-06 The permission matrix (Part 7.9) shall be deterministically enforced on every endpoint:
  - Create project: any signed-in user.
  - View project, docs, artifacts: active members of that project.
  - Invite teammates / remove members: Process Owner, or project creator.
  - Upload docs / start run: Process Owner or Analyst.
  - Answer question: only member whose role matches the question's `assigned_role`.
  - Approve business rule / resolve conflict: Process Owner only.
  - Approve / reject To-Be process: Process Owner only.
  - Approve BRD, PRD, FRD, rules catalogue, roles matrix, workflow: Process Owner only.
  - Approve architecture, data model, API spec, test plan, UAT pack: Technical Reviewer only.
  - Rejecting any artifact requires a non-empty comment.

## Acceptance criteria
- AC-14-01 (covers SPEC-14-01/02) Given an existing user, attempting to register again with the same email (case-insensitive) fails with an error. 5 wrong passwords lock the account.
- AC-14-02 (covers SPEC-14-04/05) Given an invitation sent to `rao@example.com`, when `aditi@example.com` attempts to accept it, the request is rejected with HTTP 403.
- AC-14-03 (covers SPEC-14-06) Given a user with role `analyst`, when attempting to approve a business rule or the To-Be process, the request is rejected with HTTP 403 Forbidden ("Only a Process Owner can approve a business rule").
- AC-14-04 (covers SPEC-14-06) Given a user with role `process_owner`, when attempting to approve the solution architecture or test plan, the request is rejected with HTTP 403 Forbidden ("Only a Technical Reviewer can approve architecture/tests").

## Design notes
- Files: `app/api/auth.py`, `app/api/team.py`, `app/services/permissions.py`, `app/repositories/users.py`, `app/repositories/projects.py`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-14-01
  - `test_auth_and_project_lifecycle_e2e` (`tests/test_api.py`)
  - `test_password_hashing_and_verification` (`tests/test_auth_permissions.py`)
  - `test_user_registration_duplicate_email_rejected` (`tests/test_auth_permissions.py`)
  - `test_user_registration_success` (`tests/test_auth_permissions.py`)
- SPEC-14-02
  - `test_user_lockout_after_five_failed_attempts` (`tests/test_auth_permissions.py`)
  - `test_user_login_success_and_failure` (`tests/test_auth_permissions.py`)
- SPEC-14-03
  - `test_auth_and_project_lifecycle_e2e` (`tests/test_api.py`)
  - `test_token_creation_and_expiration` (`tests/test_auth_permissions.py`)
  - `test_a_role_change_takes_effect_immediately` (`tests/test_security_hardening.py`)
  - `test_membership_and_role_are_read_fresh_on_every_request` (`tests/test_security_hardening.py`)
- SPEC-14-04
  - `test_team_invitation_revocation_and_member_removal` (`tests/test_api.py`)
  - `test_invitation_can_be_resent_within_the_limit` (`tests/test_security_hardening.py`)
  - `test_the_daily_invitation_cap_is_enforced` (`tests/test_security_hardening.py`)
- SPEC-14-05
  - `test_team_invitation_revocation_and_member_removal` (`tests/test_api.py`)
  - `test_batch_upload_is_closed_to_non_members` (`tests/test_uploads.py`)
- SPEC-14-06
  - `test_permission_matrix_enforcement` (`tests/test_auth_permissions.py`)
  - `test_an_unclassified_artifact_type_cannot_be_approved` (`tests/test_security_hardening.py`)
  - `test_an_unknown_action_is_denied_for_every_role` (`tests/test_security_hardening.py`)
  - `test_approve_artifact_with_no_type_is_denied` (`tests/test_security_hardening.py`)
  - `test_cors_allows_the_configured_front_end` (`tests/test_security_hardening.py`)
  - `test_every_generated_artifact_type_is_classified` (`tests/test_security_hardening.py`)
  - `test_only_someone_who_may_invite_can_resend` (`tests/test_security_hardening.py`)
  - `test_the_permission_matrix_still_enforces_the_brief` (`tests/test_security_hardening.py`)
  - `test_batch_upload_respects_the_permission_matrix` (`tests/test_uploads.py`)
