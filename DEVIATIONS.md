# ProcessFoundry AI — Recorded Deviations and Team Decisions

All items below reflect deliberate team decisions from the build brief (`PROCESSFOUNDRY_BUILD_BRIEF_UPDATED_UI.md`) and technical adaptations to ensure a robust, runnable application.

## 1. Real User Accounts, Authentication, and Session Security [TEAM DECISION: Part 7.3]
- **Baseline (Design doc 5.3):** Simple client-side role labels.
- **Team Decision (Part 7.3):** Every user registers and signs in with an email and password.
- **Implementation:** Passwords hashed with secure `bcrypt` (`$2b$`). 8-hour signed session tokens via `itsdangerous` passed in `Authorization: Bearer` headers. 5 failed login attempts trigger a 10-minute account lockout (`users.failed_attempts`, `users.locked_until`). Generic error message on invalid credentials ("E-mail or password is incorrect").

## 2. Project-Specific Roles, Membership, and Invitations [TEAM DECISION: Part 7.4 & 7.9]
- **Baseline:** Single global role per user.
- **Team Decision:** Roles belong to each person *inside a project* (`project_members`). Users can hold different roles in different projects.
- **Implementation:** Project creator invites teammates by email with an assigned role. Invitations expire in 14 days and can be accepted/declined/revoked. Permission matrix (Part 7.9) deterministically enforced on every backend API route.

## 3. UI Visual Design Reference Override [TEAM DECISION: Section 10.9]
- **Baseline (Part 10.1–10.8):** Marked-up proofread document visual style with yellow highlighter / red pen / Literata serif defaults.
- **Team Decision (Section 10.9):** Visual presentation overridden to follow the attached clickable SaaS prototype (`processfoundry_ai_professional_clickable_prototype.html`):
  - Deep navy navigation sidebar (`#101F36`) with clear active states and system status.
  - Light grey-blue background (`#F5F7FB`), dark navy text (`#15243A`), clean Inter sans-serif typography.
  - Blue primary actions (`#3568F5`), supporting teal accents (`#0D9B8A`).
  - White cards with subtle borders (`#E5EAF1`), restrained shadows, and 12-15px border radii.
  - Split-screen auth layout (branded navy/teal visual panel on right, clean form on left).
  - First-class drag-and-drop / file upload section directly on the Project Overview page.

## 4. Human-In-The-Loop Execution & Checkpoint State [Part 3.6 & Part 6 Phase 1]
- **Baseline:** LangGraph interrupt/checkpoint.
- **Implementation:** LangGraph orchestrator graph with persistent state checkpointing in `runs.state_json` and run status `waiting_for_human`. When critical clarification questions (conflicting rules, missing actors) are open, the graph pauses, saves state, and resumes upon human answer submission.

## 5. Database Resilience & Dual-Mode Repository Layer [Part 6 Phase 0 & Part 8.8]
- **Baseline:** Direct PostgreSQL on Supabase using `DATABASE_URL`.
- **Implementation:** The backend connects to PostgreSQL via `psycopg` when `DATABASE_URL` is configured. To ensure zero-friction local development, reproducible automated testing (`pytest`), and offline operation, an automatic SQLite database repository is included as a fallback when `DATABASE_URL` is unset or unavailable. Both adapters implement the identical project-scoped repository interface and enforce constraints.

---

## Corrections and additions made while fixing the findings in `REVIEW_REPORT.md`

### 6. Correction to item 5: the SQLite mirror does **not** enforce the schema's constraints
Item 5 above claimed that "Both adapters implement the identical project-scoped
repository interface and enforce constraints." That was wrong, and the claim is
withdrawn.

- `schema.sql` carries **40 `CHECK` constraints**, an append-only trigger on
  `audit_events` (blocking `UPDATE` and `DELETE`) and Row Level Security on every
  table. The SQLite mirror in `app/repositories/database.py` implements **none** of
  them: it mirrors the table and column layout only.
- Consequence: the approval rule `CHECK (status <> 'approved' OR approved_by IS
  NOT NULL)` and the immutability of the audit log hold **only on PostgreSQL**.
- Mitigation: the application layer enforces the approval rule itself
  (`update_rule_status`, `update_artifact_status`, `update_process_version_decision`
  all raise `ValueError` when `approved` is requested without an approver), and
  `tests/test_spec_coverage.py` carries PostgreSQL-only tests for the constraint
  and trigger semantics. Those tests **skip** unless `PFAI_TEST_POSTGRES_URL`
  points at a throwaway database, and the skip message says exactly why.
- The SQLite fallback remains restricted to test environments
  (`ALLOW_SQLITE=true` or `APP_ENV=test`); a normal start without `DATABASE_URL`
  still fails fast.

### 7. Schema additions [EXTENSION, minimal]
Three additions to `schema.sql`, each mirrored in the SQLite layer and applied to
an existing PostgreSQL database by the idempotent migrations in
`_run_postgres_migrations`:

1. `document_sections.read_from_image BOOLEAN NOT NULL DEFAULT FALSE` — the text
   of this section was read from a page image rather than a text layer, so the UI
   can show the "Read from images, check the wording" notice (brief 10.9, review
   item 5).
2. `document_sections.extracted_by TEXT` — the extractor version that last mined
   this section. This is what lets a re-run skip unchanged sections instead of
   repeating every model call and duplicating every row, as brief Phase 0 step 3
   requires ("remember results already stored so a re-run does not repeat calls
   for unchanged sections").
3. `document_understanding` (a new, 29th table) — the cached "What I understood"
   view per document, keyed by content checksum. Derived data only: it can be
   deleted at any time and is recomputed on the next read. Without it the panel
   fired one model call per document on every page render.

`clarification_items.kind` also gained `'duplicate_step'`, so the repeated-step
detector that brief 9.1 and `tests/fixtures/manifest.json` both require can store
its questions. `scripts/check_db.py` now expects 29 tables.

### 8. Two "waiting" states share one run status
`runs.status` allows only `created, running, waiting_for_human, completed, failed,
cancelled`. The run now stops twice — once for clarification and once for the
Process Owner's To-Be decision (brief 3.5 and 7.11 step 5) — and both are
genuinely "waiting for a human". Rather than widen the constraint, both use
`status = 'waiting_for_human'` and are told apart by `runs.current_node`
(`waiting_for_human` vs `waiting_for_to_be_approval`). The UI reads
`current_node` to say which action is needed.

### 9. The specs' "Tests" sections are generated, not hand-written
The specs previously named 32 pytest functions, none of which existed. Each spec's
`## Tests` section is now generated from the suite: every test cites the `SPEC-`
and `AC-` ids it proves in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if any
declared requirement loses its coverage. Regenerate with the script described in
`CHANGES.md` after adding tests.

### 10. `.venv` is not part of the project
The committed `.venv` was created on Windows (`pyvenv.cfg` points at
`C:\Users\ASUS\...\cpython-3.12-windows-x86_64`) and cannot be used on macOS or
Linux. It is listed in `.gitignore`; create a fresh virtual environment locally
rather than using it.
