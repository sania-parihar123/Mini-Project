# ProcessFoundry AI — Independent Review Report

**Reviewed:** 20 October 2026
**Method:** read-only. No source file was modified. The only file created is this one.
**Code under review:** `/Users/aditikharat/Downloads/Project-ProcessFoundaryAI 2/Project-ProcessFoundaryAI`
**Reviewer's rule:** nothing below is taken from Antigravity's README, `DEVIATIONS.md` or specs unless I reproduced it myself. Where I could not verify something, it says so explicitly.

---

## 0. Read this first: three things about the review itself

### 0.1 I very likely wrote rows into your live Supabase database. I am sorry.

My first action in Step 2 was `env -u DATABASE_URL python3 -m pytest`, intending an isolated run. That did **not** isolate anything:

`app/core/config.py:24-26` configures Pydantic Settings with `env_file = ".env"`. Unsetting a shell variable does not stop Pydantic from reading `.env`. So `settings.database_url` still resolved to your Supabase host, and `app/repositories/database.py:23` set `use_postgres = True`.

`tests/test_latency_benchmarks.py` is the one test file with **no** database-isolation fixture (the other nine all have `@pytest.fixture(autouse=True)` that monkeypatches `db.use_postgres = False`). Its tests call `/api/auth/register`, `/api/projects` and `/api/projects/{id}/documents` through `TestClient` — 24 write calls — creating accounts named `benchmark_<hex>@processfoundry.ai` and projects named `Upload Benchmark Project`, `Benchmark Project` and `Serialization Benchmark`. There is **no cleanup code anywhere in `tests/`** (no `DELETE FROM`, no teardown fixture).

Corroborating evidence that it reached Tokyo: that run took **48.87 s**. The identical suite, genuinely isolated, takes **6.85 s**. The ~42 s delta is round-trip time to the database.

I tried to confirm by running a read-only `SELECT count(*)` against the live database and the action was blocked by this environment's production-read guard, so **I could not confirm it and I did not try to work around the block.** Please check for and delete those rows yourself.

**This is itself a finding.** Running `pytest` on a developer machine that has a populated `.env` writes to production. See [F2](#f2).

### 0.2 `latency_investigation_report.md` does not exist

I searched the whole tree (`find . -iname '*latency*'`). The only match is `tests/test_latency_benchmarks.py`. There is no report file, so **Step 3's instruction to mark every number in it as confirmed / contradicted / cannot-verify has nothing to operate on.** Instead, Section 3 below reports measurements I took myself, and Section 3.5 checks the performance claims that *are* written down — in `README.md`.

### 0.3 Document inventory

| Item | Status |
|---|---|
| Brief files matching `*BRIEF*` / `*PROCESSFOUNDRY*` | **One only**: `PROCESSFOUNDRY_BUILD_BRIEF_UPDATED_UI.md` (1434 lines). No older version exists, so no version diff to report. |
| Section 10.9 (the UI override) | Present at line 1342. Read in full. |
| Appendix SQL vs `schema.sql` | **Byte-identical** (28 `CREATE TABLE` in each; extracted the appendix fence and diffed — no differences). |
| `specs/` | All 18 files read (00–16 plus `tasks.md`). |
| `DEVIATIONS.md`, `README.md` | Read in full. |
| `processfoundry_ai_professional_clickable_prototype.html` | Not present under that name. `reference_prototype.html` (32 KB) is present and is what the specs point at. Cosmetic. |

---

## 1. Verdict

The scaffolding is real and better than average: one shared `psycopg_pool` connection pool, genuinely background runs, correct project isolation on every route I probed, bcrypt + signed tokens, a real hash-chained audit log, honest verbatim-quote verification, and a UI that polls with real stage names.

But **the product cannot complete its own core workflow.** Two defects, both reproduced:

- The two endpoints that show clarification questions return **HTTP 500** as soon as one `ambiguous_term` question exists — which happens on the first run of almost any document ([F1](#f1)). The UI swallows the 500 and renders an empty list, so the user is told there are no questions.
- Answering the last critical question starts a **brand-new run from `ingest`**, which re-extracts everything, regenerates the same gap as a *new* question with a *new* fingerprint, and pauses again. Open-critical count stays at 1 forever ([F3](#f3)). **To-Be, requirements, BRD/FRD/PRD, workflow, tests and traceability are never generated through the product's normal flow.**

The 52 passing tests do not catch either one, because the tests that claim to cover this ground call agents and router functions directly instead of going through the API or the graph ([F4](#f4)).

The speed work is real where it was done (pool, background runs, user cache, HTTP keep-alive) but the two largest remaining costs were not addressed: N+1 query fan-out on the question and traceability pages, and full re-extraction (including every LLM call) on every run.

Separately: **`.env` currently has `LLM_PROVIDER=mock`.** As shipped, this application invents document content and shows it to the user as extracted fact, with nothing on screen saying so ([F5](#f5)).

---

## 2. Step 2 — The project's own checks

### 2.1 Test suite

Isolated run (fresh copy in a scratch directory, `DATABASE_URL=""`, `ALLOW_SQLITE=true`, temp SQLite):

```
platform darwin -- Python 3.14.7, pytest-9.1.1
52 passed in 6.85s
```

**52 passed, 0 failed, 0 skipped, 0 errors.** `README.md:293` claims **"32 tests — 0 failures"** — the count is **contradicted** (52 collected). The "0 failures" half is confirmed.

Slowest tests: `test_user_lockout_after_five_failed_attempts` 0.97 s, `test_priority_3_cold_vs_warm_login` 0.49 s, `test_password_hashing_and_verification` 0.48 s — all bcrypt cost, which is correct and expected.

### 2.2 Python versions

| Question | Answer |
|---|---|
| What does `pyproject.toml` claim? | `requires-python = ">=3.11"` (line 11). |
| What is installed here? | **Only Python 3.14.7.** `python3.11`, `python3.12`, `python3.13` are all absent, and `uv`, `pyenv`, `conda` and `brew` are all unavailable, so I **could not install them**. |
| So: do tests pass on 3.11 / 3.12? | **CANNOT VERIFY BY EXECUTION.** This is the one Step-2 item I could not complete. |
| What I did instead | (a) Imported all 42 modules under `app/` on 3.14.7: **41 succeeded.** The only failure is `app.ui.streamlit_app`, which executes the Streamlit app at import time and fails on `AttributeError: 'NoneType' object has no attribute 'get'` with no Streamlit runtime — expected, not a defect. (b) Grepped for syntax and stdlib features that would break on 3.11: PEP 695 `type X = ...`, PEP 695 generic `def f[T]` / `class C[T]`, `itertools.batched`, `datetime.UTC`, `@override`. **No hits.** No removed-in-3.13 stdlib either (`imp`, `distutils`, `cgi`, `telnetlib`). |
| Honest conclusion | The code contains nothing that is 3.12+-only, so 3.11 compatibility is **plausible but unproven**. Run `pytest` on 3.11 and 3.12 yourself before claiming it. |

Note also `README.md:122`: "tested on 3.14.6". I ran 3.14.7.

### 2.3 The `app/agents/gaps.py` import crash

**Already fixed.** `app/agents/gaps.py:5` reads `from typing import List, Dict, Any, Optional, Tuple`. `Optional` is imported and is used at line 32 (`run_id: Optional[str] = None`). The module imports cleanly. This is version-independent — a missing name there would have raised `NameError` on every Python version, not just 3.11/3.12.

### 2.4 Which tests touch a live database, and do they clean up?

| Test file | DB isolation | Cleans up? |
|---|---|---|
| `test_api.py` | autouse fixture → temp SQLite in `tmp_path` | n/a (temp file discarded) |
| `test_auth_permissions.py` | same | n/a |
| `test_evidence.py` | same | n/a |
| `test_fixtures.py` | same | n/a |
| `test_graph_routing.py` | same | n/a |
| `test_new_features.py` | same | n/a |
| `test_rules_gaps.py` | same | n/a |
| `test_traceability.py` | same | n/a |
| `test_parsing.py` | touches no DB | n/a |
| **`test_latency_benchmarks.py`** | **NONE** — no fixture, uses whatever `settings.database_url` resolves to | **NO.** 24 write calls; zero cleanup. |

So: **one file**, and it does not clean up. See [F2](#f2).

---

## 3. Step 3 — Measured, not guessed

### 3.1 Is a real connection pool used?

**Yes, and it is correct.**

- `app/repositories/database.py:15` imports `psycopg_pool`; `:56-64` constructs one `psycopg_pool.ConnectionPool(min_size=1, max_size=10, open=True, timeout=30.0)`.
- `app/main.py:20-32` opens it exactly once in the FastAPI `lifespan` startup hook and closes it on shutdown.
- `app/repositories/database.py:89-93`: `get_connection()` returns `self._pool.connection()` — a checkout from the shared pool, not a new connection.
- **No per-query `psycopg.connect` anywhere in `app/`.** I grepped all of `app`, `scripts` and `tests`: the only `psycopg.connect` is `scripts/check_db.py:31`, a one-shot verification script, which is fine.
- `get_connection()` lazily calls `init_pool()` if startup was skipped, so there is still only ever one pool.

The README's pool claim is **confirmed**.

### 3.2 Connections and queries per operation — measured

Instrumented by wrapping `db.get_connection` and every cursor's `execute`/`executemany`, driving the real FastAPI app over `TestClient` against a temp SQLite database. "Connections" = pool checkouts, i.e. round trips in the Postgres case.

| Operation | Connections | Queries | Assessment |
|---|---|---|---|
| register | 2 | 2 | fine |
| login | 2 | 2 | fine |
| **2nd authenticated request (`GET /api/me`, cache warm)** | **0** | **0** | the user cache works as advertised |
| create project | 1 | 3 | good — one transaction |
| My projects (`GET /api/projects`) | 1 | 1 | good |
| open a project (`GET /api/projects/{id}`) | 2 | 2 | membership check + project read |
| **upload 1 document (3 sections)** | **2** | **5** | sections bulk-inserted in one statement — good |
| **upload 3 documents** | **6** | **15** | exactly 3× the single upload; no batching across files, but no waste either |
| **poll a run (`GET /api/runs/{id}`)** | **2** | **2** | good — cheap enough to poll every 1.5 s |
| `POST /runs` — the HTTP request itself | ~4 | ~6 | returns immediately (see 3.3) |
| `POST /runs` — the full background pipeline | **335** | **595** | the real cost; see 3.4 |
| **`GET /projects/{id}/questions` (29 questions)** | **31** | **60** | **N+1: 1 + 2 per question** |
| `GET /me/questions` (Waiting for me) | 1 | 1 | one good JOIN — this is how the other should work |
| **`GET /projects/{id}/traceability`** | **85** | **130** | **N+1, and it writes — see [F8](#f8)** |

### 3.3 Does the analysis run in the background?

**Yes — verified against a real uvicorn server**, not just by reading code.

```
POST /runs returned in 0.003 s   status=200  run_status=running
  t+ 0.00 s  status=running           node=start
  t+ 0.41 s  status=waiting_for_human node=waiting_for_human
```

`app/api/runs.py:33` hands the work to `background_tasks.add_task(execute_project_run_background, ...)`. The 3 ms response is the endpoint; the pipeline then runs in the server process.

**Does the UI poll and show progress?** Yes. `app/ui/streamlit_app.py:546-575` polls `GET /api/runs/{id}`, renders the stage name and a progress bar, offers Cancel, and re-runs every 1.5 s while `status == "running"`.

I initially suspected the progress bar was fake, because `streamlit_app.py:552` reads `run_data.get("progress", 10)` and the `runs` table has no `progress` column. **That suspicion was wrong** — `app/repositories/database.py:2170-2187` computes `progress` and `stage` in `get_run` from a node→percentage map (`evidence` 30, `as_is` 45, `rules` 60, `gaps` 75, `requirements` 90, `quality` 98, `completed` 100). The progress shown is real.

**What timeout does the UI client use?** `app/ui/api_client.py:12-16` creates one persistent `httpx.Client` with `timeout=30.0` and keep-alive (connection reuse — a genuine improvement). Overrides: `upload_document` 60 s, `trigger_run` 60 s, `get_document_understanding` 60 s. Run polling uses the 30 s default, which is ample for a 2-query status read.

**A long run does not hit a UI timeout on the start path.** It does on the *answer* path — see [F3](#f3) — because answering is synchronous.

### 3.4 Per-item queries inside loops, and repeated reads

Measured, from the query-detail dump:

1. **`list_project_clarification_items` is a textbook N+1** (`database.py:1728-1745`): one `SELECT id`, then `get_clarification_item(qid)` per row, each taking its own connection and running 2 queries. 29 questions → 31 connections, 60 queries. On the Tokyo database at ~120 ms RTT this page costs roughly **7 seconds** of pure latency.
2. **`GET /traceability` is worse** — 85 connections / 130 queries, because `quality_agent.validate_traceability` re-walks clarifications (29×2), document sections (24), business rules (16), and rule→evidence joins (16).
3. **Repeated reads of the same data:** `SELECT * FROM document_sections WHERE id = ?` ran **24 times** during one run — once per evidence claim, re-fetching the same handful of sections.
4. **`is_run_cancelled` costs one `SELECT * FROM runs` per graph node** (9 nodes).
5. **Key minting on SQLite** is read-then-write (`SELECT next_value` + `UPDATE`, 75 + 71 calls in one run). **On PostgreSQL it is correct** — `database.py:454-460` uses the atomic `INSERT … ON CONFLICT DO UPDATE … RETURNING` that Part 8.4 of the brief specifies. Still one extra round trip per minted key.
6. **Re-extraction on every run** — the single biggest cost. Measured:

   | | questions | rules | evidence |
   |---|---|---|---|
   | after run #1 | 5 | 3 | 5 |
   | after run #2 | 10 | 6 | 10 |
   | after run #3 | 15 | 9 | 15 |
   | after adding a 2nd doc, run #4 | 27 | 15 | 25 |

   Nothing is reused. The brief's Phase 0 requirement — *"remember results already stored so a re-run does not repeat calls for unchanged sections"* — is **not implemented**. Every run re-bills every Gemini call and duplicates every row. See [F6](#f6).

Also absent: any of the LLM pacing the brief requires (a short delay between section calls, at most 2 concurrent calls). `evidence.py:58-63` and `rules.py:79-85` loop over sections serially with no delay and no concurrency cap. And `settings.llm_timeout_seconds` is read into `self.timeout` at `llm_service.py:25` and **never used** — no timeout is passed to the Gemini client.

### 3.5 Checking the performance claims that *are* written down

Since `latency_investigation_report.md` does not exist, I verified `README.md`'s performance statements:

| Claim | Verdict | Evidence |
|---|---|---|
| "a high-performance shared connection pool (`psycopg_pool.ConnectionPool`) is initialized and reused across database operations" | **CONFIRMED** | `database.py:56-64`, `main.py:24`, `database.py:89-93`; no per-query connect |
| "eliminating per-query TLS handshakes and connection overhead" | **CONFIRMED** in principle | pool checkouts replace connects; the 48.87 s → 6.85 s delta between Tokyo and local shows how much RTT dominates |
| "32 tests — 0 failures" | **CONTRADICTED on the count** | 52 collected, 52 passed |
| "At application startup … validate the database connection and connection pool automatically" | **CONFIRMED** | `main.py:20-28` raises on failure |
| "SQLite fallback is restricted strictly to test environments … will fail fast on startup" | **CONFIRMED** | `database.py:34-49`; `test_sqlite_fallback_fails_fast_in_production` passes, and I reproduced the guard |
| "Both adapters implement the identical project-scoped repository interface **and enforce constraints**" (`DEVIATIONS.md` §5) | **CONTRADICTED** | `schema.sql` has **40** `CHECK` constraints, the append-only audit trigger and RLS. The SQLite mirror in `database.py` has **0** `CHECK` constraints, no trigger, no RLS. See [F9](#f9) |
| "Email delivery not implemented … Integrate an SMTP/SendGrid service to activate" | **CONTRADICTED** | `app/api/team.py:2,15-40` implements it with `smtplib` + `starttls()`, correct subject line, no token in the body. It is merely unconfigured (no `SMTP_*` in `.env`). See [F13](#f13) |
| Demo account roles table | **CONTRADICTED** | README says Aditi = Process Owner, Rao = Analyst. `scripts/seed_demo.py:12-14` says Aditi = **analyst**, Rao = **process_owner** — the script matches the brief (7.10); the README does not |
| "Very large PDFs (>100 pages) may be slow. PyMuPDF processes them page-by-page with timeout" | **MISLEADING** | `document_parser.py:170-171` **rejects** >100 pages outright with an error. There is no timeout. |

### 3.6 Database region

- Host: **`aws-0-ap-northeast-1.pooler.supabase.com`**, port **5432**, database `postgres` (Supabase session-mode pooler). Password and key values were never printed.
- `ap-northeast-1` is **AWS Tokyo**.
- **Is it far from India?** Yes — roughly 5,800–6,500 km from the major Indian metros, typically **90–140 ms** round trip. Tokyo is about the worst of the nearby choices; `ap-south-1` (Mumbai) or `ap-southeast-1` (Singapore) would cut RTT by roughly 70 % and 40 % respectively.
- **This is why the N+1 fan-out matters so much.** The 48.87 s vs 6.85 s test-suite delta is that RTT, measured. A page costing 31 connections is ~7 s from India on this host and ~0.3 s on a local database. Moving the database to Mumbai *and* fixing the N+1 queries are complementary, not alternatives.

| Setting | State (values never printed) |
|---|---|
| `DATABASE_URL` | set, Tokyo pooler host |
| `SECRET_KEY` | set, 44 chars |
| `LLM_API_KEY` | set, 53 chars |
| **`LLM_PROVIDER`** | **`mock`** ← see [F5](#f5) |
| `LLM_MODEL` | `gemini-2.5-flash` |
| `ALLOW_SQLITE`, `APP_ENV` | **not present** in `.env` |
| `SMTP_HOST`/`PORT`/`USER`/`PASSWORD`/`FROM` | **not present** in `.env` (they are in `.env.example`) |

---

## 4. Step 4 — Cache and security

### 4.1 Every cache

| Cache | Location | Stores | TTL | Scope |
|---|---|---|---|---|
| `_user_cache` | `app/services/permissions.py:52` | the full `users` row (incl. `password_hash`, `failed_attempts`, `locked_until`) | **60 s** | **per process, in memory.** Not shared between workers; lost on restart. Unbounded — entries are only overwritten, never evicted, so it grows with distinct users. |
| `st.cache_data` × 13 | `app/ui/streamlit_app.py:27-78` | API responses (projects, documents, questions, team, evidence, rules, artifacts, traceability, audit) | **20–30 s** | per Streamlit process, keyed on the token, so not shared across users |

There is **no** cache of membership or role. That is the right decision.

### 4.2 Is membership and role checked fresh on every request?

**Yes — verified by experiment, not by reading.**

`require_project_member` (`permissions.py:90-95`) calls `db.get_member_role(project_id, user_id)`, which executes `SELECT role FROM project_members WHERE project_id = ? AND user_id = ? AND status = 'active'` on **every** request. I saw that exact query in the measured trace for every project-scoped endpoint.

Live test of removal:

```
analyst can view the project before removal:      200
remove the analyst (as Process Owner):           200
analyst view IMMEDIATELY after removal:          404
analyst upload immediately after removal:        404
analyst GET /api/me still works (user cache):    200
```

- **A removed member loses project access on the very next request — 0 seconds of staleness.**
- **A changed role takes effect on the very next request**, same mechanism.
- **How long can the stale cache keep access?** For project data, **it cannot** — the 60 s cache holds only the user's own row, never membership or role. The residual exposure is narrow and worth knowing: for up to 60 s after a change, a *lock-out* or a *password change* is not reflected for an already-issued token, because `get_current_user` reads `locked_until` and `failed_attempts` from the cached row. Tokens are valid 8 h and there is no revocation list, so that is the weaker link, not the cache.

### 4.3 Security checklist

| Check | Finding |
|---|---|
| **Hardcoded / default secret key** | **YES.** `app/core/config.py:9` — `secret_key: str = "pfai_default_secret_key_8f3a9e2c1b7d4e5f6a0c8b9d"`, repeated at `:42`. If `SECRET_KEY` is unset the app silently signs session tokens with a key that is committed in the source, so **anyone with the source can forge a valid session token for any user id**. There is no startup check that `SECRET_KEY` was actually provided. See [F7](#f7). |
| **Secrets in files that would be zipped or committed** | `.gitignore` correctly lists `.env`, `uploads/`, `*.db`. But **this folder is not a git repository** (`Is a git repository: false`), so `.gitignore` protects nothing today. `.env` sits in the project root with a real Supabase password and a real 53-char Gemini key. **Zipping or sharing this folder leaks both.** `uploads/` (102 files) and `data/processfoundry.db` (385 KB) would also travel with it. `.env.example` is correct — placeholders only. |
| **CORS** | **Too permissive.** `app/main.py:42-48` — `allow_origins=["*"]` with `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`. Because auth is a Bearer header rather than a cookie, this is not directly session-stealing, but it lets any website on the internet call this API from a victim's browser with a token it has obtained, and it defeats origin-based defence in depth. Restrict to `APP_BASE_URL`. |
| **Streamlit XSRF/CORS** | `.streamlit/config.toml` sets `enableCORS = false` **and** `enableXsrfProtection = false`. Both protections are switched off. Nothing in the brief asks for this. |
| **Upload path handling** | **Correct — I tried to break it and could not.** `app/api/documents.py:48-50` builds `uploads/<project_id>/<uuid4>`; the client filename is never used as a path. I uploaded a file named `../../escape.txt`: HTTP 201, `filename` stored as the literal display string `'../../escape.txt'`, **no file created outside `uploads/`**. Matches brief 8.3 rule 9. |
| **File-type checks** | **Extension only — MIME is never validated.** `documents.py:37-43` checks the suffix against `(.pdf, .docx, .txt, .md)`. `file.content_type` is stored but not checked. I uploaded `MZ\x90\x00`-prefixed binary named `evil.exe.txt` with `Content-Type: application/x-msdownload` → **HTTP 201, accepted**. Brief 5.4 requires validating "size/extension/MIME/parser result"; 3 of 4 are done. Low real risk (content is only ever parsed as text), but it is a gap against the brief. Also, the error message says ".pdf, .docx, and .txt" while `.md` is silently accepted. |
| **Size checks** | Present but **enforced after the whole body is in memory**: `documents.py:26-34` does `content = await file.read()` *then* compares against `MAX_UPLOAD_MB`. A 2 GB POST is fully buffered before rejection. PDF page cap of 100 at `document_parser.py:170`. |
| **SQL built by string formatting** | **Clean.** Exactly one f-string in a query — `database.py:1741` — and the interpolated `where_clause` is assembled only from fixed literals (`"project_id = ?"`, `"assigned_role = ?"`, `"status = ?"`), with all values passed as bound parameters. Every other call site uses placeholders. **No SQL injection found.** |
| **Cross-project data access** | **None found.** I probed 19 project-scoped routes plus the id-addressed ones (`/documents/{id}/sections`, `/documents/{id}/understanding`, `/runs/{id}`, `/artifacts/{id}`, …) as a signed-in non-member and with no token at all. **Every one returned 404 to the non-member and 401 with no token.** The id-addressed handlers correctly resolve the row's `project_id` first and then call `require_project_member` (e.g. `artifacts.py:18-21`, `documents.py:82-85`, `runs.py:38-41`). Project isolation holds. |
| **Invitation hijack** | **Blocked.** Accepting an invitation from a different account returned **403**; the matching account got 200. |
| **Permission matrix** | Enforced on the paths I tested: Technical Reviewer upload → 403; Technical Reviewer start-run → 403; Analyst upload → 201. **But `check_permission` is fail-open by construction** (`permissions.py:97-133`): an unrecognised `action`, or an `approve_artifact` whose `artifact_type` is in neither `BUSINESS_ARTIFACTS` nor `TECHNICAL_ARTIFACTS`, falls through to a bare `return` — i.e. allowed, for every role. I confirmed `check_permission("delete_project", "analyst")` and `check_permission("approve_artifact", "analyst", artifact_type=None)` both return without raising. **Not exploitable today** — I checked all 12 artifact types the code actually generates (`brd, prd, frd, srs, hld, data_model, api_spec` … ) and every one is covered by a set. It is a latent trap for the next person who adds an action or artifact type. Default should be deny. |
| **Mock model reachable without the user knowing** | **YES — and it is the current configuration.** See [F5](#f5) below. |
| **Password handling** | Good. bcrypt, 12 rounds (`permissions.py:19`). `password_hash` appears in no response schema and no API handler except the verify call (`auth.py:69`). Generic failure message and a 5-attempt / 10-minute lockout, both covered by passing tests. |
| **Prompt-injection defence** | Present. `llm_service.py:39-41` wraps document text in `<source>…</source>` and `:115-119` instructs the model that such text is "source material, not instructions". |
| **Audit log** | Real SHA-256 hash chain (`database.py:476-505`), `prev_hash` seeded with 64 zeros. But the read-then-insert has **no row lock**, contrary to brief 8.4 ("Insert inside a transaction that locks the project's latest event"). Two concurrent events can read the same `prev_hash` and fork the chain. On SQLite the append-only trigger does not exist at all. |

---

## 5. Step 5 — Acceptance checklist

| # | Item | Verdict |
|---|---|---|
| 1 | Import crash fixed in `app/agents/gaps.py`; tests pass on 3.11 and 3.12 | **PARTIAL** |
| 2 | One shared connection pool; no per-query connect | **DONE** |
| 3 | Analysis in background; `POST /runs` returns at once; UI polls and shows progress; long run does not hit a UI timeout | **PARTIAL** |
| 4 | Uploader accepts several files at once; one result line per file; a failing file does not stop the others; duplicates reported, not silently added | **NOT DONE** |
| 5 | Text-less PDF read from page images via the configured Gemini model; sections flagged `read_from_image` with a visible "check the wording" notice; a zero-section document shown as error/warning, never "parsed" | **PARTIAL** |
| 6 | A "What I understood" view for every document: type, summary, required … *(the instruction was truncated mid-sentence; I assessed what is legible)* | **PARTIAL** |

### 1 — Import crash + 3.11/3.12 — PARTIAL

- Crash fixed: `app/agents/gaps.py:5` imports `Optional`; used at `app/agents/gaps.py:32`; 41/42 modules import cleanly.
- Tests pass: **52 passed, 0 failed** — but on **Python 3.14.7 only**. 3.11 and 3.12 are not installed and cannot be installed in this environment. Static scan found no 3.12+-only syntax, but **I did not execute on either version**, so the second half of this item is unverified. `pyproject.toml:11` claims `>=3.11`.

### 2 — One shared pool, no per-query connect — DONE

- `app/repositories/database.py:56-64` — single `psycopg_pool.ConnectionPool`.
- `app/main.py:24` — created once in `lifespan`; `app/main.py:32` — closed on shutdown.
- `app/repositories/database.py:91-93` — `get_connection()` checks out from the pool.
- Only `psycopg.connect` in the tree is `scripts/check_db.py:31` (standalone script).
- Measured: `GET /api/me` on a warm cache costs **0** connections; `GET /api/projects` costs **1**.

### 3 — Background run, polling, no UI timeout — PARTIAL

Done:
- `app/api/runs.py:33` — `background_tasks.add_task(...)`. Measured against real uvicorn: **`POST /runs` returned in 0.003 s** with `status=running`.
- `app/ui/streamlit_app.py:546-575` — polls `GET /api/runs/{id}`, re-runs every 1.5 s, renders stage name, real progress bar (computed at `app/repositories/database.py:2170-2187`), and a Cancel button.
- Polling an in-flight run costs 2 connections / 2 queries — cheap.

Not done — the answer path blocks:
- `app/api/questions.py:63` calls `start_or_resume_project_run(...)` **synchronously inside the HTTP request**. `app/graph/build_graph.py:293-297` shows that function creates a run and calls `execute_project_run_background` **directly, in-process, not as a background task**.
- So answering the last critical question re-runs the entire pipeline — every Gemini call, every database round trip — while the user's request is open. The UI client's timeout for that call is **30 s** (`app/ui/api_client.py:14`, no override on `answer_question`). On the Tokyo database with real Gemini this will exceed 30 s on any realistic document.
- It took only 0.04 s in my measurement because the mock model and local SQLite make the pipeline trivial. That is a measurement artefact, not a result.

Also: `BackgroundTasks` ties runs to the process. A restart mid-run leaves the row stuck at `running` forever; nothing reconciles it.

### 4 — Multi-file uploader — NOT DONE

- **One file at a time.** `app/ui/streamlit_app.py:615-619` is a single `st.file_uploader(...)` **without `accept_multiple_files=True`**, assigned to `uploaded_file` (singular). The API is single-file too: `app/api/documents.py:19` is `file: UploadFile = File(...)`.
- **No per-file result lines**, because there is only ever one file. `streamlit_app.py:637` prints one success line for that file.
- **"A failing file does not stop the others"** is vacuous — there are no "others".
- **Duplicates are not reported; they crash.** Measured, uploading identical content three times:

  | attempt | result |
  |---|---|
  | #1 | HTTP **201** |
  | #2 | HTTP **500** Internal Server Error |
  | #3 | HTTP **500** Internal Server Error |

  Cause: `documents.py:45` computes the SHA-256, then `database.py:1200-1210` inserts with a hardcoded `version = 1`, and both `schema.sql` and the SQLite mirror carry `UNIQUE (project_id, checksum, version)`. The `IntegrityError` is never caught, so the user gets a bare 500 instead of "you already uploaded this file".
- **Orphaned files on disk:** `documents.py:52-53` writes the file to disk *before* parsing and *before* the insert, with no cleanup on failure. After the three attempts above: **1 document row, 3 files on disk.** Every duplicate and every parse failure leaks a file.

### 5 — Scanned-PDF path — PARTIAL

Done:
- `app/services/document_parser.py:186-198`: a page with `< 30` characters of text layer is rendered at 150 dpi (`page.get_pixmap(dpi=150)`, `pix.tobytes("png")`) and sent to `llm_service.extract_text_from_image`.
- `llm_service.py:53-83` uses the **configured** model (`self.model_name`, from `LLM_MODEL`) via `google.genai` with `types.Part.from_bytes` — the brief's requirement that the model name come from the environment is honoured.
- `document_parser.py:211/228` sets `read_from_image` **per section**; `:233-234` appends the warning **"Read from images, check the wording."**
- That warning is visible in the UI in two places: `streamlit_app.py:662-666` (amber banner on the document row) and `:675-676` (`st.warning` inside the "What I understood" view).
- The database column exists and is migrated for existing Postgres deployments (`database.py:77-86`, `ADD COLUMN IF NOT EXISTS read_from_image`).
- **Zero-section documents are an error, never "parsed":** `document_parser.py:35-36` raises `DocumentParserError`, surfaced as HTTP 400. Measured with an empty file: **HTTP 400 — "Document 'empty.txt' produced zero usable text sections. It may be empty or unreadable."** The document row is never created, so it can never show as parsed.

Not done:
- **With `LLM_PROVIDER=mock` — the current `.env` — the image path returns invented text.** `llm_service.py:45-51` returns a fixed block mentioning "proof of enrollment", "the 15th of the month" and "$50" **regardless of what is on the page**. That text is then parsed into sections, stored, and mined for evidence, rules and questions. It is flagged `read_from_image` and carries "check the wording", but a reviewer reading that notice will assume the wording is an imperfect transcription of *their* document, not fiction. See [F5](#f5).
- **No OCR failure is recorded on the document.** If the Gemini call throws, `document_parser.py:197-198` appends a warning *and the page simply contributes no text*. If every page is an image and every call fails, the document is rejected (good), but a partial failure silently drops pages from an otherwise "parsed" document.
- **One Gemini call per image page, serial, unpaced, with no timeout** — no delay between calls, no 2-call concurrency cap, and `settings.llm_timeout_seconds` is never passed to the client. A 100-page scan is 100 serial vision calls inside one HTTP upload request (client timeout 60 s).

### 6 — "What I understood" view — PARTIAL

The instruction was cut off at *"type, summary, required"*, so I assessed the view against what is legible plus brief §10.9.

Done:
- `app/ui/streamlit_app.py:672` renders an expander **"🔍 What I understood from {filename}"** for **every** document whose `parse_status == "parsed"`.
- Backed by a real endpoint: `GET /api/documents/{id}/understanding` (`app/api/documents.py:88-130`), membership-checked, returning `DocumentUnderstandingResponse`.
- It covers all seven categories the prompt asks for: **document type, summary, required documents, process steps, fees and waivers, dates and deadlines, people/roles/responsibilities**, plus `missing_or_uncertain_information`.
- Each item carries an **exact quote and page number**, and is badged **`✅ [FACT]` vs `💡 [INTERPRETATION]`** from `is_extracted_fact` (`streamlit_app.py:691-699`) — a good, honest touch.
- `read_from_image` surfaces the "check the wording" warning here too.

Not done / problems:
- **Quotes in this view are never verified.** The evidence pipeline checks `quote not in section_text` and discards failures (`app/agents/evidence.py:39-41`); this endpoint does **no such check** — it returns whatever the model emits, with a page number, straight to a `✅ [FACT]` badge. That is exactly the fabricated-citation risk the brief forbids (Part 4.3, Appendix rule 6).
- **One LLM call per document on every page render.** `get_document_understanding` is **not** in the `st.cache_data` list (`streamlit_app.py:27-78` caches 13 other calls but not this one), and the result is never persisted. Streamlit executes an expander's body even while it is collapsed, so opening Project Overview with 5 documents fires **5 Gemini calls**, again on every rerun — and the page reruns every 1.5 s while a run is polling.
- A document with `parse_status == "failed"` gets no understanding view — defensible, but note that failed parses never produce a row at all, so this branch is effectively dead.

---

## 6. Findings, most serious first

<a name="f1"></a>
### F1 — The two endpoints that show clarification questions return HTTP 500, and the UI hides it

**Severity: blocker.** Reproduced on `TestClient` and on a real uvicorn server.

`app/repositories/database.py:1715` appends evidence links as plain id strings:

```python
elif ttype == "evidence":
    res["linked_evidence"].append(str(tid))
```

`app/schemas/clarification.py:48` declares:

```python
linked_evidence: List[Dict[str, Any]] = []
```

A `str` is not a `Dict`, so FastAPI's response validation raises. Measured on a 5-question project:

```
GET /api/projects/{id}/questions  -> HTTP 500
GET /api/me/questions             -> HTTP 500

kind                 count  rules  steps  evidence
missing_actor            3      0      3         0
conflicting_rules        1      2      0         0
ambiguous_term           1      0      0         1   <-- the trigger
```

```
ResponseValidationError: {'type': 'dict_type', 'loc': ('response', 25, 'linked_evidence', 0),
 'msg': 'Input should be a valid dictionary', 'input': 'b3a27365-…'}
```

**One `ambiguous_term` question is enough to break both endpoints**, and `ambiguous_term` fires on any text containing "eligible", "appropriate", "as soon as possible", "timely", "proper", "reasonable" or "as deemed fit" (`app/agents/gaps.py:11-13`). Both of your own fixtures plant "eligible students" deliberately. In practice this triggers on the first run, every time.

Only `ambiguous_term` questions attach evidence links (`gaps.py:155`), which is why `conflicting_rules`- and `missing_actor`-only projects appear to work and why the test suite never notices.

**It fails silently.** `app/ui/api_client.py:111` and `:115` both read `return resp.json() if resp.status_code == 200 else []`. So the Questions & Rules page and "Waiting for me" render **an empty list** — the Process Owner is shown "no questions" while the run sits at `waiting_for_human`. A visible error would be far less damaging than this.

Fix: return dicts (ideally `{id, evidence_key, quote, document_name, section_title, page_number}` — which is what brief §7.12 requires the question screen to show anyway), or relax the field to `List[str]`. The first option fixes F1 and part of F12 together. Separately, make `api_client` surface non-200s instead of returning `[]`.

<a name="f3"></a>
### F3 — Answering a question never closes the loop; the run re-pauses forever and no documents are ever generated

**Severity: blocker.** Reproduced.

`app/api/questions.py:54-63`: when no critical question remains open, the handler calls `start_or_resume_project_run(project_id, user["id"])`. But `app/graph/build_graph.py:293-297`:

```python
def start_or_resume_project_run(project_id: str, user_id: str) -> Dict[str, Any]:
    """Initiates a new run and executes it synchronously (used in tests)."""
    run = db.create_run(project_id, started_by=user_id)
    execute_project_run_background(run["id"], project_id, user_id)
    return db.get_run(run["id"])
```

This is not a resume. It **creates a new run and re-enters the graph at `ingest`**. Re-running `ingest → evidence → as_is → rules → gaps` re-extracts everything into new rows with new UUIDs; the gap detector then regenerates the same problem as a **new** question, because fingerprints embed those UUIDs (`gaps.py:43` `f"missing_actor|{project_id}|{step['id']}"`, `:100` `f"conflicting_rules|{r1['id']}|{r2['id']}"`). A new open critical question exists, so the router pauses again.

Measured — answering every open critical question, three rounds:

```
after first run            questions=  1 open=1 open-critical=1 runs={'waiting_for_human': 1} artifacts=0
after answering round 1    questions=  2 open=1 open-critical=1 runs={'waiting_for_human': 2} artifacts=0
after answering round 2    questions=  3 open=1 open-critical=1 runs={'waiting_for_human': 3} artifacts=0
after answering round 3    questions=  4 open=1 open-critical=1 runs={'waiting_for_human': 4} artifacts=0
```

`open-critical` never reaches 0. A `waiting_for_human` run row accumulates each time. **`artifacts` stays 0 forever.**

Consequences — none of these is reachable through the product's normal flow:
- To-Be proposal and automation assessment
- requirements rows, BRD, PRD, FRD, SRS
- workflow JSON, test cases, UAT pack
- traceability matrix, roles matrix, rules catalogue, HLD, data model

Against the brief's Friday acceptance checklist: *"A human answers; the answer is stored with name, role and time; the run resumes"* and *"BRD/FRD/PRD generated with a DRAFT banner and linked IDs"* both fail.

And per item 3 above, this re-run happens **synchronously inside the answer request**, so with real Gemini it will also blow the UI's 30 s timeout.

Two things are needed: fingerprints that are stable across runs (derive them from durable identity — section index plus normalised step/rule text — not row UUIDs), and a resume that re-enters the graph **after** `gaps` rather than at `ingest`, dispatched as a background task.

<a name="f5"></a>
### F5 — The shipped configuration invents document content and presents it as fact

**Severity: critical.**

`.env` contains **`LLM_PROVIDER=mock`**. Nothing in the UI says so. I grepped `app/ui/` for "mock" — **no match**. There is no badge, no banner, no footer note.

What that means in normal use:
- `llm_service.py:45-51` — a scanned PDF page returns a **fixed, invented** block: *"All applicants must submit proof of enrollment and valid identification. Fee waiver requests must be submitted before the 15th of the month. The application fee of $50 is non-refundable unless waived by the Process Owner."* It has nothing to do with the uploaded page. It is then stored as section text and mined for evidence, rules and questions.
- `llm_service.py:161-342` — every agent gets synthesised output. Evidence/rules quotes are sliced from the real text (so the verbatim check passes), but the **To-Be process is entirely hardcoded** (`:255-294`: "Submit digital application via online portal", "Automated criteria and document check", …) with no relation to the uploaded documents, and it is presented in the UI as the AI's redesign proposal for the user's process.

Credit where due: there is **no silent gemini→mock fallback.** `llm_service.py:100-104` raises a clear error when `LLM_PROVIDER=gemini` and the key is empty, and `test_gemini_provider_fails_without_silent_mock_fallback` passes. The hole is the explicit configuration, not a fallback.

Also missing, and required by brief Phase 0 step 3: the line near the upload box **"Text from your documents is sent to Google Gemini. Use only non-sensitive documents."** I grepped `streamlit_app.py` for "Gemini" — no match. Users are never told their documents leave the machine.

Fixes: set `LLM_PROVIDER=gemini` in `.env`; restrict `mock` to test environments the same way SQLite already is (`database.py:34-49` is the pattern to copy); render a persistent, unmissable banner whenever the provider is not `gemini`; and add the Gemini data-sharing notice.

<a name="f6"></a>
### F6 — Every run duplicates all extracted data and re-bills every model call

**Severity: high.** Measured (table in §3.4): questions 5 → 10 → 15, rules 3 → 6 → 9, evidence 5 → 10 → 15 across three runs of the same unchanged document.

`evidence.py:58-63` and `rules.py:79-85` loop over **every** section on every run with no check for existing rows. The brief's Phase 0 requirement — *"remember results already stored so a re-run does not repeat calls for unchanged sections"* — is not implemented. Brief 7.11 step 7 (*"Existing records are kept; anything that depends on changed records is marked stale"*) is half-met: records are kept, but duplicated, and nothing is ever marked stale.

Costs: duplicate evidence/rules/questions in every view; Gemini billed in full on every run; and, combined with F3, unbounded growth each time anyone answers a question.

<a name="f2"></a>
### F2 — Running `pytest` on a configured machine writes to the production database

**Severity: high.** This is what bit me (§0.1).

Two independent causes:
1. `app/core/config.py:24-26` reads `.env` through Pydantic's `env_file`, so clearing the shell variable does not clear the setting. To actually get an empty value you must set `DATABASE_URL=""` explicitly.
2. `tests/test_latency_benchmarks.py` is the only test file without a DB-isolation fixture, and it performs 24 write calls through `TestClient` — registering users, creating projects, uploading documents, starting runs — with **no cleanup**.

So `pytest` on any developer machine with a populated `.env` silently writes benchmark users and projects into Supabase. Evidence: 48.87 s (live) vs 6.85 s (isolated).

Fix: add a root `tests/conftest.py` with a session-scoped autouse fixture that forces `db.use_postgres = False` and a temp SQLite path for the whole suite, and refuse to run if `settings.database_url` is non-empty unless an explicit opt-in variable is set.

<a name="f7"></a>
### F7 — Hardcoded default signing key

**Severity: high.** `app/core/config.py:9` (and `:42`):

```python
secret_key: str = "pfai_default_secret_key_8f3a9e2c1b7d4e5f6a0c8b9d"
```

If `SECRET_KEY` is missing, token signing silently falls back to a constant that is in the source tree. `permissions.py:12` builds the serializer from it at import. Anyone with the source can mint a token for any `user_id`. There is no startup validation.

`.env` does set a 44-char `SECRET_KEY`, so this instance is not currently exposed — but any fresh clone or forgotten variable is. Fail fast on an unset `SECRET_KEY` instead of defaulting, exactly as `database.py:34-49` already does for `DATABASE_URL`.

<a name="f8"></a>
### F8 — A read-only page view writes to the database and can destroy an approval

**Severity: high.** `app/api/traceability.py:19` — a `GET` handler — calls `quality_agent.validate_traceability(project_id)`, which **writes three artifacts**: `traceability_matrix` (`quality.py:68`), `hld` (`:101`) and `data_model` (`:121`). I measured `INSERT OR REPLACE INTO artifacts` ×3 during a single `GET /traceability`.

`save_artifact` (`database.py:1967-1987`) defaults to `version=1` and `status="draft"`, and on conflict does:

```sql
ON CONFLICT (project_id, artifact_type, version)
DO UPDATE SET content_json = EXCLUDED.content_json, markdown = EXCLUDED.markdown, status = EXCLUDED.status;
```

`status = EXCLUDED.status` means **`status` is reset to `'draft'`**. All three of these types are in `TECHNICAL_ARTIFACTS`, so once a Technical Reviewer approves the traceability matrix, HLD or data model, **the next person to open the Traceability page silently reverts it to draft.** `approved_by` is left set, producing an inconsistent row (`status='draft'` with an approver) that no longer satisfies the schema's intent.

I could not execute the end-to-end proof of the approval being lost, because reaching an artifact at all requires getting past F3 — I attempted it twice and the run re-paused both times. The mechanism is unambiguous from the code and the measured writes; treat it as confirmed-by-inspection, not confirmed-by-experiment.

It also makes a `GET` cost 85 connections and 130 queries (~10 s from India on the Tokyo host). Move generation to the run, and make the endpoint read-only.

<a name="f4"></a>
### F4 — Spec-to-test traceability is not real

**Severity: high**, because it is what let F1 and F3 ship.

The specs each end with a "Tests" section naming the pytest functions that prove their acceptance criteria. I checked all **32** named functions against `tests/`:

> **Not one of them exists.** 32 of 32 missing.

Including `test_approval_constraint_requires_user`, `test_project_isolation_filter`, `test_evidence_rejects_unverified_quote`, `test_run_pauses_on_critical_question`, `test_answer_creates_verified_fact_and_supersedes_conflict`, `test_mark_unknown_allows_resume_with_flag`, `test_requirements_linked_to_rules`, `test_traceability_chain_complete`, `test_permission_matrix_analyst_cannot_approve_rule`, `test_seed_demo_accounts`.

Also: **no test cites an `AC-` id** anywhere (`grep -c "AC-" tests/*.py` → 0 in all ten files), though `SPEC-nn` ids do appear in some docstrings. The brief requires *"Every test name or docstring cites the acceptance criterion it proves"* and *"A final check lists every SPEC- ID and confirms it has at least one passing test"*. Neither holds. `specs/tasks.md` marks all 22 tasks `[x]`.

The existing 52 tests are not worthless — they do cover parsing, quote verification, lockout, conflict separation, fingerprinting. The problem is **what they test through**:
- `tests/test_api.py:179-205` (`test_srs_artifact_generation`) calls `requirements_agent.generate_all_artifacts(pid)` **directly**, bypassing the graph and the HITL gate. It proves artifacts *can* be generated, which is true, while F3 makes them unreachable in the product.
- `tests/test_graph_routing.py:15-60` calls `check_critical_gaps_router(state)` with a **hand-built state dict**. It never executes the compiled graph, so the resume path — the thing that is broken — is never exercised.
- No test calls `GET /api/projects/{id}/questions` or `GET /api/me/questions` with an `ambiguous_term` question present. That is the exact gap F1 lives in.

Add end-to-end tests that drive the HTTP API through the full loop: upload → run → poll → read questions **over HTTP** → answer → poll → assert artifacts exist.

<a name="f9"></a>
### F9 — The SQLite mirror enforces none of the schema's safety constraints, and the tests run on SQLite

**Severity: medium-high.**

| | `schema.sql` | SQLite mirror in `database.py` |
|---|---|---|
| `CHECK` constraints | **40** | **0** |
| `CHECK (status <> 'approved' OR approved_by IS NOT NULL)` | 4 tables (lines 162, 209, 311, 339) | **absent** |
| Append-only audit trigger | yes (line 410) | **absent** |
| Row Level Security | yes (line 423) | n/a |
| Table count | 28 | 28 (names all match; `scripts/check_db.py` also expects the same 28 — consistent) |

`DEVIATIONS.md` §5 says both adapters "enforce constraints". They do not. Because every isolated test runs on SQLite, the constraint-backed acceptance criteria — above all **AC-01-03**, "an attempt to set `status = 'approved'` with `approved_by = NULL` is rejected" — are **not proven by anything**. `test_approval_constraint_requires_user` does not exist (F4).

The application layer does set `approved_by` correctly on the approval path I read (`artifacts.py:114`), so this is a missing safety net rather than a live breach. But the net is exactly what the brief asked for, and the claim that it exists is wrong.

<a name="f10"></a>
### F10 — Gap detection is narrower than specified, and invents conflicts it should not

**Severity: medium.**

`app/agents/gaps.py` implements three checks. `SPEC-07-01` and brief step 9 require four:
- ✅ `missing_actor` (`:40-69`)
- ✅ `conflicting_rules` (`:74-130`)
- ✅ `ambiguous_term` (`:135-162`)
- ❌ **`missing_info` — not implemented at all.** No detector produces that kind, though `QuestionKind` includes it.
- ❌ **Repeated/duplicate step — not implemented.** Both fixtures plant one (`manifest.json`: *"The scholarship clerk cross-checks student income certificates…"* in sections 4 and 6), brief 9.1 requires it, and brief §10.5 even specifies the UI note *"Repeats step 3"*. Nothing detects it.
- ❌ **Missing piece — not implemented.** Both fixtures plant one ("No appeal procedure for rejected applicants"); nothing detects it.

Worse, the conflict check is **dates only and hardwired to deadlines**:
- `:74` matches only `\d{1,2} <month name>` or `\d{1,2}/\d{1,2}/\d{2,4}`. Two different **fee amounts** or **GPA limits** are never flagged, although brief 9.1 names *"two different deadlines, fees or limits"*.
- `:91` builds the question text `f"Which submission deadline is correct: {date1} or {date2}?"` and `:99-102` the reason *"Two places state different deadlines"* — asserted even when the dates are not deadlines at all. That is close to the process-specific templating Appendix rule 4 forbids.
- `:86-90` compares **every pair** of date-bearing rules, with no same-topic test. On a 20-section document this generated **29 questions** from one file. Brief 9.1 requires that *"no extra problems are invented"*. This invents them combinatorially (O(n²)).
- `:50-56` offers hardcoded invented actor options — "Administrative Clerk", "Process Officer", "Department Committee" — presented as `options` rather than as the clearly-labelled AI suggestion the brief requires for anything the AI made up.

<a name="f11"></a>
### F11 — Two routing rules the brief calls mandatory are not wired into the graph

**Severity: medium.**

1. **Bounded repair loop is dead code.** `app/graph/build_graph.py:7` imports `quality_repair_router`, and `tests/test_graph_routing.py` tests it in isolation — but it is **never passed to `add_conditional_edges`**. `build_graph.py:247` wires `quality → complete` unconditionally. `SPEC-09-04` and brief 3.5 require *"at most two repair attempts; then save the error report and mark Needs Review"*. The function exists, the test passes, the behaviour is absent.
2. **No To-Be approval gate.** `build_graph.py:244` wires `to_be → requirements` directly. Brief 3.5 requires *"To-Be not approved → do not generate final/approved downstream artifacts"* and 7.11 step 5 requires waiting for the Process Owner. Mitigating: everything is generated as `status="draft"`, and the approval endpoints are correctly role-gated, so nothing is ever auto-approved. The ordering requirement is still unmet.

<a name="f12"></a>
### F12 — Questions do not carry the context brief §7.12 requires

**Severity: medium.** §7.12 is marked "required" and lists six things every question must show. Measured against stored records:

| Required | State |
|---|---|
| Project name | ✗ not on the question record |
| Question key `Q-001` | ✓ |
| Plain templated question | ✓ (but see F10 on the hardwired "deadline" wording) |
| Why it matters (`reason`) | ✓ |
| Per source: letter (A, B) | partial — `"Option A:"` / `"Option B:"` prefixes in `options` |
| Per source: exact quote | ✓ for `conflicting_rules` only (`gaps.py:112-113`) |
| Per source: document file name | ✓ for `conflicting_rules` only |
| Per source: section number **and** title | partial — `section_title` only; **no `section_index`** |
| Per source: page number for PDFs | ✗ **never populated**, though `ClarificationOption.page_number` exists (`schemas/clarification.py:25`) |
| "Another \<value\> or rule" + text box | ✓ (`gaps.py:114`) |
| AI suggestion, clearly labelled | ✓ — strings begin "AI suggestion, not a fact:" |
| What happens after the answer | ✗ `consequence_summary` is in the response schema (`:45`) but nothing ever sets it |

`missing_actor` and `ambiguous_term` questions carry **no source block at all** (no quote, document or section in their options), so a Process Owner cannot answer them without opening the document separately — the precise failure §7.12 exists to prevent.

Also: §7.12 requires *"never create a `conflicting_rules` question without links to both rules"* — this **is** honoured (`gaps.py:124`, `link_targets=[("rule", r1["id"]), ("rule", r2["id"])]`); I verified both links are stored.

<a name="f13"></a>
### F13 — Invitation e-mail: implemented but undocumented, unconfigured, and missing its resend path

**Severity: low-medium.**

- `README.md` lists "Email delivery not implemented … Integrate an SMTP/SendGrid service to activate" as a known limitation. **Wrong.** `app/api/team.py:15-40` sends a plain-text message over `smtplib` + `starttls()`, with the brief's exact subject format, the role, the `APP_BASE_URL` link, and **no token or project content** — as §7.4 requires.
- It is simply **unconfigured**: `.env` has no `SMTP_*`, so `team.py:18` returns `False` immediately and `email_status` stays `not_sent`. Correct degradation, wrong documentation.
- `team.py:39-40` is `except Exception: return False` — the error is swallowed with no logging, whereas §7.4 says *"Log the error without the password."*
- **`POST /api/invitations/{id}/resend` does not exist.** The brief lists it in §5.2a and §7.4 requires a "Resend e-mail" button with limits (max 5 per invitation, 20 per project per day). No route, no limit enforcement — though `resend_count` is in both schemas.
- Also absent from the route table: nothing else. All other §5.2/§5.2a endpoints are present.

<a name="f14"></a>
### F14 — Smaller items

| Item | Evidence |
|---|---|
| Audit hash chain has no row lock | `database.py:480-491` reads the latest hash then inserts, with no `SELECT … FOR UPDATE`. Brief 8.4 requires locking. Concurrent events fork the chain. |
| Rules can be linked to unrelated evidence | `app/agents/rules.py:56-57`: if no quote matches, `matched_eids.append(sec_evidence[0]["id"])` — attaches the rule to whichever evidence item happens to be first. A traceability link that asserts support which does not exist. |
| `LLM_TIMEOUT_SECONDS` is dead | read at `llm_service.py:25`, never passed to the Gemini client. |
| No LLM pacing or concurrency cap | brief Phase 0 requires a short delay between section calls and ≤2 concurrent; `evidence.py:58-63`, `rules.py:79-85` are bare serial loops. |
| Orphaned upload files | `documents.py:52-53` writes before parsing/inserting with no cleanup. Measured: 3 attempts → 1 row, 3 files. |
| Upload size checked after full buffering | `documents.py:26-34`. |
| MIME never validated | extension-only; `evil.exe.txt` with binary content accepted (201). |
| `.md` accepted but not advertised | `documents.py:38` allows it; `:42` error text names only pdf/docx/txt. |
| Streamlit XSRF and CORS disabled | `.streamlit/config.toml`. |
| API CORS wide open | `main.py:42-48`, `allow_origins=["*"]` + `allow_credentials=True`. |
| `check_permission` fails open | `permissions.py:97-133`; unknown action or unclassified artifact type → allowed for all roles. Not reachable via the 12 real artifact types, which are all classified. |
| `_user_cache` unbounded | `permissions.py:52`; TTL-only, never evicted. |
| Module-level DB side effect at import | `database.py:30-32` — `DatabaseRepository.__init__` calls `_init_sqlite()`, creating/touching `data/processfoundry.db` merely by importing the module. |
| `.venv` is a Windows venv | `pyvenv.cfg` points at `C:\Users\ASUS\…\cpython-3.12-windows-x86_64`; unusable on macOS/Linux. `README.md:116` also hardcodes `c:\Users\ASUS\OneDrive\Desktop\…`. |
| README demo roles contradict the seed script | §3.5 table above. |
| README PDF claim is wrong | says ">100 pages may be slow … with timeout"; code **rejects** >100 pages and has no timeout. |
| README "known limitation" about `clarification_answers` | the table exists in all three places (schema.sql, SQLite mirror, `check_db.py`); the warning is stale. |
| Specs reference files that do not exist | `app/repositories/base.py`, `projects.py`, `users.py`, `clarification.py`, `app/agents/hitl.py`, `app/services/validators.py`, `app/schemas/team.py`, `app/ui/pages/` are all named in specs/`tasks.md` and none exist. The real code is consolidated into `database.py` (2241 lines) and `streamlit_app.py` (1305 lines). |

---

## 7. What is genuinely good

Stated plainly, because the findings above are heavy and this part is real:

- **Connection pooling is done properly** — one pool, created once in `lifespan`, shared, closed on shutdown, no stray `connect` calls. Verified.
- **Background runs work.** `POST /runs` returns in 3 ms; the UI polls a 2-query status endpoint every 1.5 s and shows a real, node-derived progress percentage.
- **Project isolation is airtight** on every one of ~25 routes I probed, including the id-addressed ones: 404 to non-members, 401 without a token.
- **Removal and role changes take effect immediately** — membership is read fresh on every request, and the 60 s cache deliberately holds only the user row.
- **No SQL injection.** One f-string query, interpolating only fixed literals.
- **No path traversal.** `../../escape.txt` wrote nothing outside `uploads/`; storage paths are server-generated UUIDs; filenames are display-only.
- **Verbatim quote verification is honest** — `evidence.py:39-41` discards any claim whose quote is not a substring, and logs it. (The "What I understood" endpoint is the one place that skips this; see item 6.)
- **No silent gemini→mock fallback**, with a passing test to prove it.
- **The audit log is a real SHA-256 chain**, not a label.
- **Invitation security is correct** — wrong-account accept returns 403.
- **Zero-section documents are rejected with a clear 400**, never shown as parsed.
- **The scanned-PDF path exists and is wired to the configured model**, flags sections `read_from_image`, carries the "check the wording" notice in two UI places, and ships a safe idempotent Postgres migration for the new column.
- **`schema.sql` is byte-identical to the brief's appendix**, and the 28 tables are consistent across schema, SQLite mirror and `check_db.py`.
- **The fixtures are good work** — two genuinely different processes, all five planted defect classes plus clear facts that must not be flagged, recorded in a machine-readable `manifest.json`.
- **Section 10.9 is implemented faithfully.** All eight palette tokens are present in `app/ui/theme.py` (`#101f36`, `#f5f7fb`, `#15243a`, `#e5eaf1`, `#3568f5`, `#2455df`, `#eaf0ff`, `#0d9b8a`), Inter is loaded, and `.streamlit/config.toml` matches.
- **The `✅ [FACT]` / `💡 [INTERPRETATION]` badging** in the understanding view is a genuinely good idea that the brief did not ask for.

---

## 8. Suggested order of work

1. **F1** — change `linked_evidence` to return dicts with quote, document, section and page. Unblocks the Questions page and "Waiting for me", and covers most of F12. Also make `api_client` stop converting errors into `[]`.
2. **F3** — make fingerprints stable across runs (section index + normalised text, not row UUIDs), and make resume re-enter after `gaps` as a background task. Unblocks every downstream artifact.
3. **F5** — set `LLM_PROVIDER=gemini`; gate `mock` behind the test-environment check that `database.py:34-49` already implements; add a persistent provider banner and the Gemini data-sharing notice.
4. **F2** — add `tests/conftest.py` forcing SQLite isolation suite-wide, and make the suite refuse to run against a non-empty `DATABASE_URL`.
5. **F7** — fail fast on an unset `SECRET_KEY`.
6. **F8** — stop `GET /traceability` from writing; never let `save_artifact` reset `status`.
7. **F4** — add end-to-end HTTP tests for the full loop; then reconcile the spec "Tests" sections with reality (rename the tests or the specs, but make them match).
8. **F6** — skip sections whose evidence already exists; mark dependants stale instead of duplicating.
9. **Performance** — batch `list_project_clarification_items` into one JOIN (31 connections → 1), and move the database to `ap-south-1` (Mumbai). Do both; the N+1 fix is the larger win and the region change compounds it.
10. **F9–F14** — constraints in the SQLite mirror, the missing `missing_info`/duplicate-step/missing-piece detectors, the repair loop and To-Be gate, the resend endpoint, CORS, MIME validation, and the README corrections.

---

## 9. Explicitly not verified

In the interest of not overclaiming:

- **Tests on Python 3.11 / 3.12** — not installed, no installer available. Static scan found no 3.12+-only syntax; execution was impossible.
- **Whether my first `pytest` run actually created rows in Supabase** — the confirming `SELECT` was blocked by this environment's production-read guard and I did not work around it. The circumstantial evidence (§0.1) is strong.
- **Any measurement against the real PostgreSQL instance.** All query and connection counts in §3.2 were taken on temp SQLite. The *shapes* (N+1, per-item loops, counts) are identical on both paths; the *per-query cost* is what differs, and that is where Tokyo RTT multiplies them. One genuinely Postgres-specific difference I did check and report: key minting is atomic on Postgres and read-then-write on SQLite.
- **F8's approval loss, end to end.** The mechanism is certain from the code plus the measured `INSERT OR REPLACE` writes, but I could not reach an approvable artifact through the API because F3 blocks the path. Confirmed by inspection, not by experiment.
- **Any real Gemini call.** Everything ran with `LLM_PROVIDER=mock`, deliberately — no API spend, no network. So real-model behaviour (actual JSON conformance, real retry/rate-limit handling, real OCR quality) is untested by me.
- **The Streamlit UI rendered in a browser.** All UI findings come from reading `streamlit_app.py` (1305 lines), `theme.py` and `components.py`, plus the API behaviour behind them. I did not take screenshots.
- **`uploads/` and `data/processfoundry.db` contents.** Names and counts only (102 upload files, one 385 KB SQLite file), per the review rules.
- **Acceptance item 6's full requirement** — the instruction was truncated at "type, summary, required". I assessed the view against the legible part plus brief §10.9.
- **Concurrency failure modes** (the audit-chain fork, the SQLite minting race) are reasoned from the code. I did not run concurrent writers to trigger them.

---

*End of report. No source file was modified during this review.*
