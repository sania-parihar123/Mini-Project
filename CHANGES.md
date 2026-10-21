# CHANGES — fixes for the findings in `REVIEW_REPORT.md`

**Written for:** whoever maintains this codebase next, and the reviewer who wrote `REVIEW_REPORT.md`.

**Final test result:** `176 passed, 3 skipped` on **Python 3.14.7**, run with the real
`.env` in place and no shell overrides. The 3 skips are the PostgreSQL-only
constraint tests (no local PostgreSQL available — see [Phase 7](#phase-7) and
[Not done](#what-i-could-not-do)).

Nothing below is claimed as fixed unless a test listed beside it passes. The brief's
rules were not changed: the model proposes and code validates, evidence quotes stay
verbatim substrings of their source, conflicting rules stay as separate rows, an
unknown actor stays `NULL`, the AI never sets `approved`, and project isolation and
the permission matrix are unchanged (and now have more tests than before).

| Baseline | Now |
|---|---|
| 52 tests | **179 collected — 176 passed, 3 skipped** |
| `pytest` wrote to the live Supabase database | refuses to start if it could reach any real database |
| Questions page returned HTTP 500 | HTTP 200 with the full brief 7.12 source block |
| Answering never closed the loop; 0 documents | loop closes; all 12 documents generated |
| Every run duplicated all rows and re-billed the model | re-run adds 0 rows and makes 0 model calls |
| 3 of 5 planted defect classes detected | 5 of 5, in both fixtures |
| 32 spec-named tests, none of which existed | every spec requirement cites a real, passing test |

---

## Phase 0 — Make the tests safe (F2)

| Change | Where |
|---|---|
| `.env` loading can be switched off, so a test run cannot pick up a real credential | [app/core/config.py:18-22](app/core/config.py#L18-L22) (`dotenv_disabled`, `_ENV_FILE`) |
| Session-wide isolation: temp SQLite, temp upload dir, offline model, all forced before any app import | [tests/conftest.py:26-42](tests/conftest.py#L26-L42) |
| The suite **refuses to start** if `settings.database_url` is non-empty or the repository is in PostgreSQL mode, unless `ALLOW_LIVE_DB_TESTS=1` | [tests/conftest.py:48-78](tests/conftest.py#L48-L78) (`check_no_live_database`, `pytest_configure`) |
| Opening a `psycopg_pool.ConnectionPool` during tests is a hard failure | [tests/conftest.py:81-104](tests/conftest.py#L81-L104) |
| Per-test SQLite database, autouse and unconditional, so no test file can forget it | [tests/conftest.py:107-120](tests/conftest.py#L107-L120) |
| Importing the repository no longer creates `data/processfoundry.db`; the schema is built lazily on first use | [app/repositories/database.py:27-41](app/repositories/database.py#L27-L41), [:96-99](app/repositories/database.py#L96-L99) |
| `is_test_environment()` is now one shared definition used by both the database and model guards, and honours `.env` as the README documents | [app/core/config.py:95-120](app/core/config.py#L95-L120) |

**Proven by** `tests/test_test_isolation.py` (12 tests), notably
`test_settings_cannot_see_a_database_url_from_dotenv` — the exact hole that caused
F2 — `test_guard_refuses_a_non_empty_database_url_without_opt_in`, and
`test_init_pool_never_opens_postgres_during_tests`.

**Measured effect:** the suite runs in ~22 s against temporary SQLite. Before, the
same suite took 48.87 s because it was reaching Tokyo.

---

## Phase 1 — Unblock the question flow (F1, F12)

| Change | Where |
|---|---|
| `linked_evidence` returns objects (`id`, `evidence_key`, `quote`, `document_name`, `section_index`, `section_title`, `page_number`), not bare id strings | [app/repositories/database.py:1821-1893](app/repositories/database.py#L1821-L1893) (`_rows_to_clarification_items`) |
| Response model matches, and gained `project_name`, `consequence_summary`, typed `options` and `ClarificationSource` | [app/schemas/clarification.py:21-68](app/schemas/clarification.py#L21-L68) |
| The N+1 is gone: one JOINed projection loads items, links and full evidence context | [app/repositories/database.py:1778-1805](app/repositories/database.py#L1778-L1805) (`_CLARIFICATION_SELECT`) |
| "Waiting for me" reuses the same projection, keeping its membership-and-role join | [app/repositories/database.py:1927-1949](app/repositories/database.py#L1927-L1949) |
| `consequence_summary` is derived deterministically from the question kind and its links — code, not model text, and no schema change | [app/repositories/database.py:1793-1819](app/repositories/database.py#L1793-L1819) |
| Source context for steps, rules and evidence, each in one query | [app/repositories/database.py:1474-1536](app/repositories/database.py#L1474-L1536) (`get_step_sources`, `get_evidence_sources`, rule `sources`) |
| **The UI no longer swallows errors.** Every `return resp.json() if status == 200 else []` is gone; non-200 raises `APIError` with the server's own message | [app/ui/api_client.py:9-59](app/ui/api_client.py#L9-L59) (`APIError`, `_unwrap`) — 30 call sites converted |
| A shared renderer puts all six brief 7.12 items on screen: project name, key, question, why it matters, lettered sources with quote/document/section/page, the choices, and what happens on confirm | [app/ui/components.py:88-165](app/ui/components.py#L88-L165) (`question_context_html`) |
| Both the "Waiting for me" and "Questions & Rules" pages use it | [app/ui/streamlit_app.py](app/ui/streamlit_app.py) |

**Proven by** `tests/test_questions_endpoint.py` (8 tests):
`test_list_project_questions_returns_200_with_evidence_linked_questions`,
`test_waiting_for_me_returns_200_with_evidence_linked_questions`,
`test_every_question_carries_the_context_brief_7_12_requires`,
`test_conflicting_rules_question_shows_both_passages_with_letters`, and
`test_question_list_costs_one_query_regardless_of_question_count`, which asserts
**exactly 1** query for a list that previously cost 60.

---

## Phase 2 — Make answering finish the run (F3, F6)

This is the central fix.

### Stable fingerprints
Fingerprints are built from durable identity — document, section index, normalised
text — never from row UUIDs: [app/agents/gaps.py:105-139](app/agents/gaps.py#L105-L139)
(`_norm`, `_source_key`, `fingerprint`), used at each detector.

### A real resume, in the background
The graph is now three compiled segments, and resuming re-enters at the start of the
next one instead of at `ingest`: [app/graph/build_graph.py](app/graph/build_graph.py).

```
segment 1  ingest → evidence → as_is → rules → gaps → [pause for clarification]
segment 2  gaps_recheck → to_be → [pause for To-Be approval]
segment 3  requirements → testing → quality → (≤2 repairs) → complete
```

| Change | Where |
|---|---|
| `resume_run_after_clarification` continues the **same** run from `gaps_recheck`, which only reloads open questions — no extraction, no model call | [app/graph/build_graph.py:470-481](app/graph/build_graph.py#L470-L481), [:145-158](app/graph/build_graph.py#L145-L158) |
| The answer endpoint dispatches it as a background task, so the request returns at once | [app/api/questions.py:54-72](app/api/questions.py#L54-L72) |
| `start_or_resume_project_run` (which created a new run from `ingest`) is no longer called from any request path | [app/graph/build_graph.py:497-506](app/graph/build_graph.py#L497-L506) |
| Checkpoint and restore: bulky state is reloaded from the database rather than stored in `runs.state_json` | [app/graph/build_graph.py:371-410](app/graph/build_graph.py#L371-L410) |

### Idempotent runs
| Change | Where |
|---|---|
| A section already mined by the current `EXTRACTOR_VERSION` is skipped; its stored evidence is reused | [app/agents/evidence.py:58-82](app/agents/evidence.py#L58-L82) |
| Same for rules | [app/agents/rules.py:79-96](app/agents/rules.py#L79-L96) |
| `document_sections.extracted_by` records the version that mined each section | `schema.sql`, SQLite mirror, and `_run_postgres_migrations` |
| The As-Is model is reused when the evidence signature is unchanged; changed evidence creates a **new version** and marks dependants stale, never an overwrite | [app/agents/discovery.py:12-26](app/agents/discovery.py#L12-L26), [:46-75](app/agents/discovery.py#L46-L75) |
| `mark_dependants_stale` moves dependent artifacts, requirements and process versions to `stale`/`needs_review` and writes an audit event | [app/repositories/database.py:2505-2545](app/repositories/database.py#L2505-L2545) |

### Interrupted runs
`reconcile_interrupted_runs` marks runs left at `running` as `failed` with a plain
reason, called from startup:
[app/repositories/database.py:2547-2578](app/repositories/database.py#L2547-L2578),
[app/main.py:30-42](app/main.py#L30-L42).

### Bounded repair and the To-Be gate
| Change | Where |
|---|---|
| `quality_repair_router` is finally **wired into the graph**: `quality → {complete, repair, needs_review}`, `repair → quality`, at most 2 attempts | [app/graph/build_graph.py:413-440](app/graph/build_graph.py#L413-L440) |
| The repair is honest: an ungrounded requirement is marked `needs_clarification` with the brief's wording, never given an invented link | [app/agents/quality.py](app/agents/quality.py) (`repair_orphan_requirements`), [app/repositories/database.py](app/repositories/database.py) (`flag_requirement_needs_clarification`) |
| After two attempts the run saves an error report and is marked Needs Review | [app/graph/build_graph.py:313-340](app/graph/build_graph.py#L313-L340) (`needs_review_node`) |
| **The To-Be approval gate**: the run stops after proposing the To-Be and generates nothing downstream until a Process Owner approves | [app/graph/build_graph.py:212-240](app/graph/build_graph.py#L212-L240) (`await_to_be_approval_node`) |
| Approving continues the run in the background | [app/api/artifacts.py:84-105](app/api/artifacts.py#L84-L105) |

**Proven by** `tests/test_full_loop_e2e.py` (8 tests). The headline one,
`test_full_loop_upload_run_answer_approve_generates_every_document`, drives the whole
cycle over HTTP and asserts the run completes, open-critical reaches 0, and
`brd, prd, frd, workflow_json, test_plan, uat_pack, traceability_matrix,
rules_catalogue, roles_matrix` all exist. Also
`test_answering_does_not_create_a_second_run`,
`test_a_second_run_on_an_unchanged_document_adds_no_rows`,
`test_unchanged_sections_cost_no_model_calls_on_a_re_run` (asserts **zero** model
calls), `test_fingerprints_are_stable_across_runs`, and
`test_interrupted_runs_are_reconciled`.

**Also verified against a real uvicorn server** (not just `TestClient`):

```
1) paused:      status=waiting_for_human  node=waiting_for_human            progress=75%
2) answered 4 critical questions
3) To-Be gate:  status=waiting_for_human  node=waiting_for_to_be_approval   progress=88%
   artifacts before approval: 0
4) approve:     200  {'downstream_generation_started': True}
5) finished:    status=completed          node=completed                    progress=100%
6) artifacts (12): brd, data_model, frd, hld, prd, roles_matrix, rules_catalogue,
                   srs, test_plan, traceability_matrix, uat_pack, workflow_json
7) traceability chains: 8   valid=True
```

---

## Phase 3 — Real AI configuration (F5)

| Change | Where |
|---|---|
| `LLM_PROVIDER=mock` is refused at startup outside a test environment, using the same guard pattern as the SQLite fallback | [app/services/llm_service.py:55-82](app/services/llm_service.py#L55-L82) (`validate_configuration`), called from [app/main.py:22-28](app/main.py#L22-L28) |
| `/api/health` reports `llm_provider` and `model_is_mock` so the UI can warn | [app/main.py:82-95](app/main.py#L82-L95) |
| A standing banner on every page when the provider is not `gemini` | [app/ui/streamlit_app.py](app/ui/streamlit_app.py) (after the sign-in gate) |
| The brief's data-sharing notice next to the upload box: *"Text from your documents is sent to Google Gemini. Use only non-sensitive documents."* | [app/ui/streamlit_app.py](app/ui/streamlit_app.py) |
| Mock OCR output now says **"MOCK OCR OUTPUT - NOT READ FROM YOUR DOCUMENT"** instead of inventing a plausible `$50` fee and a deadline | [app/services/llm_service.py:95-106](app/services/llm_service.py#L95-L106) |
| `LLM_TIMEOUT_SECONDS` is actually applied (it was read and ignored) | both Gemini call sites, via `types.HttpOptions(timeout=...)` |
| Pacing between calls and at most 2 concurrent calls, as brief Phase 0 requires | [app/services/llm_service.py:29-37](app/services/llm_service.py#L29-L37), [:84-93](app/services/llm_service.py#L84-L93) (`_pace`, `_call_slots`) |
| **"What I understood" verifies every quote** against the stored section text; an unverifiable quote is dropped, counted and reported, never shown with a page number and a FACT badge | [app/api/documents.py](app/api/documents.py) (`_verify_understanding_quotes`) |
| The result is persisted per document **checksum** and cached in the UI, instead of one model call per document on every render | [app/repositories/database.py](app/repositories/database.py) (`get/save_document_understanding`), [app/ui/streamlit_app.py](app/ui/streamlit_app.py) (`fetch_document_understanding`) |
| A page that cannot be read is recorded as a document warning, so a partly-read file never shows as fully parsed | [app/services/document_parser.py:181-240](app/services/document_parser.py#L181-L240) |

**Proven by** `tests/test_llm_configuration.py` (15 tests):
`test_mock_provider_is_refused_outside_a_test_environment`,
`test_there_is_no_silent_fallback_from_gemini_to_mock`,
`test_mock_ocr_output_says_it_is_not_from_the_document`,
`test_the_configured_timeout_is_not_ignored`,
`test_a_fabricated_understanding_quote_is_dropped`,
`test_understanding_is_computed_once_per_document_content` (asserts **zero** extra
model calls).

---

## Phase 4 — Uploads (review item 4, F14)

| Change | Where |
|---|---|
| `POST /api/projects/{id}/documents/batch` takes several files and returns **one result line per file** | [app/api/documents.py](app/api/documents.py) (`upload_documents_batch`) |
| A failing file does not stop the others — every file is attempted and reported | same |
| The UI uploader takes several files (`accept_multiple_files=True`), shows progress, and lists each result with its reason | [app/ui/streamlit_app.py](app/ui/streamlit_app.py) |
| Duplicate content returns **409** naming the existing document, not an unhandled 500 | [app/api/documents.py](app/api/documents.py), [app/repositories/database.py](app/repositories/database.py) (`find_document_by_checksum`) |
| The file is written to disk **after** parsing succeeds and the row exists, and removed if anything fails — no orphans | [app/api/documents.py](app/api/documents.py) (`_store_one_document`) |
| The size limit is enforced **while streaming**, in 64 KiB chunks, instead of after buffering the whole body | [app/api/documents.py](app/api/documents.py) (`_read_within_limit`) → HTTP 413 |
| MIME type and magic bytes are validated, not just the extension | [app/api/documents.py](app/api/documents.py) (`_validate_content_type`, `REQUIRED_MAGIC`) |
| The error message lists **every** accepted type, including `.md` | [app/api/documents.py](app/api/documents.py) (`_extension_of`) |

**Proven by** `tests/test_uploads.py` (15 tests):
`test_several_files_upload_at_once_with_one_result_line_each`,
`test_a_failing_file_does_not_stop_the_others`,
`test_duplicate_content_is_reported_not_a_500`,
`test_a_rejected_upload_leaves_no_file_on_disk` (1 document, 1 file after 4 failed
attempts), `test_oversize_upload_is_rejected_without_buffering_everything`,
`test_mime_type_is_validated_not_just_the_extension`,
`test_the_client_filename_is_never_used_as_a_path`.

Live check: a 4-file batch (one duplicate, one fake PDF) returned 2 stored, 2 refused,
each with a plain reason.

---

## Phase 5 — Safe reads and security (F7, F8, F14)

| Change | Where |
|---|---|
| **`GET /traceability` is read-only.** Validation and artifact writing are separate: `validate_traceability` computes, `generate_quality_artifacts` persists, and only the run's quality node calls the latter | [app/agents/quality.py:9-33](app/agents/quality.py#L9-L33), [app/graph/build_graph.py](app/graph/build_graph.py) |
| **`save_artifact` never discards an approval.** Regenerating over an approved or rejected artifact writes the *next* version; an unapproved draft of the same version is still updated in place | [app/repositories/database.py:2259-2330](app/repositories/database.py#L2259-L2330) |
| **No hardcoded signing key.** `secret_key` defaults to empty, and startup refuses an unset key, the retired default, or anything under 16 characters | [app/core/config.py:23](app/core/config.py#L23), [:122-152](app/core/config.py#L122-L152), [app/main.py:15-21](app/main.py#L15-L21) |
| CORS is limited to `APP_BASE_URL` with specific methods and headers, instead of `allow_origins=["*"]` with credentials | [app/main.py:60-80](app/main.py#L60-L80) (`_allowed_origins`) |
| Streamlit XSRF protection re-enabled | [.streamlit/config.toml](.streamlit/config.toml) |
| **`check_permission` fails closed.** An unknown action, or an `approve_artifact` whose type is in neither set, is denied for every role | [app/services/permissions.py:118-137](app/services/permissions.py#L118-L137), [:172-196](app/services/permissions.py#L172-L196) |
| The user cache is bounded (512 entries, oldest evicted) with a 30 s TTL; membership and role are still read fresh on every request | [app/services/permissions.py:51-85](app/services/permissions.py#L51-L85) |
| The audit chain locks the previous event (`SELECT ... FOR UPDATE`) on PostgreSQL, as brief 8.4 requires | [app/repositories/database.py:600-620](app/repositories/database.py#L600-L620) |
| **A rule is never attached to unrelated evidence.** The `sec_evidence[0]` fallback is gone; an ungrounded rule is stored unlinked and raises a `parsing_error` question for the Analyst | [app/agents/rules.py:56-62](app/agents/rules.py#L56-L62), [:98-137](app/agents/rules.py#L98-L137) |
| Invitation e-mail failures are logged without the password | [app/api/team.py:41-52](app/api/team.py#L41-L52) |
| `POST /api/invitations/{id}/resend` with brief 7.4's limits (5 per invitation, 20 per project per day) and a Resend button on the Team page | [app/api/team.py](app/api/team.py), [app/ui/streamlit_app.py](app/ui/streamlit_app.py) |

**Proven by** `tests/test_security_hardening.py` (28 tests), notably
`test_the_traceability_get_writes_nothing`,
`test_regenerating_does_not_discard_an_approval`,
`test_startup_refuses_the_retired_default_secret_key`,
`test_an_unclassified_artifact_type_cannot_be_approved`,
`test_membership_and_role_are_read_fresh_on_every_request` (a removed member gets 404
on the **next** request, no sleep), `test_the_audit_chain_is_continuous`,
`test_invitation_can_be_resent_within_the_limit`.

---

## Phase 6 — Gap detection quality (F10)

`app/agents/gaps.py` was rewritten. It now runs six deterministic checks, none of
them specific to any process.

| Check | Status | Where |
|---|---|---|
| `missing_actor` | kept, now carries its source block | `_check_missing_actors` |
| `conflicting_rules` | **rewritten** | `_check_conflicting_rules`, `_raise_conflict` |
| `ambiguous_term` | kept, now carries its source block | `_check_ambiguous_terms` |
| `missing_info` from step unknowns | **new** | `_check_step_unknowns` |
| `duplicate_step` | **new**, with the "Repeats step N" note | `_check_duplicate_steps`, `_check_duplicate_evidence` |
| Missing appeal / notification path | **new** | `_check_missing_paths` |

Conflict detection specifically:

- Works on **dates, amounts, limits and durations**, not dates only
  (`SUBJECT_CUES`, `VALUE_PATTERNS`, `extract_values`).
- Only compares rules about the **same subject**, decided from the rules' own words
  (`detect_subject`); a value with no subject word falls back to a neutral noun
  (`_subject_for_value`).
- Produces **one question per subject** listing every distinct value as a lettered
  option, so the count cannot grow with the square of the rules. This also matches
  brief 7.12 item 5 better than one question per pair did.
- The wording no longer asserts "submission deadline": the template uses the subject
  found in the text.
- Values keep the document's own casing ("31 March", not "31 march").

Two further fixes found while doing this:

- **Brief 9.2 was being violated.** The discovery prompt fed evidence IDs into the
  text it asked the model to summarise, and they came back out inside step names
  (`- [EVD-001] Quote: "..."`). IDs are now metadata only:
  [app/agents/discovery.py:28-34](app/agents/discovery.py#L28-L34).
- `'duplicate_step'` added to the `kind` CHECK in `schema.sql`, the Pydantic literal
  and an idempotent PostgreSQL migration.

**Proven by** `tests/test_fixture_defect_coverage.py` (19 tests, both fixtures):
one test per planted defect class plus
`test_every_planted_defect_class_is_covered` (all five kinds on one run),
`test_clear_facts_are_not_flagged`,
`test_no_extra_conflicts_are_invented`,
`test_quotes_are_reproducible_from_the_source`, and
`test_the_same_code_handles_both_processes_with_no_branch`, which fails if any agent
file mentions a process name.

---

## Phase 7 — Tests and documents (F4, F9, F14)
<a name="phase-7"></a>

### Spec-to-test traceability is now real
- **104 existing tests** gained explicit `SPEC-`/`AC-` citations in their docstrings.
- Each spec's `## Tests` section is **generated from the suite**, listing the real
  tests that cite its requirements. Regenerate it with the script in
  `DEVIATIONS.md` §9 after adding tests.
- `tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if any
  of the **86** declared `SPEC-` ids loses its coverage. All 86 are covered.
- `test_the_specs_list_test_names_that_actually_exist` fails if a spec names a test
  that does not exist — the F4 condition, now enforced.
- `test_the_spec_coverage_report_can_be_printed` prints a per-requirement report.

### Requirements that had no test at all
While closing the coverage gap I found **SPEC-03-05 was not implemented**:
`document_chunks` existed in the schema and nothing ever wrote a row to it, so the
retrieval layer the brief asks for (4.6) did not exist. Implemented:

- Sections are chunked on sentence boundaries with overlap, inside the same
  transaction as the section insert: `_chunk_section_text`,
  `_save_document_chunks_tx`.
- `search_document_chunks` does project-scoped keyword retrieval — `tsvector` +
  `ts_rank` on PostgreSQL, `LIKE` on SQLite.
- This adds **one** statement to the upload transaction (5 instead of 4, still one
  connection). `test_priority_1_upload_roundtrip_count_and_bulk_reduction` was
  updated to 5 with the reason stated inline.

New tests also cover SPEC-02-04 (`<source>` delimiting), SPEC-05-01/03/04 (step
storage, `STEP-nnn` keys, step fields), SPEC-11-03, SPEC-13-01..05 and
SPEC-16-01..04 (UI shell, tokens, signed-out gate, all 12 pages, no mock data), and
SPEC-15-04 (the demo seed script, which the README contradicted).

### PostgreSQL-only constraint tests
Three tests prove what SQLite cannot: `CHECK (status <> 'approved' OR approved_by IS
NOT NULL)`, the append-only `audit_events` trigger, and per-project key uniqueness.
They **skip** unless `PFAI_TEST_POSTGRES_URL` is set, and the skip message says why.
`DEVIATIONS.md` §6 withdraws the incorrect claim that both adapters enforce the
constraints.

### Documentation corrected
`README.md`: test count (32 → 176 passed / 3 skipped), the Python-version note (now
says 3.11/3.12 are unverified), the demo roles (now match `scripts/seed_demo.py` and
brief 7.10 — Aditi is the **Analyst**), the 100-page PDF limit (a hard refusal, not a
slow path), e-mail delivery (implemented, needs SMTP settings), the stale
`clarification_answers` note (replaced with the real SQLite-constraint limitation),
the hardcoded `c:\Users\ASUS\...` path, and 28 → 29 tables throughout. The test-suite
section now lists every test file, how to run the PostgreSQL-only tests, and the
traceability check.

`DEVIATIONS.md` gained five entries (§6–§10) covering the withdrawn claim, the three
schema additions, the two "waiting" states sharing one run status, the generated spec
Tests sections, and `.venv`.

---

## What I could not do
<a name="what-i-could-not-do"></a>

1. **Run the suite on Python 3.11 or 3.12.** Neither is installed, and `uv`, `pyenv`,
   `conda`, `brew` and `asdf` are all absent, so I could not install them. The final
   run is **Python 3.14.7 only**. A static scan found no 3.12+-only syntax (no PEP 695
   `type` aliases or generic parameter lists, no `itertools.batched`, no
   `datetime.UTC`, no `@override`) and no stdlib removed in 3.13, so 3.11
   compatibility is plausible but **unproven**. Please run `pytest` on both before
   claiming support. README now says so.

2. **Run the PostgreSQL constraint tests.** No local PostgreSQL and no Docker. The
   three tests are written and skip with an explicit reason; the command to run them
   is in the README.

3. **Confirm whether the earlier review run left rows in your Supabase database.**
   Reported in `REVIEW_REPORT.md` §0.1. Reading production is blocked in this
   environment and I did not work around it. Please look for users matching
   `benchmark_%@processfoundry.ai` and projects named `Upload Benchmark Project`,
   `Benchmark Project` or `Serialization Benchmark`, and delete them. Phase 0 makes a
   repeat impossible.

4. **Verify the UI in a browser.** All UI changes are verified by reading the source
   and by API-level tests. I ran a real uvicorn server and drove the full flow over
   HTTP, but took no screenshots and did not click through Streamlit.

5. **Test against a real Gemini model.** Everything ran with `LLM_PROVIDER=mock`
   deliberately — no API spend, no network. Real-model behaviour (actual JSON
   conformance, genuine rate-limit handling, OCR quality) is still untested by me.
   The pacing, concurrency cap and timeout are verified structurally, not under load.

6. **Delete `.venv`.** It is a Windows virtual environment that cannot work here, but
   removing it is your call. It is in `.gitignore` and documented in `DEVIATIONS.md` §10.

7. **`.env` was not touched**, as instructed. It still has `LLM_PROVIDER=mock`, so
   **the app will now refuse to start** until you set `LLM_PROVIDER=gemini` — that is
   the intended effect of the F5 fix. For offline work, set `APP_ENV=test` or
   `ALLOW_SQLITE=true` alongside it.

---

## Still open

| Item | Why it is still open |
|---|---|
| **Database region** | `DATABASE_URL` points at `aws-0-ap-northeast-1` (Tokyo), ~90–140 ms from India. The N+1 fan-out is fixed, which is the larger win, but moving the database to `ap-south-1` (Mumbai) would cut the remaining round-trip cost by roughly 70%. I did not change `.env`. |
| **Two identical `ambiguous_term` questions across documents** | Two documents each containing "eligible" produce one question each, correctly linked to their own source. Defensible, but noisy on a large upload. Deduplicating by term across documents would need a product decision about whether one definition covers all sources. |
| **`agent_runs` is still unused** | The table exists; per-node timings are never written. Not a regression and not in the review's findings. |
| **Streamlit session loss on refresh** | Already a documented known limitation (brief 7.3 accepts it). |
| **No `missing_info` question links** | The appeal/notification questions have no source links, because the finding *is* the absence of a source. The UI handles an empty source block. |
| **`check_db.py` expects 29 tables** | If you run it against the Supabase database before applying the new `schema.sql` objects, it will report `document_understanding` missing. The app's own startup migration creates it; `check_db.py` does not. |

---

## Phase 8 — Raw HTML rendering as literal text

**Reported symptom:** the three Project Overview stat cards (Open questions,
Artifacts, Team members) displayed as raw HTML instead of rendering.

**Root cause.** `st.markdown(..., unsafe_allow_html=True)` still runs the string
through a CommonMark parser first, and two Markdown rules destroy an indented
template:

* a **whitespace-only line** inside an HTML block closes that block;
* a line indented **four or more spaces** then becomes an indented **code block**,
  so the markup is escaped and displayed as text.

`render_stat_cards` appended each card with 8-space indentation and a trailing
`\n        `, which produced a whitespace-only line *between* cards. Reproduced
with `markdown-it-py` (the same CommonMark spec Streamlit's front end follows):

```
BEFORE:  code block: True    markup escaped to text: True    stat-card divs in DOM: 1/3
AFTER :  code block: False   markup escaped to text: False   stat-card divs in DOM: 3/3
```

The first card rendered and the other two appeared as
`&lt;div class=&quot;pf-stat-card&quot;&gt;…` — exactly the reported symptom.

**The same bug hit the entire theme stylesheet**, which nobody had noticed:

```
BEFORE:  <style> tag survives: no    design tokens reaching the browser: 0/4
AFTER :  <style> tag survives: yes   design tokens reaching the browser: 4/4
```

`app/ui/theme.py`'s CSS string starts with a 4-space-indented `<style>` and
contains 15 blank lines, so the browser received
`<pre><code>&lt;style&gt; @import url(…` — **not one Section 10.9 design token was
ever applied.** The navy sidebar, cards, pills and typography were all inert.
This is why so much of the UI looked like default Streamlit.

### The fix

| Change | Where |
|---|---|
| `html_block()` collapses a template onto one line, so no line-level Markdown construct can exist. Lines join tightly where one tag ends and the next begins (adjacent inline elements keep their exact spacing) and with a single space otherwise (text wrapped across source lines does not run its words together). | [app/ui/components.py:34-47](app/ui/components.py#L34-L47) |
| `render_html()` is now the **only** place in the app that calls `st.markdown` with `unsafe_allow_html`. | [app/ui/components.py:50-55](app/ui/components.py#L50-L55) |
| All **102** call sites rewritten to `render_html(...)`: 97 in `streamlit_app.py`, 4 in `components.py`, 1 in `theme.py`. | `app/ui/` |
| Templates keep their readable indentation in the Python source; normalisation happens at render time, so nothing became harder to maintain. | — |

The collapse is whitespace-only and content-preserving. The app contains no
`<pre>`, `<textarea>` or `white-space: pre` (checked), so nothing in it is
whitespace-sensitive. CSS integrity after collapsing was verified: braces
balanced (54/54), comments balanced (17/17), and `@import` still precedes the
first rule.

**The rewrite was proved lossless**, not assumed: every one of the 102 first
arguments was compared byte-for-byte against a pre-rewrite copy of the three
files. All identical.

> Note on how this was done: the first attempt indexed the source as a *string*
> using `ast` `col_offset` values, which are **UTF-8 byte** offsets. On lines
> containing `·`, `→`, `✓` or emoji the positions drifted and ate characters,
> producing one syntax error and ~15 silently damaged lines. The files were
> restored from a verified copy and the rewrite redone on `bytes`.

### The Deploy label overlapping the user name

Streamlit's built-in toolbar (the Deploy button, hamburger menu, "Running"
status and the thin decoration bar) is absolutely positioned over the top-right
of the page — exactly where `.pf-topbar` shows the signed-in user's name and
role. `theme.py` had only made the header transparent and zero-height, so its
contents still painted on top.

Now hidden outright, since the app supplies its own top bar:
`[data-testid="stToolbar"]`, `[data-testid="stToolbarActions"]`,
`[data-testid="stDeployButton"]`, `[data-testid="stStatusWidget"]`,
`[data-testid="stDecoration"]`, `.stDeployButton` and `#MainMenu`. The collapsed
header also gained `pointer-events: none`, and `.pf-topbar` a `z-index` above
anything Streamlit still paints there. [app/ui/theme.py:35-66](app/ui/theme.py#L35-L66)

### All 12 pages audited

Every page in the dispatch chain was checked. No page passes HTML to a widget
that cannot render it, and no container or widget *label* contains HTML:

| Page | `render_html` calls |
|---|---|
| My projects | 12 |
| Create a project | 3 |
| Overview & Uploads | 19 |
| Waiting for me | 11 |
| Sources & Evidence | 2 |
| As-Is Discovery | 4 |
| Questions & Rules | 3 |
| Process Redesign | 7 |
| Requirements & Specs | 1 |
| Workflow & Traceability | 5 |
| Team & invitations | 8 |
| Audit log | 6 |

### Tests

`tests/test_ui_html_rendering.py` — 15 tests, including the normaliser's
behaviour (indentation, blank lines, no word-joining, tag adjacency, idempotence,
content preservation), the real 3-card stat payload, the theme stylesheet
surviving with all 8 design tokens, the toolbar being hidden, and two structural
guards that fail if anyone reintroduces the bug: `render_html` must remain the
only unsafe caller, and no widget may receive HTML it cannot render.

Both services were also booted together (FastAPI on 8598, Streamlit on 8599):
the API answered `/api/health` and Streamlit returned HTTP 200 with no import
error, confirming `theme.py` importing from `components.py` creates no cycle.

**Suite after Phase 8: 191 passed, 3 skipped.**

### Still open from this phase

**Card wrappers do not actually wrap.** Ten places open a wrapper in one call and
close it in a later one, e.g. `render_html('<div class="pf-card">')` … widgets …
`render_html('</div>')` (lines 461, 852, 910, 979, 1066, 1144, 1227, 1306, 1385,
1415 of `streamlit_app.py`). Each `st.markdown` is its own DOM container, so the
opening `<div>` is auto-closed by the browser immediately and the orphan
`</div>` is discarded: the card paints as an empty bordered box with its content
below it, unwrapped. This is a layout defect, **not** raw HTML shown as text, and
fixing it means restructuring those blocks — either `with st.container(border=True):`
or emitting the whole card in one `render_html` call. Left alone here because the
brief for this phase was not to change behaviour or layout.
