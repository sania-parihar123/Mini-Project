-- ProcessFoundry AI: PostgreSQL schema (MVP)
-- Tags: [BASELINE] = table/columns named in the design document.
--       [EXTENSION] = columns/tables added to make the design buildable.
--       [PROPOSED]  = from the 14 Oct discussion; not in the design document.
-- Rules baked into the schema:
--   * Every project-owned table carries project_id; every query MUST filter by it.
--   * Human-readable keys (EVD-001, BR-001, ...) are unique PER PROJECT; primary keys are UUIDs.
--   * An 'approved' status is impossible without a named human approver (CHECK constraints).
--   * AI never writes status = 'approved'.

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
-- Optional, only if semantic search is added later:
-- CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------- people [PROPOSED]
-- Real accounts: e-mail + password (hash only). See Part 7.3.
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE
                    CHECK (email = lower(email) AND email ~ '^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$'),
    password_hash   TEXT NOT NULL,            -- argon2id or bcrypt hash only. Never the password. [PROPOSED]
    failed_attempts INT NOT NULL DEFAULT 0,   -- wrong passwords in a row [PROPOSED]
    locked_until    TIMESTAMPTZ,              -- sign-in refused until this time [PROPOSED]
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- projects [BASELINE]
CREATE TABLE projects (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    process_type  TEXT,                       -- free text: 'scholarship', 'admission', ...
    description   TEXT,
    goals         TEXT,                       -- [BASELINE] create-project field
    constraints   TEXT,                       -- [BASELINE] create-project field
    department    TEXT,                       -- [EXTENSION] in MVP scope
    stakeholders  JSONB NOT NULL DEFAULT '[]',-- [EXTENSION]
    status        TEXT NOT NULL DEFAULT 'created'
                  CHECK (status IN ('created','in_progress','waiting_for_human','completed','archived')),
    created_by    UUID REFERENCES users(id),  -- [PROPOSED]
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Who is an ACTIVE member of which project, and in which role. One role per person per project.
-- Pending invitations live in project_invitations (below), not here. [PROPOSED]
CREATE TABLE project_members (
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL REFERENCES users(id),
    role          TEXT NOT NULL CHECK (role IN ('process_owner','analyst','technical_reviewer')),
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','removed')),
    invited_by    UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, user_id)
);
CREATE INDEX idx_members_user ON project_members(user_id) WHERE status <> 'removed';

-- Invitations for people who may not have an account yet. Matched by e-mail at sign-in. [PROPOSED]
CREATE TABLE project_invitations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    email         TEXT NOT NULL CHECK (email = lower(email)),
    role          TEXT NOT NULL CHECK (role IN ('process_owner','analyst','technical_reviewer')),
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','revoked','expired')),
    invited_by    UUID NOT NULL REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL DEFAULT now() + interval '14 days',
    accepted_by   UUID REFERENCES users(id),
    accepted_at   TIMESTAMPTZ,
    email_status  TEXT NOT NULL DEFAULT 'not_sent' CHECK (email_status IN ('sent','not_sent')),  -- invitation e-mail result
    email_sent_at TIMESTAMPTZ,
    resend_count  INTEGER NOT NULL DEFAULT 0 CHECK (resend_count BETWEEN 0 AND 5),
    CHECK (status <> 'accepted' OR (accepted_by IS NOT NULL AND accepted_at IS NOT NULL))
);
CREATE UNIQUE INDEX uq_invite_pending ON project_invitations(project_id, email, role) WHERE status = 'pending';
CREATE INDEX idx_invite_email ON project_invitations(email) WHERE status = 'pending';

-- Per-project counters used by the application to mint EVD-001, BR-001, REQ-001, ... [EXTENSION]
-- Increment inside the same transaction that inserts the row.
CREATE TABLE project_counters (
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity        TEXT NOT NULL,              -- 'EVD','BR','STEP','REQ','TEST','UAT','Q','FACT'
    next_value    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (project_id, entity)
);

-- ---------------------------------------------------------------- sources [BASELINE]
CREATE TABLE documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,              -- display only; NEVER used as a storage path
    mime_type     TEXT NOT NULL,
    checksum      TEXT NOT NULL,              -- sha256 of the stored file
    version       INTEGER NOT NULL DEFAULT 1,
    storage_path  TEXT NOT NULL,              -- server-generated, e.g. uploads/<project_id>/<uuid>
    size_bytes    BIGINT,                     -- [EXTENSION]
    parse_status  TEXT NOT NULL DEFAULT 'pending'
                  CHECK (parse_status IN ('pending','parsed','failed')),   -- [EXTENSION]
    parse_warnings JSONB NOT NULL DEFAULT '[]',                            -- [EXTENSION]
    uploaded_by   UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, checksum, version)
);
CREATE INDEX idx_documents_project ON documents(project_id);

CREATE TABLE document_sections (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id    UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_index  INTEGER NOT NULL,          -- [EXTENSION] order inside the document
    page_number    INTEGER,
    section_title  TEXT,
    text           TEXT NOT NULL,
    read_from_image BOOLEAN NOT NULL DEFAULT FALSE,  -- [EXTENSION] text came from page images (OCR)
    extracted_by   TEXT,                      -- [EXTENSION] extractor version that last mined this
                                              -- section; lets a re-run skip unchanged sections
                                              -- instead of repeating every model call
    UNIQUE (document_id, section_index)
);

-- Chunks for retrieval. Start with full-text search; add an embedding column only if needed. [BASELINE: RAG]
CREATE TABLE document_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id    UUID REFERENCES document_sections(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    text          TEXT NOT NULL,
    tsv           TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    -- embedding vector(768),                 -- optional (pgvector)
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX idx_chunks_tsv ON document_chunks USING GIN (tsv);
CREATE INDEX idx_chunks_project ON document_chunks(project_id);

-- Cached "What I understood" view per document, keyed by content checksum, so
-- opening a page does not fire a model call per document on every render.
-- Derived data only: it can be deleted at any time and will be recomputed. [EXTENSION]
CREATE TABLE document_understanding (
    document_id   UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    checksum      TEXT NOT NULL,              -- documents.checksum this was computed from
    content_json  JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- evidence [BASELINE]
CREATE TABLE evidence_items (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    evidence_key         TEXT NOT NULL,       -- 'EVD-001'                         [EXTENSION]
    document_section_id  UUID NOT NULL REFERENCES document_sections(id),
    claim                TEXT NOT NULL,       -- the extracted statement           [EXTENSION]
    quote                TEXT NOT NULL,       -- EXACT text from the section; the app must verify this
    claim_type           TEXT NOT NULL,       -- 'step','actor','rule','date','form','other'
    confidence           NUMERIC(3,2) CHECK (confidence BETWEEN 0 AND 1),
    status               TEXT NOT NULL DEFAULT 'extracted'
                         CHECK (status IN ('extracted','reviewed','rejected')),  -- [EXTENSION]
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, evidence_key)
);
CREATE INDEX idx_evidence_project ON evidence_items(project_id);
CREATE INDEX idx_evidence_section ON evidence_items(document_section_id);

-- ---------------------------------------------------------------- process model [BASELINE]
CREATE TABLE process_versions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version       INTEGER NOT NULL,
    as_is_json    JSONB,
    to_be_json    JSONB,
    status        TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','needs_clarification','needs_review','approved','rejected','stale')),
    approved_by   UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, version),
    CHECK (status <> 'approved' OR approved_by IS NOT NULL)
);

CREATE TABLE process_steps (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_version_id  UUID NOT NULL REFERENCES process_versions(id) ON DELETE CASCADE,
    step_key            TEXT NOT NULL,        -- 'STEP-001'
    name                TEXT NOT NULL,
    actor               TEXT,                 -- NULL = not stated in the source (never guess)
    step_type           TEXT,                 -- 'form_submission','review','payment',...
    sequence            INTEGER NOT NULL,
    inputs              JSONB NOT NULL DEFAULT '[]',   -- [EXTENSION]
    outputs             JSONB NOT NULL DEFAULT '[]',   -- [EXTENSION]
    unknowns            JSONB NOT NULL DEFAULT '[]',   -- [EXTENSION] e.g. ["actor not stated"]
    automation          TEXT CHECK (automation IN ('deterministic','ai_assisted','human','hybrid')), -- To-Be only
    human_approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (process_version_id, step_key)
);

CREATE TABLE step_evidence (                  -- [EXTENSION] step -> evidence links
    step_id      UUID NOT NULL REFERENCES process_steps(id) ON DELETE CASCADE,
    evidence_id  UUID NOT NULL REFERENCES evidence_items(id),
    PRIMARY KEY (step_id, evidence_id)
);

CREATE TABLE step_transitions (               -- [EXTENSION] workflow JSON "transitions"
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_version_id UUID NOT NULL REFERENCES process_versions(id) ON DELETE CASCADE,
    from_step_id  UUID NOT NULL REFERENCES process_steps(id) ON DELETE CASCADE,
    to_step_id    UUID NOT NULL REFERENCES process_steps(id) ON DELETE CASCADE,
    condition     TEXT
);

-- ---------------------------------------------------------------- business rules [BASELINE]
CREATE TABLE business_rules (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    rule_key       TEXT NOT NULL,             -- 'BR-001'
    description    TEXT NOT NULL,
    condition_json JSONB NOT NULL DEFAULT '{}',   -- condition, outcome, exceptions
    status         TEXT NOT NULL DEFAULT 'needs_review'
                   CHECK (status IN ('draft','needs_review','needs_clarification','approved','superseded','rejected')),
    supersedes_rule_id UUID REFERENCES business_rules(id),   -- [PROPOSED] set when a conflict is resolved
    approved_by    UUID REFERENCES users(id),
    approved_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, rule_key),
    CHECK (status <> 'approved' OR approved_by IS NOT NULL)
);
-- Conflicting rules (e.g. 31 March vs 15 April) are stored as TWO rows. Never merged by code or AI.

CREATE TABLE rule_evidence (
    rule_id      UUID NOT NULL REFERENCES business_rules(id) ON DELETE CASCADE,
    evidence_id  UUID NOT NULL REFERENCES evidence_items(id),
    PRIMARY KEY (rule_id, evidence_id)
);

-- ---------------------------------------------------------------- runs [EXTENSION]
CREATE TABLE runs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status        TEXT NOT NULL DEFAULT 'created'
                  CHECK (status IN ('created','running','waiting_for_human','completed','failed','cancelled')),
    current_node  TEXT,
    state_json    JSONB,                      -- saved graph state / checkpoint so the run can resume
    last_error    TEXT,
    started_by    UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_runs_project ON runs(project_id);

-- ---------------------------------------------------------------- clarification (human in the loop)
CREATE TABLE clarification_items (            -- [BASELINE] + extensions
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    run_id         UUID REFERENCES runs(id),
    question_key   TEXT NOT NULL,             -- 'Q-001'
    question       TEXT NOT NULL,
    reason         TEXT,                      -- "why it matters"
    kind           TEXT NOT NULL DEFAULT 'missing_info'
                   CHECK (kind IN ('conflicting_rules','missing_actor','ambiguous_term','missing_info',
                                   'duplicate_step','parsing_error','technical_conflict',
                                   'user_question')),   -- [PROPOSED]
    assigned_role  TEXT NOT NULL DEFAULT 'process_owner'
                   CHECK (assigned_role IN ('process_owner','analyst','technical_reviewer')), -- [PROPOSED]
    options        JSONB NOT NULL DEFAULT '[]',     -- e.g. ["31 March","15 April","Other"]
    ai_suggestion  TEXT,                            -- always shown labelled "AI suggestion"
    status         TEXT NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open','answered','unknown','stale','cancelled')),
    answer         TEXT,                            -- current answer (history is in clarification_answers)
    answered_by    UUID REFERENCES users(id),
    answered_at    TIMESTAMPTZ,
    asked_by       UUID REFERENCES users(id),       -- for kind = 'user_question'
    fingerprint    TEXT NOT NULL,                   -- same problem => same fingerprint => asked once
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, question_key),
    UNIQUE (project_id, fingerprint),
    CHECK (status NOT IN ('answered') OR (answer IS NOT NULL AND answered_by IS NOT NULL))
);
CREATE INDEX idx_clar_inbox ON clarification_items(project_id, assigned_role, status);

-- What a question is about (rules, steps, evidence). Lets the UI show both conflicting sources. [EXTENSION]
CREATE TABLE clarification_links (
    clarification_id UUID NOT NULL REFERENCES clarification_items(id) ON DELETE CASCADE,
    target_type      TEXT NOT NULL CHECK (target_type IN ('rule','step','evidence','requirement')),
    target_id        UUID NOT NULL,
    PRIMARY KEY (clarification_id, target_type, target_id)
);

-- Answer history: re-answering never deletes the old answer. [PROPOSED]
CREATE TABLE clarification_answers (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clarification_id UUID NOT NULL REFERENCES clarification_items(id) ON DELETE CASCADE,
    answer_kind      TEXT NOT NULL CHECK (answer_kind IN ('answer','unknown')),
    answer_text      TEXT,
    answered_by      UUID NOT NULL REFERENCES users(id),
    role             TEXT NOT NULL,
    answered_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded       BOOLEAN NOT NULL DEFAULT FALSE
);

-- Facts confirmed by a human (graph state field "verified_facts"). [PROPOSED]
CREATE TABLE verified_facts (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    fact_key       TEXT NOT NULL,             -- 'FACT-001'
    statement      TEXT NOT NULL,             -- "The submission deadline is 31 March."
    clarification_id UUID REFERENCES clarification_items(id),
    confirmed_by   UUID NOT NULL REFERENCES users(id),
    confirmed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','stale')),
    UNIQUE (project_id, fact_key)
);

-- ---------------------------------------------------------------- requirements [BASELINE]
CREATE TABLE requirements (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirement_key TEXT NOT NULL,            -- 'REQ-001'
    type            TEXT NOT NULL CHECK (type IN ('business','functional','non_functional','workflow')),
    title           TEXT,
    statement       TEXT NOT NULL,
    priority        TEXT CHECK (priority IN ('Must','Should','Could','Wont')),
    acceptance_criteria JSONB NOT NULL DEFAULT '[]',   -- [EXTENSION]
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','needs_clarification','needs_review','reviewed','approved','stale')),
    approved_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, requirement_key),
    CHECK (status <> 'approved' OR approved_by IS NOT NULL)
);

CREATE TABLE requirement_links (
    requirement_id UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,  -- the "source requirement"
    target_type    TEXT NOT NULL CHECK (target_type IN ('evidence','rule','step','requirement','verified_fact')), -- [EXTENSION]
    target_id      UUID NOT NULL,
    link_type      TEXT NOT NULL,             -- 'supported_by','derived_from','related_to'
    PRIMARY KEY (requirement_id, target_type, target_id, link_type)
);
CREATE INDEX idx_reqlinks_target ON requirement_links(target_type, target_id);

-- ---------------------------------------------------------------- artifacts [BASELINE]
CREATE TABLE artifacts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,              -- 'as_is_report','to_be_spec','brd','frd','prd','srs','rules_catalogue',
                                              -- 'roles_matrix','data_model','hld','api_spec','test_plan','uat_pack',
                                              -- 'workflow_json','traceability_matrix'
    version       INTEGER NOT NULL DEFAULT 1,
    content_json  JSONB,
    markdown      TEXT,
    status        TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','needs_clarification','needs_review','reviewed','approved','stale')),
    approved_by   UUID REFERENCES users(id),
    created_by    UUID REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, artifact_type, version),
    CHECK (status <> 'approved' OR approved_by IS NOT NULL)
);

CREATE TABLE artifact_links (
    artifact_id  UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    target_type  TEXT NOT NULL CHECK (target_type IN ('evidence','rule','step','requirement','test','verified_fact')),
    target_id    UUID NOT NULL,
    link_type    TEXT NOT NULL,
    PRIMARY KEY (artifact_id, target_type, target_id, link_type)
);

-- ---------------------------------------------------------------- tests [BASELINE]
CREATE TABLE test_cases (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    test_key       TEXT NOT NULL,             -- 'TEST-001'
    requirement_id UUID NOT NULL REFERENCES requirements(id),   -- every test points to a requirement
    kind           TEXT CHECK (kind IN ('positive','negative','boundary','exception','permission','journey')), -- [EXTENSION]
    scenario       TEXT NOT NULL,
    preconditions  TEXT,                                          -- [EXTENSION]
    steps          JSONB NOT NULL DEFAULT '[]',                   -- [EXTENSION]
    expected_result TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, test_key)
);

-- ---------------------------------------------------------------- approvals and history
CREATE TABLE approvals (                      -- [BASELINE]
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    target_type   TEXT NOT NULL CHECK (target_type IN ('rule','process_version','artifact','requirement')),
    target_id     UUID NOT NULL,
    decision      TEXT NOT NULL CHECK (decision IN ('approve','request_changes','reject')),
    reviewer      UUID NOT NULL REFERENCES users(id),
    reviewer_role TEXT NOT NULL,              -- [EXTENSION] role used when deciding
    comment       TEXT,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (decision = 'approve' OR (comment IS NOT NULL AND length(trim(comment)) > 0))  -- reason needed to reject
);
CREATE INDEX idx_approvals_target ON approvals(target_type, target_id);

CREATE TABLE agent_runs (                     -- [BASELINE]
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    run_id        UUID REFERENCES runs(id),   -- [EXTENSION]
    node_name     TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('started','succeeded','failed','needs_review')),
    input_summary TEXT,                       -- never store secrets or unnecessary personal data
    output_ref    TEXT,
    error         TEXT,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ
);
CREATE INDEX idx_agent_runs_run ON agent_runs(run_id);

-- Append-only history with a hash chain so edits to old events are detectable. [PROPOSED]
CREATE TABLE audit_events (
    id            BIGSERIAL PRIMARY KEY,
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    event_type    TEXT NOT NULL,              -- 'question_asked','answer_recorded','decision_recorded',...
    actor         TEXT NOT NULL,              -- user name or 'system'
    subject       TEXT,
    details       JSONB NOT NULL DEFAULT '{}',
    prev_hash     TEXT NOT NULL,
    hash          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_project ON audit_events(project_id, id);
-- Block edits and deletes (history must be append-only):
CREATE OR REPLACE FUNCTION audit_events_block_change() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_events is append-only'; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER audit_events_no_update BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_block_change();

-- ---------------------------------------------------------------- Supabase / hosted Postgres lock-down
-- Supabase exposes every table in the "public" schema through an automatic REST API using a public
-- "anon" key. With Row Level Security (RLS) OFF, anyone holding that key could read or write these tables.
-- The backend connects with the database role directly (DATABASE_URL), which bypasses RLS, so we turn RLS
-- ON for every table and add NO policies: the REST API then sees nothing, the backend still works.
-- Harmless on plain PostgreSQL.
DO $$
DECLARE t text;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;
