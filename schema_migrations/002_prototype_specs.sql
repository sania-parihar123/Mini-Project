-- Migration: 002_prototype_specs.sql
-- Description: Table for storing cached interactive prototype specifications per project.

CREATE TABLE IF NOT EXISTS prototype_specs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    spec_fingerprint TEXT NOT NULL,
    spec_json       JSONB NOT NULL,
    spec_version    INTEGER NOT NULL DEFAULT 1,
    generated_by    UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, spec_version)
);

CREATE INDEX IF NOT EXISTS idx_proto_project ON prototype_specs(project_id);

ALTER TABLE public.prototype_specs ENABLE ROW LEVEL SECURITY;
-- No RLS policies: backend connection role bypasses RLS; anon key cannot access table.
