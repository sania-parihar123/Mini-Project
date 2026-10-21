# ProcessFoundry AI

> **Enterprise Process Discovery, Redesign & Specification Platform**  
> AI-assisted extraction of As-Is processes, conflict detection, To-Be redesign, and full requirements artifact generation — with every claim grounded in a verbatim quote from a source document.

---

## Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Installation](#installation)
5. [Database Configuration](#database-configuration)
6. [Running the Application](#running-the-application)
7. [Demo Walkthrough](#demo-walkthrough)
8. [Test Suite](#test-suite)
9. [Security and Permissions](#security-and-permissions)
10. [Known Limitations](#known-limitations)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Streamlit UI  (localhost:8501)                             │
│  12-page SaaS layout matching reference_prototype.html      │
│  Deep navy sidebar · light grey-blue bg · blue CTAs        │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPX REST  (Bearer token)
┌────────────────────▼────────────────────────────────────────┐
│  FastAPI Backend  (localhost:8000)                          │
│  /api/auth  /api/projects  /api/documents  /api/runs        │
│  /api/questions  /api/artifacts  /api/team  /api/traceability│
└────────────────────┬────────────────────────────────────────┘
                     │
      ┌──────────────▼──────────────┐
      │  LangGraph StateGraph       │  (app/graph/)
      │  ingest→evidence→as_is      │
      │  →rules→gaps→[PAUSE]        │
      │  →to_be→requirements        │
      │  →testing→quality→complete  │
      └──────────────┬──────────────┘
                     │
      ┌──────────────▼──────────────┐
      │  Database Repository        │
      │  PostgreSQL (production)    │
      │  SQLite (dev / tests)       │
      └─────────────────────────────┘
```

### Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Verbatim grounding** | Every evidence item carries a `quote` verified to be a substring of its source section (enforced in the agent, the repository and the "What I understood" view) |
| **Deterministic routing** | Python code decides pause/resume — not the LLM |
| **AI never auto-approves** | All rules, process models, and artifacts start in `needs_review`; humans must approve |
| **Role-gated answering** | Clarification questions carry an `assigned_role`; only that role can answer |
| **Fingerprinted deduplication** | Each clarification question has a fingerprint; duplicate detection is idempotent |
| **Hash-chained audit log** | Every audit event chains SHA-256 hashes — providing tamper evidence |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Streamlit 1.x |
| **Backend API** | FastAPI + Uvicorn |
| **AI Orchestration** | LangGraph StateGraph |
| **LLM** | Google Gemini via `google-genai` (deterministic mock fallback when `GEMINI_API_KEY` is unset) |
| **Database** | PostgreSQL (production) / SQLite (dev + tests) |
| **Auth** | bcrypt passwords, 8-hour `itsdangerous` signed tokens |
| **Document Parsing** | PyMuPDF (PDF), python-docx (DOCX), built-in (TXT/MD) |
| **Validation** | Pydantic v2 |

---

## Project Structure

```
Project-ProcessFoundaryAI/
├── app/
│   ├── api/               # FastAPI routers (auth, projects, documents, runs, questions, artifacts, team, traceability)
│   ├── agents/            # LangGraph nodes: evidence, discovery, rules, gaps, redesign, requirements, testing, quality
│   ├── core/config.py     # Pydantic settings (reads .env)
│   ├── graph/             # StateGraph: state.py, routing.py, build_graph.py
│   ├── repositories/      # database.py — dual-mode PostgreSQL/SQLite repository (29 tables)
│   ├── schemas/           # Pydantic request/response models
│   ├── services/          # document_parser, llm_service, permissions, artifact_export
│   ├── ui/                # Streamlit: streamlit_app.py, api_client.py, theme.py, components.py
│   └── main.py            # FastAPI application entrypoint
├── tests/
│   ├── fixtures/          # scholarship_sop.txt, hostel_allotment_policy.txt, manifest.json
│   ├── test_parsing.py
│   ├── test_evidence.py
│   ├── test_rules_gaps.py
│   ├── test_auth_permissions.py
│   ├── test_graph_routing.py
│   ├── test_api.py
│   ├── test_traceability.py
│   └── test_fixtures.py
├── scripts/
│   ├── run_dev.ps1        # Windows PowerShell dev runner
│   ├── seed_demo.py       # Seed demo users and project
│   └── check_db.py        # Verify the 29-table schema
├── specs/                 # 17 spec files (00-overview through 16-visual-design)
├── schema.sql             # Authoritative 29-table PostgreSQL schema
├── .env.example           # Template for environment variables
├── pyproject.toml         # Python project metadata and pytest config
└── DEVIATIONS.md          # Documented deliberate decisions
```

---

## Installation

### Prerequisites

- Python 3.11+ (`pyproject.toml` requires `>=3.11`). The suite has been run on 3.14.7; it has **not** been executed on 3.11 or 3.12, so treat those as unverified.
- Git

### Steps

```bash
# From the directory you cloned or unpacked this project into
cd Project-ProcessFoundaryAI

# Install the project and its dependencies
pip install -e ".[dev]"
```

### Environment Configuration

Copy `.env.example` to `.env` and configure:

```ini
# .env

# --- Database (PostgreSQL required for normal operation) ---
DATABASE_URL=postgresql://user:password@host:5432/processfoundry

# --- Local Testing Override (restricted to test environments) ---
# Set to true ONLY for isolated automated tests or local offline development
ALLOW_SQLITE=false

# --- Security ---
SECRET_KEY=your-secret-key-change-this-in-production

# --- LLM Gateway ---
LLM_PROVIDER=gemini
LLM_API_KEY=your-gemini-api-key-here
LLM_MODEL=gemini-2.5-flash

# --- File Uploads ---
UPLOAD_DIR=uploads
MAX_UPLOAD_MB=25
```

---

## Database Configuration

### PostgreSQL (Production & Normal Operation — Default)

ProcessFoundry AI uses PostgreSQL as its primary database engine. At application startup, a high-performance shared connection pool (`psycopg_pool.ConnectionPool`) is initialized and reused across database operations, eliminating per-query TLS handshakes and connection overhead.

1. Ensure your PostgreSQL database or Supabase pooler is running.
2. Initialize schema:
   ```powershell
   psql -U postgres -d processfoundry -f schema.sql
   ```
3. Set `DATABASE_URL` in `.env`.
4. The application will validate the database connection and connection pool automatically on startup.

### SQLite (Restricted to Isolated Test Environments)

To prevent accidental production data loss, **SQLite fallback is restricted strictly to test environments**. When running normally without `DATABASE_URL`, the application will fail fast on startup with a clear configuration error.

To enable SQLite for isolated unit/integration tests or local testing:
- Set `ALLOW_SQLITE=true` or `APP_ENV=test` in `.env` or your shell environment.
- Tests running under `pytest` automatically isolate with temporary SQLite databases.

Seed the demo users (when SQLite is enabled or PostgreSQL is configured):

```powershell
python scripts/seed_demo.py
```

This creates three demo accounts (password `Process123!` for all):

| Name | Email | Role (brief 7.10) |
|------|-------|------|
| Aditi Sharma | aditi@example.com | Analyst |
| Rao Mehta | rao@example.com | Process Owner |
| Anil Kapoor | anil@example.com | Technical Reviewer |

### PostgreSQL (Production)

1. Create a database and run the schema:
   ```sql
   psql -U postgres -d processfoundry -f schema.sql
   ```

2. Set `DATABASE_URL` in `.env`

3. Verify the 29-table schema:
   ```powershell
   python scripts/check_db.py
   ```

---

## Running the Application

### Option A: Development Script (Recommended)

**On macOS / Linux:**
```bash
bash scripts/run_dev.sh
```

**On Windows (PowerShell):**
```powershell
.\scripts\run_dev.ps1
```

This starts the FastAPI backend on port 8000 and the Streamlit frontend on port 8501.

### Option B: Manual (Two Terminals)

**Terminal 1 — Backend API:**
```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Streamlit UI:**
```powershell
python -m streamlit run app/ui/streamlit_app.py --server.port 8501
```

Then open **http://localhost:8501** in your browser.

---

## Demo Walkthrough

After seeding the demo data:

### 1. Register or Log In
- Visit http://localhost:8501
- Log in as `aditi@example.com` / `Process123!` (Process Owner)

### 2. Create a Project
- Click **＋ Create a project**
- Fill in the project name, department, goals, and constraints

### 3. Upload Source Documents
- On the Project Overview page, drag-and-drop PDF, DOCX, or TXT files
- The system parses them, computes SHA-256 checksums, and displays section counts

### 4. Start AI Analysis
- Click **Start AI Analysis**
- LangGraph runs: Ingest → Evidence Extraction → As-Is Discovery → Rules → Gap Analysis
- If critical conflicts or missing actors are found, the run **pauses** and creates clarification questions

### 5. Answer Questions (Aditi → Rao workflow)
- **Aditi (Process Owner)** sees questions assigned to her role in **Waiting for me**
- She answers deadline conflicts and provides missing actor names
- Once all critical questions are resolved, the run auto-resumes

### 6. Review To-Be Process
- After resumption: Redesign → Requirements → Testing → Quality validation
- Aditi reviews the proposed To-Be process and approves or requests changes

### 7. Download Artifacts
- BRD, PRD, FRD, Workflow JSON, Traceability Matrix are available for download

### 8. Audit Log
- Every action (upload, run start/pause/resume, answer, approval) is in the hash-chained audit log

---

## Test Suite

```bash
python -m pytest -q
```

The suite needs no setup and no network: `tests/conftest.py` forces a temporary
SQLite database, redirects uploads to a temporary directory and selects the
offline model, and it **refuses to start** if it could reach a real database.

**176 passed, 3 skipped** (the skips are the PostgreSQL-only constraint checks):

| Test File | Coverage |
|-----------|---------|
| `test_test_isolation.py` | The suite cannot reach a live database; `.env` is ignored; a PostgreSQL pool cannot be opened |
| `test_parsing.py` | Document parsing, section detection, checksum, unsupported format rejection |
| `test_uploads.py` | Multi-file batch upload, per-file results, duplicate reporting (409), streaming size limit, MIME validation, no orphan files, server-generated paths |
| `test_evidence.py` | Verbatim quote extraction, fabricated-quote rejection |
| `test_rules_gaps.py` | Conflict preservation as separate rows, missing actor detection, vague term detection, fingerprint deduplication |
| `test_fixtures.py` | Planted defect detection on both fixtures, SHA-256 determinism |
| `test_fixture_defect_coverage.py` | All five planted defect classes found in both fixtures; clear facts not flagged; no invented conflicts; quotes reproducible; no process-specific code |
| `test_questions_endpoint.py` | The question list and "Waiting for me" over HTTP, full brief 7.12 context, one query per list |
| `test_full_loop_e2e.py` | The whole cycle over HTTP: upload → run → poll → read questions → answer → To-Be approval → every document generated; idempotent re-runs |
| `test_graph_routing.py` | Pause on critical questions, resume on resolution, bounded quality repair (≤2 retries) |
| `test_llm_configuration.py` | Mock provider refused outside tests, no silent fallback, pacing and timeout, verified quotes in "What I understood", cached per checksum |
| `test_security_hardening.py` | SECRET_KEY guard, restricted CORS, fail-closed permissions, bounded user cache, fresh membership checks, read-only traceability, approvals never discarded, audit chain, invitation resend limits |
| `test_auth_permissions.py` | bcrypt hashing, registration, login, 5-attempt lockout, token creation, Part 7.9 permission matrix |
| `test_api.py` | FastAPI health, full E2E: register→login→project→upload→run→audit |
| `test_traceability.py` | Quote audit zero mismatches, orphan requirement detection, validation writes nothing |
| `test_new_features.py` | SQLite guard, pool lifecycle, scanned-PDF path, background runs and cancellation |
| `test_latency_benchmarks.py` | Query and connection counts per operation, cold vs warm login, cache hits |
| `test_spec_coverage.py` | Every `SPEC-` id has a citing test; specs name only tests that exist; PostgreSQL-only constraint checks (skipped without `PFAI_TEST_POSTGRES_URL`) |

### Running the PostgreSQL-only tests

Three tests prove constraint semantics the SQLite mirror does not implement. Point
them at a database you are willing to lose:

```bash
createdb pfai_throwaway
psql -d pfai_throwaway -f schema.sql
PFAI_TEST_POSTGRES_URL=postgresql://localhost/pfai_throwaway python -m pytest tests/test_spec_coverage.py -q
```

### Spec-to-test traceability

Each spec's `## Tests` section is generated from the suite; every test cites the
`SPEC-`/`AC-` ids it proves. `test_every_spec_id_has_a_covering_test` fails if a
declared requirement loses its coverage.

---

## Security and Permissions

### Authentication
- Passwords hashed with bcrypt (12 rounds)
- Session tokens are 8-hour signed tokens (`itsdangerous.URLSafeTimedSerializer`)
- Generic error messages on login failure (no user enumeration)
- Account locked for 10 minutes after 5 consecutive failed attempts

### Part 7.9 Permission Matrix

| Action | Process Owner | Analyst | Technical Reviewer | Viewer |
|--------|:---:|:---:|:---:|:---:|
| View project | ✓ | ✓ | ✓ | ✓ |
| Upload document | ✓ | ✓ | ✗ | ✗ |
| Start / cancel run | ✓ | ✓ | ✗ | ✗ |
| Answer question (own role) | ✓ | ✓ | ✓ | ✗ |
| Approve business rules / To-Be | ✓ | ✗ | ✗ | ✗ |
| Approve technical artifacts (HLD, SRS) | ✗ | ✗ | ✓ | ✗ |
| Invite / remove members | ✓ | ✗ | ✗ | ✗ |

---

## Known Limitations

| Limitation | Notes |
|-----------|-------|
| **Real LLM calls require `GEMINI_API_KEY`** | Without it, a deterministic mock generator returns structured outputs for testing. Set the key to use Google Gemini. |
| **Invitation e-mail needs SMTP settings** | Sending **is** implemented (`app/api/team.py`, plain text over `smtplib` + STARTTLS, per brief 7.4), including a resend endpoint limited to 5 per invitation and 20 invitations per project per day. It is inactive until `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` and `SMTP_FROM` are set in `.env`; until then invitations are saved with `email_status = 'not_sent'` and still appear on the invitee's dashboard, which is the source of truth. |
| **No HTTPS in dev mode** | Production deployment should front Uvicorn with nginx + TLS. |
| **PDFs over 100 pages are refused** | `document_parser.py` rejects a PDF with more than 100 pages outright, with a clear error. It is a hard limit, not a slow path, and there is no per-page timeout. |
| **Streamlit session state resets on hot-reload** | Expected Streamlit behavior; users must re-authenticate after dev server restarts. |
| **SQLite does not enforce the schema's constraints** | `schema.sql` carries 40 `CHECK` constraints, the append-only `audit_events` trigger and Row Level Security. The SQLite mirror used for tests and offline development implements none of them, so those guarantees hold only on PostgreSQL. The application layer enforces the approval rule itself (`update_rule_status`, `update_artifact_status`), and `tests/test_spec_coverage.py` carries PostgreSQL-only tests that **skip** unless `PFAI_TEST_POSTGRES_URL` points at a throwaway database. |
| **Not run on Python 3.11 or 3.12** | `pyproject.toml` claims `>=3.11` and the code contains no 3.12+ syntax, but the suite has only been executed on 3.14.7. |
| **Runs live in the API process** | Analysis runs as a FastAPI background task, so a server restart interrupts any run in flight. Startup marks such runs `failed` with a clear reason rather than leaving them stuck at `running`. |
