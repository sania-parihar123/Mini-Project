"""ProcessFoundry AI: Dual-mode Database Engine and Repository Layer.

Supports PostgreSQL via psycopg when DATABASE_URL is configured, and provides an
automated local SQLite fallback for isolated, zero-dependency testing and development.
"""
import hashlib
import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg_pool

from app.core.config import settings, is_test_environment

logger = logging.getLogger("processfoundry.repository")


def _jload(v, default=None):
    """JSONB columns arrive already parsed on PostgreSQL; TEXT on SQLite."""
    if v is None or v == "":
        return default
    return json.loads(v) if isinstance(v, (str, bytes)) else v


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class DatabaseRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.use_postgres = bool(settings.database_url.strip())
        self.postgres_url = settings.database_url.strip()
        self._pool: Optional[psycopg_pool.ConnectionPool] = None

        # The SQLite path may be supplied directly, or through PF_SQLITE_PATH so
        # that a test run can redirect it before this module is imported.
        env_sqlite_path = os.environ.get("PF_SQLITE_PATH", "").strip()
        if db_path:
            self.sqlite_path = db_path
        elif env_sqlite_path:
            self.sqlite_path = env_sqlite_path
        else:
            self.sqlite_path = str(Path("data") / "processfoundry.db")

        # The schema is created lazily on first use. Doing it in __init__ meant
        # that merely importing this module created data/processfoundry.db.
        self._sqlite_ready_path: Optional[str] = None

    def validate_configuration(self):
        """Validate database configuration during startup and fail fast if invalid."""
        if not self.use_postgres and not is_test_environment():
            raise RuntimeError(
                "ProcessFoundry AI Configuration Error: DATABASE_URL is missing or empty. "
                "A PostgreSQL connection URL is required for normal operation. "
                "SQLite is restricted to isolated test environments. "
                "To enable SQLite for local testing, set ALLOW_SQLITE=true or APP_ENV=test in your environment."
            )

    def init_pool(self, min_size: int = 1, max_size: int = 10):
        """Initialise PostgreSQL shared connection pool, or validate SQLite test configuration."""
        self.validate_configuration()
        if self.use_postgres:
            if self._pool is None:
                try:
                    self._pool = psycopg_pool.ConnectionPool(
                        conninfo=self.postgres_url,
                        min_size=min_size,
                        max_size=max_size,
                        open=True,
                        timeout=30.0
                    )
                    self._run_postgres_migrations()
                except Exception as e:
                    self._pool = None
                    raise RuntimeError(f"Failed to initialize PostgreSQL connection pool: {e}")

    def close_pool(self):
        """Clean up and close connection pool on application shutdown."""
        if self._pool is not None:
            try:
                self._pool.close()
            except Exception:
                pass
            self._pool = None

    def _run_postgres_migrations(self):
        """Apply safe idempotent migrations for PostgreSQL."""
        if not self.use_postgres or not self._pool:
            return
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE document_sections 
                    ADD COLUMN IF NOT EXISTS read_from_image BOOLEAN NOT NULL DEFAULT FALSE;
                """)
                cur.execute("""
                    ALTER TABLE document_sections
                    ADD COLUMN IF NOT EXISTS extracted_by TEXT;
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS document_understanding (
                        document_id   UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
                        checksum      TEXT NOT NULL,
                        content_json  JSONB NOT NULL,
                        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                """)
                # Allow the duplicate_step question kind on databases created
                # before that detector existed.
                cur.execute("""
                    ALTER TABLE clarification_items
                    DROP CONSTRAINT IF EXISTS clarification_items_kind_check;
                """)
                cur.execute("""
                    ALTER TABLE clarification_items
                    ADD CONSTRAINT clarification_items_kind_check
                    CHECK (kind IN ('conflicting_rules','missing_actor','ambiguous_term',
                                    'missing_info','duplicate_step','parsing_error',
                                    'technical_conflict','user_question'));
                """)

    def get_connection(self):
        if self.use_postgres:
            if self._pool is None:
                self.init_pool()
            return self._pool.connection()
        else:
            # Create the schema on first use (and again if sqlite_path changed).
            if self._sqlite_ready_path != self.sqlite_path:
                self._init_sqlite()
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn

    def _init_sqlite(self):
        """Initialize SQLite database with schema matching schema.sql."""
        parent = Path(self.sqlite_path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_ready_path = self.sqlite_path
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cur = conn.cursor()
            cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                last_login_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                process_type TEXT,
                description TEXT,
                goals TEXT,
                constraints TEXT,
                department TEXT,
                stakeholders TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'created',
                created_by TEXT REFERENCES users(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_members (
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id),
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                invited_by TEXT REFERENCES users(id),
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS project_invitations (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                email TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                invited_by TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                accepted_by TEXT REFERENCES users(id),
                accepted_at TEXT,
                email_status TEXT NOT NULL DEFAULT 'not_sent',
                email_sent_at TEXT,
                resend_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS project_counters (
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                entity TEXT NOT NULL,
                next_value INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (project_id, entity)
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                checksum TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                storage_path TEXT NOT NULL,
                size_bytes INTEGER,
                parse_status TEXT NOT NULL DEFAULT 'pending',
                parse_warnings TEXT NOT NULL DEFAULT '[]',
                uploaded_by TEXT REFERENCES users(id),
                created_at TEXT NOT NULL,
                UNIQUE (project_id, checksum, version)
            );

            CREATE TABLE IF NOT EXISTS document_sections (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                section_index INTEGER NOT NULL,
                page_number INTEGER,
                section_title TEXT,
                text TEXT NOT NULL,
                read_from_image INTEGER NOT NULL DEFAULT 0,
                extracted_by TEXT,
                UNIQUE (document_id, section_index)
            );

            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                section_id TEXT REFERENCES document_sections(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                UNIQUE (document_id, chunk_index)
            );

            CREATE TABLE IF NOT EXISTS document_understanding (
                document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
                checksum TEXT NOT NULL,
                content_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS evidence_items (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                evidence_key TEXT NOT NULL,
                document_section_id TEXT NOT NULL REFERENCES document_sections(id),
                claim TEXT NOT NULL,
                quote TEXT NOT NULL,
                claim_type TEXT NOT NULL,
                confidence REAL,
                status TEXT NOT NULL DEFAULT 'extracted',
                created_at TEXT NOT NULL,
                UNIQUE (project_id, evidence_key)
            );

            CREATE TABLE IF NOT EXISTS process_versions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                as_is_json TEXT,
                to_be_json TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                approved_by TEXT REFERENCES users(id),
                created_at TEXT NOT NULL,
                UNIQUE (project_id, version)
            );

            CREATE TABLE IF NOT EXISTS process_steps (
                id TEXT PRIMARY KEY,
                process_version_id TEXT NOT NULL REFERENCES process_versions(id) ON DELETE CASCADE,
                step_key TEXT NOT NULL,
                name TEXT NOT NULL,
                actor TEXT,
                step_type TEXT,
                sequence INTEGER NOT NULL,
                inputs TEXT NOT NULL DEFAULT '[]',
                outputs TEXT NOT NULL DEFAULT '[]',
                unknowns TEXT NOT NULL DEFAULT '[]',
                automation TEXT,
                human_approval_required INTEGER NOT NULL DEFAULT 0,
                UNIQUE (process_version_id, step_key)
            );

            CREATE TABLE IF NOT EXISTS step_evidence (
                step_id TEXT NOT NULL REFERENCES process_steps(id) ON DELETE CASCADE,
                evidence_id TEXT NOT NULL REFERENCES evidence_items(id),
                PRIMARY KEY (step_id, evidence_id)
            );

            CREATE TABLE IF NOT EXISTS step_transitions (
                id TEXT PRIMARY KEY,
                process_version_id TEXT NOT NULL REFERENCES process_versions(id) ON DELETE CASCADE,
                from_step_id TEXT NOT NULL REFERENCES process_steps(id) ON DELETE CASCADE,
                to_step_id TEXT NOT NULL REFERENCES process_steps(id) ON DELETE CASCADE,
                condition TEXT
            );

            CREATE TABLE IF NOT EXISTS business_rules (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                rule_key TEXT NOT NULL,
                description TEXT NOT NULL,
                condition_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'needs_review',
                supersedes_rule_id TEXT REFERENCES business_rules(id),
                approved_by TEXT REFERENCES users(id),
                approved_at TEXT,
                created_at TEXT NOT NULL,
                UNIQUE (project_id, rule_key)
            );

            CREATE TABLE IF NOT EXISTS rule_evidence (
                rule_id TEXT NOT NULL REFERENCES business_rules(id) ON DELETE CASCADE,
                evidence_id TEXT NOT NULL REFERENCES evidence_items(id),
                PRIMARY KEY (rule_id, evidence_id)
            );

            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'created',
                current_node TEXT,
                state_json TEXT,
                last_error TEXT,
                started_by TEXT REFERENCES users(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clarification_items (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                run_id TEXT REFERENCES runs(id),
                question_key TEXT NOT NULL,
                question TEXT NOT NULL,
                reason TEXT,
                kind TEXT NOT NULL DEFAULT 'missing_info',
                assigned_role TEXT NOT NULL DEFAULT 'process_owner',
                options TEXT NOT NULL DEFAULT '[]',
                ai_suggestion TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                answer TEXT,
                answered_by TEXT REFERENCES users(id),
                answered_at TEXT,
                asked_by TEXT REFERENCES users(id),
                fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (project_id, question_key),
                UNIQUE (project_id, fingerprint)
            );

            CREATE TABLE IF NOT EXISTS clarification_links (
                clarification_id TEXT NOT NULL REFERENCES clarification_items(id) ON DELETE CASCADE,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                PRIMARY KEY (clarification_id, target_type, target_id)
            );

            CREATE TABLE IF NOT EXISTS clarification_answers (
                id TEXT PRIMARY KEY,
                clarification_id TEXT NOT NULL REFERENCES clarification_items(id) ON DELETE CASCADE,
                answer_kind TEXT NOT NULL,
                answer_text TEXT,
                answered_by TEXT NOT NULL REFERENCES users(id),
                role TEXT NOT NULL,
                answered_at TEXT NOT NULL,
                superseded INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS verified_facts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                fact_key TEXT NOT NULL,
                statement TEXT NOT NULL,
                clarification_id TEXT REFERENCES clarification_items(id),
                confirmed_by TEXT NOT NULL REFERENCES users(id),
                confirmed_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                UNIQUE (project_id, fact_key)
            );

            CREATE TABLE IF NOT EXISTS requirements (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                requirement_key TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT,
                statement TEXT NOT NULL,
                priority TEXT,
                acceptance_criteria TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft',
                approved_by TEXT REFERENCES users(id),
                created_at TEXT NOT NULL,
                UNIQUE (project_id, requirement_key)
            );

            CREATE TABLE IF NOT EXISTS requirement_links (
                requirement_id TEXT NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                link_type TEXT NOT NULL,
                PRIMARY KEY (requirement_id, target_type, target_id, link_type)
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                artifact_type TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                content_json TEXT,
                markdown TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                approved_by TEXT REFERENCES users(id),
                created_by TEXT REFERENCES users(id),
                created_at TEXT NOT NULL,
                UNIQUE (project_id, artifact_type, version)
            );

            CREATE TABLE IF NOT EXISTS artifact_links (
                artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                link_type TEXT NOT NULL,
                PRIMARY KEY (artifact_id, target_type, target_id, link_type)
            );

            CREATE TABLE IF NOT EXISTS test_cases (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                test_key TEXT NOT NULL,
                requirement_id TEXT NOT NULL REFERENCES requirements(id),
                kind TEXT,
                scenario TEXT NOT NULL,
                preconditions TEXT,
                steps TEXT NOT NULL DEFAULT '[]',
                expected_result TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (project_id, test_key)
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                reviewer TEXT NOT NULL REFERENCES users(id),
                reviewer_role TEXT NOT NULL,
                comment TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                run_id TEXT REFERENCES runs(id),
                node_name TEXT NOT NULL,
                status TEXT NOT NULL,
                input_summary TEXT,
                output_ref TEXT,
                error TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                subject TEXT,
                details TEXT NOT NULL DEFAULT '{}',
                prev_hash TEXT NOT NULL,
                hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            # Run SQLite migrations for existing databases
            cur.execute("PRAGMA table_info(document_sections);")
            cols = [row[1] for row in cur.fetchall()]
            if cols and "read_from_image" not in cols:
                cur.execute("ALTER TABLE document_sections ADD COLUMN read_from_image INTEGER NOT NULL DEFAULT 0;")

    # ----------------------------------------------------
    # Key Minting
    # ----------------------------------------------------
    def mint_key(self, project_id: str, entity: str) -> str:
        """Atomically mint project-scoped readable keys: EVD-001, BR-001, STEP-001, REQ-001, etc."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO project_counters (project_id, entity, next_value)
                    VALUES (%s, %s, 2)
                    ON CONFLICT (project_id, entity)
                    DO UPDATE SET next_value = project_counters.next_value + 1
                    RETURNING next_value - 1;
                """, (project_id, entity))
                val = cur.fetchone()[0]
            else:
                cur.execute("SELECT next_value FROM project_counters WHERE project_id = ? AND entity = ?", (project_id, entity))
                row = cur.fetchone()
                if row:
                    val = row["next_value"]
                    cur.execute("UPDATE project_counters SET next_value = next_value + 1 WHERE project_id = ? AND entity = ?", (project_id, entity))
                else:
                    val = 1
                    cur.execute("INSERT INTO project_counters (project_id, entity, next_value) VALUES (?, ?, 2)", (project_id, entity))
                conn.commit()
            return f"{entity}-{val:03d}"

    # ----------------------------------------------------
    # Audit Logging (Hash-Chained)
    # ----------------------------------------------------
    def _log_audit_event_tx(self, cur, project_id: str, event_type: str, actor: str, subject: Optional[str] = None, details: Optional[Dict[str, Any]] = None, prev_hash: Optional[str] = None) -> Dict[str, Any]:
        """Append an immutable, hash-chained audit event within an active cursor/transaction."""
        details_json = json.dumps(details or {}, sort_keys=True)
        created_at = now_iso()
        if prev_hash is None:
            if self.use_postgres:
                # FOR UPDATE locks the project's latest event for the rest of this
                # transaction, as brief 8.4 requires. Without the lock two
                # concurrent events could read the same prev_hash and fork the
                # chain (finding F14). SKIP LOCKED is deliberately NOT used: we
                # must wait for the real tail, not skip past it.
                cur.execute(
                    "SELECT hash FROM audit_events WHERE project_id = %s "
                    "ORDER BY id DESC LIMIT 1 FOR UPDATE;",
                    (project_id,),
                )
                row = cur.fetchone()
                prev_hash = row[0] if row else "0" * 64
            else:
                # SQLite serialises writers with a single write lock, so the
                # read-then-insert cannot interleave.
                cur.execute("SELECT hash FROM audit_events WHERE project_id = ? ORDER BY id DESC LIMIT 1;", (project_id,))
                row = cur.fetchone()
                prev_hash = row["hash"] if row else "0" * 64

        event_canonical = f"{prev_hash}|{project_id}|{event_type}|{actor}|{subject}|{details_json}|{created_at}"
        event_hash = hashlib.sha256(event_canonical.encode("utf-8")).hexdigest()
        if self.use_postgres:
            cur.execute("""
                INSERT INTO audit_events (project_id, event_type, actor, subject, details, prev_hash, hash, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (project_id, event_type, actor, subject, details_json, prev_hash, event_hash, created_at))
            event_id = cur.fetchone()[0]
        else:
            cur.execute("""
                INSERT INTO audit_events (project_id, event_type, actor, subject, details, prev_hash, hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (project_id, event_type, actor, subject, details_json, prev_hash, event_hash, created_at))
            event_id = cur.lastrowid

        return {
            "id": event_id,
            "project_id": project_id,
            "event_type": event_type,
            "actor": actor,
            "subject": subject,
            "details": details or {},
            "prev_hash": prev_hash,
            "hash": event_hash,
            "created_at": created_at
        }

    def log_audit_event(self, project_id: str, event_type: str, actor: str, subject: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append an immutable, hash-chained audit event."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            res = self._log_audit_event_tx(cur, project_id, event_type, actor, subject, details)
            if not self.use_postgres:
                conn.commit()
            return res

    def list_audit_events(self, project_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM audit_events WHERE project_id = ? ORDER BY id DESC" if not self.use_postgres else "SELECT * FROM audit_events WHERE project_id = %s ORDER BY id DESC"
            cur.execute(query, (project_id,))
            rows = cur.fetchall()
            result = []
            for r in rows:
                result.append({
                    "id": r["id"] if not self.use_postgres else r[0],
                    "project_id": r["project_id"] if not self.use_postgres else r[1],
                    "event_type": r["event_type"] if not self.use_postgres else r[2],
                    "actor": r["actor"] if not self.use_postgres else r[3],
                    "subject": r["subject"] if not self.use_postgres else r[4],
                    "details": json.loads(r["details"]) if isinstance(r["details"] if not self.use_postgres else r[5], str) else (r["details"] if not self.use_postgres else r[5]),
                    "prev_hash": r["prev_hash"] if not self.use_postgres else r[6],
                    "hash": r["hash"] if not self.use_postgres else r[7],
                    "created_at": r["created_at"] if not self.use_postgres else str(r[8])
                })
            return result

    # ----------------------------------------------------
    # Users & Authentication
    # ----------------------------------------------------
    def create_user(self, display_name: str, email: str, password_hash: str) -> Dict[str, Any]:
        user_id = str(uuid.uuid4())
        created_at = now_iso()
        email_clean = email.strip().lower()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO users (id, display_name, email, password_hash, created_at)
                    VALUES (%s, %s, %s, %s, %s);
                """, (user_id, display_name.strip(), email_clean, password_hash, created_at))
            else:
                cur.execute("""
                    INSERT INTO users (id, display_name, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?, ?);
                """, (user_id, display_name.strip(), email_clean, password_hash, created_at))
                conn.commit()
            return {
                "id": user_id,
                "display_name": display_name.strip(),
                "email": email_clean,
                "created_at": created_at
            }

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        email_clean = email.strip().lower()
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM users WHERE email = ?" if not self.use_postgres else "SELECT * FROM users WHERE email = %s"
            cur.execute(query, (email_clean,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(row) if not self.use_postgres else {
                "id": str(row[0]),
                "display_name": row[1],
                "email": row[2],
                "password_hash": row[3],
                "failed_attempts": row[4],
                "locked_until": str(row[5]) if row[5] else None,
                "last_login_at": str(row[6]) if row[6] else None,
                "created_at": str(row[7])
            }

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM users WHERE id = ?" if not self.use_postgres else "SELECT * FROM users WHERE id = %s"
            cur.execute(query, (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(row) if not self.use_postgres else {
                "id": str(row[0]),
                "display_name": row[1],
                "email": row[2],
                "password_hash": row[3],
                "failed_attempts": row[4],
                "locked_until": str(row[5]) if row[5] else None,
                "last_login_at": str(row[6]) if row[6] else None,
                "created_at": str(row[7])
            }

    def update_user_failed_attempts(self, email: str, count: int, locked_until: Optional[str] = None):
        email_clean = email.strip().lower()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("UPDATE users SET failed_attempts = %s, locked_until = %s WHERE email = %s", (count, locked_until, email_clean))
            else:
                cur.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE email = ?", (count, locked_until, email_clean))
                conn.commit()

    def update_user_login_success(self, email: str):
        email_clean = email.strip().lower()
        login_time = now_iso()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = %s WHERE email = %s", (login_time, email_clean))
            else:
                cur.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = ? WHERE email = ?", (login_time, email_clean))
                conn.commit()

    # ----------------------------------------------------
    # Projects & Membership
    # ----------------------------------------------------
    def create_project(self, name: str, user_id: str, role: str = "analyst", process_type: str = "general", description: str = "", department: str = "", goals: str = "", constraints: str = "") -> Dict[str, Any]:
        project_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO projects (id, name, process_type, description, department, goals, constraints, status, created_by, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'created', %s, %s, %s);
                """, (project_id, name, process_type, description, department, goals, constraints, user_id, created_at, created_at))
                cur.execute("""
                    INSERT INTO project_members (project_id, user_id, role, status, created_at)
                    VALUES (%s, %s, %s, 'active', %s);
                """, (project_id, user_id, role, created_at))
            else:
                cur.execute("""
                    INSERT INTO projects (id, name, process_type, description, department, goals, constraints, status, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'created', ?, ?, ?);
                """, (project_id, name, process_type, description, department, goals, constraints, user_id, created_at, created_at))
                cur.execute("""
                    INSERT INTO project_members (project_id, user_id, role, status, created_at)
                    VALUES (?, ?, ?, 'active', ?);
                """, (project_id, user_id, role, created_at))
            # Initial audit event in same transaction with canonical 0*64 initial prev_hash
            self._log_audit_event_tx(cur, project_id, "project_created", actor=user_id, subject=name, details={"role": role}, prev_hash="0"*64)
            if not self.use_postgres:
                conn.commit()

        return {
            "id": project_id,
            "name": name,
            "process_type": process_type,
            "description": description,
            "goals": goals,
            "constraints": constraints,
            "department": department,
            "stakeholders": [],
            "status": "created",
            "created_by": user_id,
            "created_at": created_at,
            "updated_at": created_at,
            "my_role": role,
            "members_count": 1,
            "waiting_count": 0,
        }

    def _format_project_row(self, row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        if not self.use_postgres:
            p_dict = {
                "id": str(row["id"]),
                "name": row["name"],
                "process_type": row["process_type"],
                "description": row["description"],
                "goals": row["goals"],
                "constraints": row["constraints"],
                "department": row["department"],
                "stakeholders": json.loads(row["stakeholders"]) if isinstance(row["stakeholders"], str) else row["stakeholders"],
                "status": row["status"],
                "created_by": str(row["created_by"]) if row["created_by"] else None,
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "my_role": row["my_role"] if "my_role" in row.keys() else None,
                "members_count": row["members_count"] if "members_count" in row.keys() else 0,
                "waiting_count": row["waiting_count"] if "waiting_count" in row.keys() else 0,
            }
        else:
            p_dict = {
                "id": str(row[0]),
                "name": row[1],
                "process_type": row[2],
                "description": row[3],
                "goals": row[4],
                "constraints": row[5],
                "department": row[6],
                "stakeholders": json.loads(row[7]) if isinstance(row[7], str) else row[7],
                "status": row[8],
                "created_by": str(row[9]) if row[9] else None,
                "created_at": str(row[10]),
                "updated_at": str(row[11]),
                "my_role": row[12] if len(row) > 12 else None,
                "members_count": row[13] if len(row) > 13 else 0,
                "waiting_count": row[14] if len(row) > 14 else 0,
            }
        if isinstance(p_dict.get("stakeholders"), str):
            try:
                p_dict["stakeholders"] = json.loads(p_dict["stakeholders"])
            except Exception:
                pass
        return p_dict

    def get_project(self, project_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    SELECT 
                        p.id, p.name, p.process_type, p.description, p.goals, p.constraints,
                        p.department, p.stakeholders, p.status, p.created_by, p.created_at, p.updated_at,
                        (SELECT pm.role FROM project_members pm WHERE pm.project_id = p.id AND pm.user_id = %s AND pm.status = 'active' LIMIT 1) AS my_role,
                        (SELECT count(*) FROM project_members pm WHERE pm.project_id = p.id AND pm.status = 'active') AS members_count,
                        (SELECT count(*) FROM clarification_items ci WHERE ci.project_id = p.id AND ci.status = 'open') AS waiting_count
                    FROM projects p
                    WHERE p.id = %s;
                """, (user_id, project_id))
            else:
                cur.execute("""
                    SELECT 
                        p.id, p.name, p.process_type, p.description, p.goals, p.constraints,
                        p.department, p.stakeholders, p.status, p.created_by, p.created_at, p.updated_at,
                        (SELECT pm.role FROM project_members pm WHERE pm.project_id = p.id AND pm.user_id = ? AND pm.status = 'active' LIMIT 1) AS my_role,
                        (SELECT count(*) FROM project_members pm WHERE pm.project_id = p.id AND pm.status = 'active') AS members_count,
                        (SELECT count(*) FROM clarification_items ci WHERE ci.project_id = p.id AND ci.status = 'open') AS waiting_count
                    FROM projects p
                    WHERE p.id = ?;
                """, (user_id, project_id))
            row = cur.fetchone()
            if not row:
                return None
            return self._format_project_row(row)

    def list_user_projects(self, user_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    SELECT 
                        p.id, p.name, p.process_type, p.description, p.goals, p.constraints,
                        p.department, p.stakeholders, p.status, p.created_by, p.created_at, p.updated_at,
                        m.role AS my_role,
                        (SELECT count(*) FROM project_members pm WHERE pm.project_id = p.id AND pm.status = 'active') AS members_count,
                        (SELECT count(*) FROM clarification_items ci WHERE ci.project_id = p.id AND ci.status = 'open') AS waiting_count
                    FROM projects p
                    JOIN project_members m ON m.project_id = p.id
                    WHERE m.user_id = %s AND m.status = 'active'
                    ORDER BY p.updated_at DESC;
                """, (user_id,))
            else:
                cur.execute("""
                    SELECT 
                        p.id, p.name, p.process_type, p.description, p.goals, p.constraints,
                        p.department, p.stakeholders, p.status, p.created_by, p.created_at, p.updated_at,
                        m.role AS my_role,
                        (SELECT count(*) FROM project_members pm WHERE pm.project_id = p.id AND pm.status = 'active') AS members_count,
                        (SELECT count(*) FROM clarification_items ci WHERE ci.project_id = p.id AND ci.status = 'open') AS waiting_count
                    FROM projects p
                    JOIN project_members m ON m.project_id = p.id
                    WHERE m.user_id = ? AND m.status = 'active'
                    ORDER BY p.updated_at DESC;
                """, (user_id,))
            rows = cur.fetchall()
            return [self._format_project_row(r) for r in rows if r]

    def get_member_role(self, project_id: str, user_id: str) -> Optional[str]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT role FROM project_members WHERE project_id = ? AND user_id = ? AND status = 'active'" if not self.use_postgres else "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s AND status = 'active'"
            cur.execute(query, (project_id, user_id))
            row = cur.fetchone()
            return row[0] if row else None

    def list_project_members(self, project_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    SELECT m.project_id, m.user_id, u.display_name, u.email, m.role, m.status, m.created_at
                    FROM project_members m
                    JOIN users u ON u.id = m.user_id
                    WHERE m.project_id = %s AND m.status = 'active'
                    ORDER BY m.created_at ASC;
                """, (project_id,))
            else:
                cur.execute("""
                    SELECT m.project_id, m.user_id, u.display_name, u.email, m.role, m.status, m.created_at
                    FROM project_members m
                    JOIN users u ON u.id = m.user_id
                    WHERE m.project_id = ? AND m.status = 'active'
                    ORDER BY m.created_at ASC;
                """, (project_id,))
            rows = cur.fetchall()
            return [{
                "project_id": str(r[0]),
                "user_id": str(r[1]),
                "display_name": r[2],
                "email": r[3],
                "role": r[4],
                "status": r[5],
                "created_at": str(r[6])
            } for r in rows]

    def remove_member(self, project_id: str, user_id: str):
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("UPDATE project_members SET status = 'removed' WHERE project_id = %s AND user_id = %s", (project_id, user_id))
            else:
                cur.execute("UPDATE project_members SET status = 'removed' WHERE project_id = ? AND user_id = ?", (project_id, user_id))
                conn.commit()

    # ----------------------------------------------------
    # Invitations
    # ----------------------------------------------------
    def create_invitation(self, project_id: str, email: str, role: str, invited_by: str) -> Dict[str, Any]:
        inv_id = str(uuid.uuid4())
        created_at = now_iso()
        email_clean = email.strip().lower()
        # 14 days expiration
        expires_at = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + 14 * 86400, timezone.utc).isoformat()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO project_invitations (id, project_id, email, role, status, invited_by, created_at, expires_at)
                    VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s);
                """, (inv_id, project_id, email_clean, role, invited_by, created_at, expires_at))
            else:
                cur.execute("""
                    INSERT INTO project_invitations (id, project_id, email, role, status, invited_by, created_at, expires_at)
                    VALUES (?, ?, ?, ?, 'pending', ?, ?, ?);
                """, (inv_id, project_id, email_clean, role, invited_by, created_at, expires_at))
                conn.commit()

        self.log_audit_event(project_id, "invitation_created", actor=invited_by, subject=email_clean, details={"role": role})
        return self.get_invitation(inv_id)

    def count_invitations_created_today(self, project_id: str) -> int:
        """How many invitations this project created today (brief 7.4 daily cap)."""
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute(
                    "SELECT count(*) FROM project_invitations "
                    f"WHERE project_id = {ph} AND created_at >= date_trunc('day', now())",
                    (project_id,),
                )
            else:
                cur.execute(
                    "SELECT count(*) FROM project_invitations "
                    f"WHERE project_id = {ph} AND substr(created_at, 1, 10) = substr(?, 1, 10)",
                    (project_id, now_iso()),
                )
            row = cur.fetchone()
        return int(row[0]) if row else 0

    def record_invitation_resend(self, inv_id: str, email_sent: bool) -> Optional[Dict[str, Any]]:
        """Increment resend_count and record the e-mail outcome (brief 7.4).

        The schema caps resend_count at 5 with a CHECK, so the caller must check
        the limit first; this method only records an allowed resend.
        """
        ph = "%s" if self.use_postgres else "?"
        status_value = "sent" if email_sent else "not_sent"
        sent_at = now_iso() if email_sent else None
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""UPDATE project_invitations
                    SET resend_count = resend_count + 1,
                        email_status = {ph},
                        email_sent_at = COALESCE({ph}, email_sent_at)
                    WHERE id = {ph}""",
                (status_value, sent_at, inv_id),
            )
            if not self.use_postgres:
                conn.commit()
        return self.get_invitation(inv_id)

    def get_invitation(self, inv_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    SELECT i.*, p.name as project_name, u.display_name as inviter_name
                    FROM project_invitations i
                    JOIN projects p ON p.id = i.project_id
                    JOIN users u ON u.id = i.invited_by
                    WHERE i.id = %s;
                """, (inv_id,))
            else:
                cur.execute("""
                    SELECT i.*, p.name as project_name, u.display_name as inviter_name
                    FROM project_invitations i
                    JOIN projects p ON p.id = i.project_id
                    JOIN users u ON u.id = i.invited_by
                    WHERE i.id = ?;
                """, (inv_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": str(row["id"] if not self.use_postgres else row[0]),
                "project_id": str(row["project_id"] if not self.use_postgres else row[1]),
                "email": row["email"] if not self.use_postgres else row[2],
                "role": row["role"] if not self.use_postgres else row[3],
                "status": row["status"] if not self.use_postgres else row[4],
                "invited_by": str(row["invited_by"] if not self.use_postgres else row[5]),
                "created_at": str(row["created_at"] if not self.use_postgres else row[6]),
                "expires_at": str(row["expires_at"] if not self.use_postgres else row[7]),
                "email_status": row["email_status"] if not self.use_postgres else row[10],
                "resend_count": row["resend_count"] if not self.use_postgres else row[12],
                "project_name": row["project_name"] if not self.use_postgres else row[13],
                "inviter_name": row["inviter_name"] if not self.use_postgres else row[14]
            }

    def list_pending_invitations_for_email(self, email: str) -> List[Dict[str, Any]]:
        email_clean = email.strip().lower()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    SELECT i.id FROM project_invitations i
                    WHERE i.email = %s AND i.status = 'pending'
                    ORDER BY i.created_at DESC;
                """, (email_clean,))
            else:
                cur.execute("""
                    SELECT i.id FROM project_invitations i
                    WHERE i.email = ? AND i.status = 'pending'
                    ORDER BY i.created_at DESC;
                """, (email_clean,))
            rows = cur.fetchall()
            inv_ids = [r[0] for r in rows]

        return [self.get_invitation(iid) for iid in inv_ids if iid]

    def list_project_invitations(self, project_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("SELECT id FROM project_invitations WHERE project_id = %s ORDER BY created_at DESC;", (project_id,))
            else:
                cur.execute("SELECT id FROM project_invitations WHERE project_id = ? ORDER BY created_at DESC;", (project_id,))
            rows = cur.fetchall()
            inv_ids = [r[0] for r in rows]
        return [self.get_invitation(iid) for iid in inv_ids if iid]

    def accept_invitation(self, inv_id: str, user_id: str) -> Dict[str, Any]:
        inv = self.get_invitation(inv_id)
        if not inv:
            raise ValueError("Invitation not found")
        accepted_at = now_iso()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    UPDATE project_invitations
                    SET status = 'accepted', accepted_by = %s, accepted_at = %s
                    WHERE id = %s;
                """, (user_id, accepted_at, inv_id))
                cur.execute("""
                    INSERT INTO project_members (project_id, user_id, role, status, invited_by, created_at)
                    VALUES (%s, %s, %s, 'active', %s, %s)
                    ON CONFLICT (project_id, user_id)
                    DO UPDATE SET role = EXCLUDED.role, status = 'active';
                """, (inv["project_id"], user_id, inv["role"], inv["invited_by"], accepted_at))
            else:
                cur.execute("""
                    UPDATE project_invitations
                    SET status = 'accepted', accepted_by = ?, accepted_at = ?
                    WHERE id = ?;
                """, (user_id, accepted_at, inv_id))
                cur.execute("""
                    INSERT OR REPLACE INTO project_members (project_id, user_id, role, status, invited_by, created_at)
                    VALUES (?, ?, ?, 'active', ?, ?);
                """, (inv["project_id"], user_id, inv["role"], inv["invited_by"], accepted_at))
                conn.commit()

        self.log_audit_event(inv["project_id"], "invitation_accepted", actor=user_id, subject=inv["email"], details={"role": inv["role"]})
        return self.get_invitation(inv_id)

    def decline_invitation(self, inv_id: str, user_id: str):
        inv = self.get_invitation(inv_id)
        if not inv:
            return
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("UPDATE project_invitations SET status = 'revoked' WHERE id = %s", (inv_id,))
            else:
                cur.execute("UPDATE project_invitations SET status = 'revoked' WHERE id = ?", (inv_id,))
                conn.commit()
        self.log_audit_event(inv["project_id"], "invitation_declined", actor=user_id, subject=inv["email"])

    def revoke_invitation(self, inv_id: str, revoker_user_id: str):
        inv = self.get_invitation(inv_id)
        if not inv:
            return
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("UPDATE project_invitations SET status = 'revoked' WHERE id = %s", (inv_id,))
            else:
                cur.execute("UPDATE project_invitations SET status = 'revoked' WHERE id = ?", (inv_id,))
                conn.commit()
        self.log_audit_event(inv["project_id"], "invitation_revoked", actor=revoker_user_id, subject=inv["email"])

    # ----------------------------------------------------
    # Documents, Sections & Chunks
    # ----------------------------------------------------
    def save_document(self, project_id: str, filename: str, mime_type: str, checksum: str, storage_path: str, size_bytes: int, uploaded_by: Optional[str] = None) -> Dict[str, Any]:
        doc_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO documents (id, project_id, filename, mime_type, checksum, version, storage_path, size_bytes, parse_status, uploaded_by, created_at)
                    VALUES (%s, %s, %s, %s, %s, 1, %s, %s, 'pending', %s, %s);
                """, (doc_id, project_id, filename, mime_type, checksum, storage_path, size_bytes, uploaded_by, created_at))
            else:
                cur.execute("""
                    INSERT INTO documents (id, project_id, filename, mime_type, checksum, version, storage_path, size_bytes, parse_status, uploaded_by, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'pending', ?, ?);
                """, (doc_id, project_id, filename, mime_type, checksum, storage_path, size_bytes, uploaded_by, created_at))
                conn.commit()
        return {
            "id": doc_id,
            "project_id": project_id,
            "filename": filename,
            "mime_type": mime_type,
            "checksum": checksum,
            "version": 1,
            "storage_path": storage_path,
            "size_bytes": size_bytes,
            "parse_status": "pending",
            "parse_warnings": [],
            "uploaded_by": uploaded_by,
            "created_at": created_at,
            "sections_count": 0
        }

    def update_document_parse_status(self, document_id: str, parse_status: str, warnings: List[str]):
        warnings_json = json.dumps(warnings)
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("UPDATE documents SET parse_status = %s, parse_warnings = %s WHERE id = %s", (parse_status, warnings_json, document_id))
            else:
                cur.execute("UPDATE documents SET parse_status = ?, parse_warnings = ? WHERE id = ?", (parse_status, warnings_json, document_id))
                conn.commit()

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM documents WHERE id = ?" if not self.use_postgres else "SELECT * FROM documents WHERE id = %s"
            cur.execute(query, (doc_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row) if not self.use_postgres else {
                "id": str(row[0]),
                "project_id": str(row[1]),
                "filename": row[2],
                "mime_type": row[3],
                "checksum": row[4],
                "version": row[5],
                "storage_path": row[6],
                "size_bytes": row[7],
                "parse_status": row[8],
                "parse_warnings": json.loads(row[9]) if isinstance(row[9], str) else row[9],
                "uploaded_by": str(row[10]) if row[10] else None,
                "created_at": str(row[11])
            }
            if isinstance(d.get("parse_warnings"), str):
                d["parse_warnings"] = json.loads(d["parse_warnings"])

            sec_query = "SELECT count(*) FROM document_sections WHERE document_id = ?" if not self.use_postgres else "SELECT count(*) FROM document_sections WHERE document_id = %s"
            cur.execute(sec_query, (doc_id,))
            d["sections_count"] = cur.fetchone()[0]
            return d

    def find_document_by_checksum(self, project_id: str, checksum: str) -> Optional[Dict[str, Any]]:
        """Existing document with the same content, so a duplicate can be reported.

        The documents table has UNIQUE (project_id, checksum, version); without
        this lookup the constraint surfaced as an unhandled HTTP 500 (finding F14).
        """
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, filename, created_at FROM documents "
                f"WHERE project_id = {ph} AND checksum = {ph} "
                f"ORDER BY version ASC LIMIT 1",
                (project_id, checksum),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {"id": str(row[0]), "filename": row[1], "created_at": str(row[2])}

    def delete_document(self, document_id: str) -> None:
        """Remove a document row that failed to store completely.

        Only used to undo a half-finished upload, so no user-visible record is
        ever deleted: sections and chunks cascade with it.
        """
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM documents WHERE id = {ph}", (document_id,))
            if not self.use_postgres:
                conn.commit()

    def list_project_documents(self, project_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    SELECT d.id, d.project_id, d.filename, d.mime_type, d.checksum, d.version,
                           d.storage_path, d.size_bytes, d.parse_status, d.parse_warnings,
                           d.uploaded_by, d.created_at, COUNT(s.id) AS sections_count
                    FROM documents d
                    LEFT JOIN document_sections s ON s.document_id = d.id
                    WHERE d.project_id = %s
                    GROUP BY d.id, d.project_id, d.filename, d.mime_type, d.checksum, d.version,
                             d.storage_path, d.size_bytes, d.parse_status, d.parse_warnings,
                             d.uploaded_by, d.created_at
                    ORDER BY d.created_at DESC;
                """, (project_id,))
                rows = cur.fetchall()
                docs = []
                for r in rows:
                    pw = json.loads(r[9]) if isinstance(r[9], str) else (r[9] or [])
                    docs.append({
                        "id": str(r[0]),
                        "project_id": str(r[1]),
                        "filename": r[2],
                        "mime_type": r[3],
                        "checksum": r[4],
                        "version": r[5],
                        "storage_path": r[6],
                        "size_bytes": r[7],
                        "parse_status": r[8],
                        "parse_warnings": pw,
                        "uploaded_by": str(r[10]) if r[10] else None,
                        "created_at": str(r[11]),
                        "sections_count": r[12]
                    })
                return docs
            else:
                cur.execute("""
                    SELECT d.id, d.project_id, d.filename, d.mime_type, d.checksum, d.version,
                           d.storage_path, d.size_bytes, d.parse_status, d.parse_warnings,
                           d.uploaded_by, d.created_at, COUNT(s.id) AS sections_count
                    FROM documents d
                    LEFT JOIN document_sections s ON s.document_id = d.id
                    WHERE d.project_id = ?
                    GROUP BY d.id
                    ORDER BY d.created_at DESC;
                """, (project_id,))
                rows = cur.fetchall()
                docs = []
                for r in rows:
                    pw = json.loads(r["parse_warnings"]) if isinstance(r["parse_warnings"], str) else (r["parse_warnings"] or [])
                    docs.append({
                        "id": str(r["id"]),
                        "project_id": str(r["project_id"]),
                        "filename": r["filename"],
                        "mime_type": r["mime_type"],
                        "checksum": r["checksum"],
                        "version": r["version"],
                        "storage_path": r["storage_path"],
                        "size_bytes": r["size_bytes"],
                        "parse_status": r["parse_status"],
                        "parse_warnings": pw,
                        "uploaded_by": str(r["uploaded_by"]) if r["uploaded_by"] else None,
                        "created_at": str(r["created_at"]),
                        "sections_count": r["sections_count"]
                    })
                return docs

    def _save_document_sections_tx(self, cur, document_id: str, sections: List[Dict[str, Any]], project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not sections:
            return []
        saved = []
        params = []
        for i, s in enumerate(sections, 1):
            sec_id = str(uuid.uuid4())
            sec_idx = s.get("section_index", i)
            page_no = s.get("page_number")
            title = s.get("section_title")
            text = s.get("text", "")
            read_from_image = bool(s.get("read_from_image", False))
            saved.append({
                "id": sec_id,
                "document_id": document_id,
                "section_index": sec_idx,
                "page_number": page_no,
                "section_title": title,
                "text": text,
                "read_from_image": read_from_image
            })
            params.extend([
                sec_id,
                document_id,
                sec_idx,
                page_no,
                title,
                text,
                read_from_image if self.use_postgres else (1 if read_from_image else 0)
            ])

        placeholders = ", ".join(["(%s, %s, %s, %s, %s, %s, %s)"] * len(sections)) if self.use_postgres else ", ".join(["(?, ?, ?, ?, ?, ?, ?)"] * len(sections))
        sql = f"INSERT INTO document_sections (id, document_id, section_index, page_number, section_title, text, read_from_image) VALUES {placeholders};"
        cur.execute(sql, params)
        self._save_document_chunks_tx(cur, document_id, saved, project_id)
        return saved

    # Retrieval chunks. SPEC-03-05 and brief 4.6 require them ("chunk, keeping
    # document ID, page/section ... start with keyword/full-text search"), and the
    # table existed in the schema, but nothing ever wrote a row to it.
    CHUNK_TARGET_CHARS = 1200
    CHUNK_OVERLAP_CHARS = 120

    def _chunk_section_text(self, text: str) -> List[str]:
        """Split one section into retrieval-sized pieces on sentence boundaries."""
        text = (text or "").strip()
        if not text:
            return []
        if len(text) <= self.CHUNK_TARGET_CHARS:
            return [text]

        pieces: List[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.CHUNK_TARGET_CHARS, len(text))
            if end < len(text):
                # Prefer a sentence end, then a line break, then a space.
                for sep in (". ", ".\n", "\n", " "):
                    cut = text.rfind(sep, start + self.CHUNK_TARGET_CHARS // 2, end)
                    if cut != -1:
                        end = cut + len(sep)
                        break
            piece = text[start:end].strip()
            if piece:
                pieces.append(piece)
            if end >= len(text):
                break
            start = max(end - self.CHUNK_OVERLAP_CHARS, end if end > start else start + 1)
        return pieces

    def _save_document_chunks_tx(self, cur, document_id: str, sections: List[Dict[str, Any]], project_id: Optional[str] = None) -> int:
        """Write retrieval chunks for the given sections, inside the same transaction.

        The caller passes project_id when it knows it, so a chunked upload costs
        one extra INSERT and no extra SELECT.
        """
        if not project_id:
            cur.execute(
                "SELECT project_id FROM documents WHERE id = %s" if self.use_postgres
                else "SELECT project_id FROM documents WHERE id = ?",
                (document_id,),
            )
            row = cur.fetchone()
            if not row:
                return 0
            project_id = str(row[0])

        params: List[Any] = []
        count = 0
        for section in sections:
            for piece in self._chunk_section_text(section.get("text", "")):
                params.extend([
                    str(uuid.uuid4()), project_id, document_id,
                    section["id"], count, piece,
                ])
                count += 1
        if not count:
            return 0

        row_sql = "(%s, %s, %s, %s, %s, %s)" if self.use_postgres else "(?, ?, ?, ?, ?, ?)"
        cur.execute(
            "INSERT INTO document_chunks (id, project_id, document_id, section_id, chunk_index, text) "
            f"VALUES {', '.join([row_sql] * count)};",
            params,
        )
        return count

    def search_document_chunks(self, project_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Keyword retrieval over stored chunks, scoped to one project (brief 4.6).

        PostgreSQL uses the generated tsvector column and ts_rank; SQLite falls
        back to LIKE matching, which is enough for local development.
        """
        if not (query or "").strip():
            return []
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute(
                    """
                    SELECT c.id, c.document_id, c.section_id, c.text
                    FROM document_chunks c
                    WHERE c.project_id = %s AND c.tsv @@ plainto_tsquery('english', %s)
                    ORDER BY ts_rank(c.tsv, plainto_tsquery('english', %s)) DESC
                    LIMIT %s
                    """,
                    (project_id, query, query, limit),
                )
            else:
                terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
                if not terms:
                    return []
                where = " OR ".join(["lower(c.text) LIKE ?"] * len(terms))
                cur.execute(
                    f"""SELECT c.id, c.document_id, c.section_id, c.text
                        FROM document_chunks c
                        WHERE c.project_id = ? AND ({where})
                        LIMIT ?""",
                    (project_id, *[f"%{t}%" for t in terms], limit),
                )
            return [
                {"id": str(r[0]), "document_id": str(r[1]),
                 "section_id": str(r[2]) if r[2] else None, "text": r[3]}
                for r in cur.fetchall()
            ]

    def save_document_sections(self, document_id: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not sections:
            return []
        with self.get_connection() as conn:
            cur = conn.cursor()
            res = self._save_document_sections_tx(cur, document_id, sections)
            if not self.use_postgres:
                conn.commit()
            return res

    def save_document_with_sections(
        self,
        project_id: str,
        filename: str,
        mime_type: str,
        checksum: str,
        storage_path: str,
        size_bytes: int,
        uploaded_by: Optional[str],
        sections: List[Dict[str, Any]],
        warnings: List[str]
    ) -> Dict[str, Any]:
        """Atomically insert document, bulk sections, and audit log in a single transaction."""
        doc_id = str(uuid.uuid4())
        created_at = now_iso()
        warnings_json = json.dumps(warnings)

        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO documents (id, project_id, filename, mime_type, checksum, version, storage_path, size_bytes, parse_status, parse_warnings, uploaded_by, created_at)
                    VALUES (%s, %s, %s, %s, %s, 1, %s, %s, 'parsed', %s, %s, %s);
                """, (doc_id, project_id, filename, mime_type, checksum, storage_path, size_bytes, warnings_json, uploaded_by, created_at))
            else:
                cur.execute("""
                    INSERT INTO documents (id, project_id, filename, mime_type, checksum, version, storage_path, size_bytes, parse_status, parse_warnings, uploaded_by, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'parsed', ?, ?, ?);
                """, (doc_id, project_id, filename, mime_type, checksum, storage_path, size_bytes, warnings_json, uploaded_by, created_at))

            if sections:
                self._save_document_sections_tx(cur, doc_id, sections, project_id=project_id)

            self._log_audit_event_tx(
                cur,
                project_id,
                "document_uploaded",
                actor=uploaded_by or "system",
                subject=filename,
                details={"sections_count": len(sections)}
            )

            if not self.use_postgres:
                conn.commit()

        return {
            "id": doc_id,
            "project_id": project_id,
            "filename": filename,
            "mime_type": mime_type,
            "checksum": checksum,
            "version": 1,
            "storage_path": storage_path,
            "size_bytes": size_bytes,
            "parse_status": "parsed",
            "parse_warnings": warnings,
            "uploaded_by": uploaded_by,
            "created_at": created_at,
            "sections_count": len(sections)
        }

    def list_document_sections(self, document_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM document_sections WHERE document_id = ? ORDER BY section_index ASC" if not self.use_postgres else "SELECT * FROM document_sections WHERE document_id = %s ORDER BY section_index ASC"
            cur.execute(query, (document_id,))
            rows = cur.fetchall()
            result = []
            for r in rows:
                if self.use_postgres:
                    result.append({
                        "id": str(r[0]),
                        "document_id": str(r[1]),
                        "section_index": r[2],
                        "page_number": r[3],
                        "section_title": r[4],
                        "text": r[5],
                        "read_from_image": bool(r[6]) if len(r) > 6 else False
                    })
                else:
                    read_img = bool(r["read_from_image"]) if "read_from_image" in r.keys() else False
                    result.append({
                        "id": str(r["id"]),
                        "document_id": str(r["document_id"]),
                        "section_index": r["section_index"],
                        "page_number": r["page_number"],
                        "section_title": r["section_title"],
                        "text": r["text"],
                        "read_from_image": read_img
                    })
            return result

    def get_section(self, section_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM document_sections WHERE id = ?" if not self.use_postgres else "SELECT * FROM document_sections WHERE id = %s"
            cur.execute(query, (section_id,))
            r = cur.fetchone()
            if not r:
                return None
            if self.use_postgres:
                return {
                    "id": str(r[0]),
                    "document_id": str(r[1]),
                    "section_index": r[2],
                    "page_number": r[3],
                    "section_title": r[4],
                    "text": r[5],
                    "read_from_image": bool(r[6]) if len(r) > 6 else False
                }
            else:
                read_img = bool(r["read_from_image"]) if "read_from_image" in r.keys() else False
                return {
                    "id": str(r["id"]),
                    "document_id": str(r["document_id"]),
                    "section_index": r["section_index"],
                    "page_number": r["page_number"],
                    "section_title": r["section_title"],
                    "text": r["text"],
                    "read_from_image": read_img
                }

    # ----------------------------------------------------
    # Evidence Items
    # ----------------------------------------------------
    # ----------------------------------------------------
    # Cached "What I understood" view (derived data, per content checksum)
    # ----------------------------------------------------
    def get_document_understanding(self, document_id: str, checksum: str) -> Optional[Dict[str, Any]]:
        """Return the cached understanding if it was computed from this exact content."""
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT content_json FROM document_understanding "
                f"WHERE document_id = {ph} AND checksum = {ph}",
                (document_id, checksum),
            )
            row = cur.fetchone()
        if not row or not row[0]:
            return None
        payload = row[0]
        if isinstance(payload, (str, bytes)):
            try:
                payload = json.loads(payload)
            except Exception:
                return None
        return payload

    def save_document_understanding(self, document_id: str, checksum: str, content: Dict[str, Any]) -> None:
        """Store the understanding for this content, replacing any older one."""
        payload = json.dumps(content)
        created_at = now_iso()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute(
                    """
                    INSERT INTO document_understanding (document_id, checksum, content_json, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (document_id)
                    DO UPDATE SET checksum = EXCLUDED.checksum,
                                  content_json = EXCLUDED.content_json,
                                  created_at = EXCLUDED.created_at;
                    """,
                    (document_id, checksum, payload, created_at),
                )
            else:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO document_understanding
                        (document_id, checksum, content_json, created_at)
                    VALUES (?, ?, ?, ?);
                    """,
                    (document_id, checksum, payload, created_at),
                )
                conn.commit()

    def save_evidence_item(self, project_id: str, section_id: str, claim: str, quote: str, claim_type: str = "other", confidence: float = 0.90) -> Dict[str, Any]:
        """Save evidence item after verifying quote is a verbatim substring of section."""
        sec = self.get_section(section_id)
        if not sec or quote not in sec["text"]:
            raise ValueError(f"Evidence quote verification failed: quote is not an exact substring of section {section_id}")

        evd_key = self.mint_key(project_id, "EVD")
        evd_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO evidence_items (id, project_id, evidence_key, document_section_id, claim, quote, claim_type, confidence, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'extracted', %s);
                """, (evd_id, project_id, evd_key, section_id, claim, quote, claim_type, confidence, created_at))
            else:
                cur.execute("""
                    INSERT INTO evidence_items (id, project_id, evidence_key, document_section_id, claim, quote, claim_type, confidence, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'extracted', ?);
                """, (evd_id, project_id, evd_key, section_id, claim, quote, claim_type, confidence, created_at))
                conn.commit()

        return {
            "id": evd_id,
            "project_id": project_id,
            "evidence_key": evd_key,
            "document_section_id": section_id,
            "claim": claim,
            "quote": quote,
            "claim_type": claim_type,
            "confidence": confidence,
            "status": "extracted",
            "created_at": created_at
        }

    def list_project_evidence(self, project_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    SELECT e.*, s.section_title, s.section_index, s.page_number, d.filename as document_filename
                    FROM evidence_items e
                    JOIN document_sections s ON s.id = e.document_section_id
                    JOIN documents d ON d.id = s.document_id
                    WHERE e.project_id = %s
                    ORDER BY e.evidence_key ASC;
                """, (project_id,))
            else:
                cur.execute("""
                    SELECT e.*, s.section_title, s.section_index, s.page_number, d.filename as document_filename
                    FROM evidence_items e
                    JOIN document_sections s ON s.id = e.document_section_id
                    JOIN documents d ON d.id = s.document_id
                    WHERE e.project_id = ?
                    ORDER BY e.evidence_key ASC;
                """, (project_id,))
            rows = cur.fetchall()
            return [{
                "id": str(r["id"] if not self.use_postgres else r[0]),
                "project_id": str(r["project_id"] if not self.use_postgres else r[1]),
                "evidence_key": r["evidence_key"] if not self.use_postgres else r[2],
                "document_section_id": str(r["document_section_id"] if not self.use_postgres else r[3]),
                "claim": r["claim"] if not self.use_postgres else r[4],
                "quote": r["quote"] if not self.use_postgres else r[5],
                "claim_type": r["claim_type"] if not self.use_postgres else r[6],
                "confidence": float(r["confidence"] if not self.use_postgres else r[7]),
                "status": r["status"] if not self.use_postgres else r[8],
                "created_at": str(r["created_at"] if not self.use_postgres else r[9]),
                "section_title": r["section_title"] if not self.use_postgres else r[10],
                "section_index": r["section_index"] if not self.use_postgres else r[11],
                "page_number": r["page_number"] if not self.use_postgres else r[12],
                "document_filename": r["document_filename"] if not self.use_postgres else r[13]
            } for r in rows]

    # ----------------------------------------------------
    # Business Rules
    # ----------------------------------------------------
    def save_business_rule(self, project_id: str, description: str, condition_json: Dict[str, Any], evidence_ids: List[str]) -> Dict[str, Any]:
        rule_key = self.mint_key(project_id, "BR")
        rule_id = str(uuid.uuid4())
        created_at = now_iso()
        cond_str = json.dumps(condition_json)
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO business_rules (id, project_id, rule_key, description, condition_json, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, 'needs_review', %s);
                """, (rule_id, project_id, rule_key, description, cond_str, created_at))
                for eid in evidence_ids:
                    cur.execute("INSERT INTO rule_evidence (rule_id, evidence_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (rule_id, eid))
            else:
                cur.execute("""
                    INSERT INTO business_rules (id, project_id, rule_key, description, condition_json, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'needs_review', ?);
                """, (rule_id, project_id, rule_key, description, cond_str, created_at))
                for eid in evidence_ids:
                    cur.execute("INSERT OR IGNORE INTO rule_evidence (rule_id, evidence_id) VALUES (?, ?);", (rule_id, eid))
                conn.commit()

        return self.get_business_rule(rule_id)

    def get_business_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM business_rules WHERE id = ?" if not self.use_postgres else "SELECT * FROM business_rules WHERE id = %s"
            cur.execute(query, (rule_id,))
            r = cur.fetchone()
            if not r:
                return None
            res = {
                "id": str(r["id"] if not self.use_postgres else r[0]),
                "project_id": str(r["project_id"] if not self.use_postgres else r[1]),
                "rule_key": r["rule_key"] if not self.use_postgres else r[2],
                "description": r["description"] if not self.use_postgres else r[3],
                "condition_json": _jload(r["condition_json"] if not self.use_postgres else r[4]),
                "status": r["status"] if not self.use_postgres else r[5],
                "supersedes_rule_id": str(r["supersedes_rule_id"] if not self.use_postgres else r[6]) if (r["supersedes_rule_id"] if not self.use_postgres else r[6]) else None,
                "approved_by": str(r["approved_by"] if not self.use_postgres else r[7]) if (r["approved_by"] if not self.use_postgres else r[7]) else None,
                "approved_at": str(r["approved_at"] if not self.use_postgres else r[8]) if (r["approved_at"] if not self.use_postgres else r[8]) else None,
                "created_at": str(r["created_at"] if not self.use_postgres else r[9])
            }
            # Fetch the full source context for each supporting evidence item, so
            # a question built from this rule can show everything brief 7.12
            # requires (quote, file name, section number and title, page number).
            ph = "%s" if self.use_postgres else "?"
            cur.execute(
                f"""
                SELECT e.id, e.evidence_key, e.quote,
                       d.filename, s.section_index, s.section_title, s.page_number
                FROM rule_evidence re
                JOIN evidence_items e ON e.id = re.evidence_id
                JOIN document_sections s ON s.id = e.document_section_id
                JOIN documents d ON d.id = s.document_id
                WHERE re.rule_id = {ph}
                ORDER BY s.section_index ASC
                """,
                (rule_id,),
            )
            erows = cur.fetchall()
            res["sources"] = [
                {
                    "id": str(er[0]),
                    "evidence_key": er[1],
                    "quote": er[2],
                    "document_name": er[3],
                    "section_index": er[4],
                    "section_title": er[5],
                    "page_number": er[6],
                }
                for er in erows
            ]
            res["evidence_quotes"] = [er[2] for er in erows]
            res["document_name"] = erows[0][3] if erows else None
            res["section_title"] = erows[0][5] if erows else None
            return res

    def get_step_sources(self, step_id: str) -> List[Dict[str, Any]]:
        """Source passages behind a process step, via step_evidence (brief 7.12 item 4)."""
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT e.id, e.evidence_key, e.quote,
                       d.filename, s.section_index, s.section_title, s.page_number
                FROM step_evidence se
                JOIN evidence_items e ON e.id = se.evidence_id
                JOIN document_sections s ON s.id = e.document_section_id
                JOIN documents d ON d.id = s.document_id
                WHERE se.step_id = {ph}
                ORDER BY s.section_index ASC
                """,
                (step_id,),
            )
            return [
                {
                    "id": str(r[0]),
                    "evidence_key": r[1],
                    "quote": r[2],
                    "document_name": r[3],
                    "section_index": r[4],
                    "section_title": r[5],
                    "page_number": r[6],
                }
                for r in cur.fetchall()
            ]

    def get_evidence_sources(self, evidence_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Source context for the given evidence items, keyed by id (one query)."""
        if not evidence_ids:
            return {}
        ph = "%s" if self.use_postgres else "?"
        placeholders = ", ".join([ph] * len(evidence_ids))
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT e.id, e.evidence_key, e.quote,
                       d.filename, s.section_index, s.section_title, s.page_number
                FROM evidence_items e
                JOIN document_sections s ON s.id = e.document_section_id
                JOIN documents d ON d.id = s.document_id
                WHERE e.id IN ({placeholders})
                """,
                tuple(evidence_ids),
            )
            return {
                str(r[0]): {
                    "id": str(r[0]),
                    "evidence_key": r[1],
                    "quote": r[2],
                    "document_name": r[3],
                    "section_index": r[4],
                    "section_title": r[5],
                    "page_number": r[6],
                }
                for r in cur.fetchall()
            }

    def list_project_business_rules(self, project_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT id FROM business_rules WHERE project_id = ? ORDER BY rule_key ASC" if not self.use_postgres else "SELECT id FROM business_rules WHERE project_id = %s ORDER BY rule_key ASC"
            cur.execute(query, (project_id,))
            rows = cur.fetchall()
            rule_ids = [r[0] for r in rows]
        return [self.get_business_rule(rid) for rid in rule_ids if rid]

    def update_rule_status(self, rule_id: str, status: str, approved_by: Optional[str] = None, supersedes_rule_id: Optional[str] = None):
        """Enforce check: status cannot be 'approved' without non-null approved_by."""
        if status == "approved" and not approved_by:
            raise ValueError("Rule approval constraint violation: approved_by cannot be null when status is 'approved'")
        approved_at = now_iso() if status == "approved" else None
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    UPDATE business_rules
                    SET status = %s, approved_by = %s, approved_at = %s, supersedes_rule_id = COALESCE(%s, supersedes_rule_id)
                    WHERE id = %s;
                """, (status, approved_by, approved_at, supersedes_rule_id, rule_id))
            else:
                cur.execute("""
                    UPDATE business_rules
                    SET status = ?, approved_by = ?, approved_at = ?, supersedes_rule_id = COALESCE(?, supersedes_rule_id)
                    WHERE id = ?;
                """, (status, approved_by, approved_at, supersedes_rule_id, rule_id))
                conn.commit()

    # ----------------------------------------------------
    # Process Versions and Steps
    # ----------------------------------------------------
    def create_process_version(self, project_id: str, version: int, as_is_json: Optional[Dict[str, Any]] = None, to_be_json: Optional[Dict[str, Any]] = None, status: str = "draft") -> Dict[str, Any]:
        pv_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.get_connection() as conn:
            cur = conn.cursor()
            as_is_str = json.dumps(as_is_json) if as_is_json else None
            to_be_str = json.dumps(to_be_json) if to_be_json else None
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO process_versions (id, project_id, version, as_is_json, to_be_json, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (project_id, version)
                    DO UPDATE SET as_is_json = EXCLUDED.as_is_json, to_be_json = EXCLUDED.to_be_json, status = EXCLUDED.status;
                """, (pv_id, project_id, version, as_is_str, to_be_str, status, created_at))
            else:
                cur.execute("""
                    INSERT OR REPLACE INTO process_versions (id, project_id, version, as_is_json, to_be_json, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (pv_id, project_id, version, as_is_str, to_be_str, status, created_at))
                conn.commit()
        return self.get_latest_process_version(project_id)

    def get_latest_process_version(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM process_versions WHERE project_id = ? ORDER BY version DESC LIMIT 1" if not self.use_postgres else "SELECT * FROM process_versions WHERE project_id = %s ORDER BY version DESC LIMIT 1"
            cur.execute(query, (project_id,))
            r = cur.fetchone()
            if not r:
                return None
            pv_dict = {
                "id": str(r["id"] if not self.use_postgres else r[0]),
                "project_id": str(r["project_id"] if not self.use_postgres else r[1]),
                "version": r["version"] if not self.use_postgres else r[2],
                "as_is_json": _jload(r["as_is_json"] if not self.use_postgres else r[3]),
                "to_be_json": _jload(r["to_be_json"] if not self.use_postgres else r[4]),
                "status": r["status"] if not self.use_postgres else r[5],
                "approved_by": str(r["approved_by"] if not self.use_postgres else r[6]) if (r["approved_by"] if not self.use_postgres else r[6]) else None,
                "created_at": str(r["created_at"] if not self.use_postgres else r[7]),
                "steps": []
            }
            pv_dict["steps"] = self.list_process_steps(pv_dict["id"])
            return pv_dict

    def update_process_version_decision(self, pv_id: str, decision: str, reviewer_id: str, reviewer_role: str, comment: Optional[str] = None):
        """Enforces Part 7.9 & schema: decision reject requires comment; approval requires human."""
        if decision != "approve" and (not comment or not comment.strip()):
            raise ValueError("Comment is required when requesting changes or rejecting a process version.")
        new_status = "approved" if decision == "approve" else ("rejected" if decision == "reject" else "needs_review")
        approver = reviewer_id if decision == "approve" else None
        timestamp = now_iso()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    UPDATE process_versions
                    SET status = %s, approved_by = %s
                    WHERE id = %s
                    RETURNING project_id;
                """, (new_status, approver, pv_id))
                pid = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO approvals (id, project_id, target_type, target_id, decision, reviewer, reviewer_role, comment, timestamp)
                    VALUES (%s, %s, 'process_version', %s, %s, %s, %s, %s, %s);
                """, (str(uuid.uuid4()), pid, pv_id, decision, reviewer_id, reviewer_role, comment, timestamp))
            else:
                cur.execute("SELECT project_id FROM process_versions WHERE id = ?", (pv_id,))
                pid = cur.fetchone()[0]
                cur.execute("UPDATE process_versions SET status = ?, approved_by = ? WHERE id = ?", (new_status, approver, pv_id))
                cur.execute("""
                    INSERT INTO approvals (id, project_id, target_type, target_id, decision, reviewer, reviewer_role, comment, timestamp)
                    VALUES (?, ?, 'process_version', ?, ?, ?, ?, ?, ?);
                """, (str(uuid.uuid4()), pid, pv_id, decision, reviewer_id, reviewer_role, comment, timestamp))
                conn.commit()

        self.log_audit_event(pid, "process_decision_recorded", actor=reviewer_id, subject=f"version {pv_id}", details={"decision": decision, "role": reviewer_role, "comment": comment})

    def save_process_step(self, project_id: str, process_version_id: str, name: str, actor: Optional[str], step_type: str, sequence: int, inputs: List[str], outputs: List[str], unknowns: List[str], automation: Optional[str] = None, human_approval_required: bool = False, evidence_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        step_key = self.mint_key(project_id, "STEP")
        step_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            cur = conn.cursor()
            inp_s = json.dumps(inputs)
            out_s = json.dumps(outputs)
            unk_s = json.dumps(unknowns)
            har_val = 1 if human_approval_required else 0
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO process_steps (id, process_version_id, step_key, name, actor, step_type, sequence, inputs, outputs, unknowns, automation, human_approval_required)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (step_id, process_version_id, step_key, name, actor, step_type, sequence, inp_s, out_s, unk_s, automation, human_approval_required))
                if evidence_ids:
                    for eid in evidence_ids:
                        cur.execute("INSERT INTO step_evidence (step_id, evidence_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;", (step_id, eid))
            else:
                cur.execute("""
                    INSERT INTO process_steps (id, process_version_id, step_key, name, actor, step_type, sequence, inputs, outputs, unknowns, automation, human_approval_required)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (step_id, process_version_id, step_key, name, actor, step_type, sequence, inp_s, out_s, unk_s, automation, har_val))
                if evidence_ids:
                    for eid in evidence_ids:
                        cur.execute("INSERT OR IGNORE INTO step_evidence (step_id, evidence_id) VALUES (?, ?);", (step_id, eid))
                conn.commit()

        return {
            "id": step_id,
            "process_version_id": process_version_id,
            "step_key": step_key,
            "name": name,
            "actor": actor,
            "step_type": step_type,
            "sequence": sequence,
            "inputs": inputs,
            "outputs": outputs,
            "unknowns": unknowns,
            "automation": automation,
            "human_approval_required": human_approval_required
        }

    def list_process_steps(self, process_version_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM process_steps WHERE process_version_id = ? ORDER BY sequence ASC" if not self.use_postgres else "SELECT * FROM process_steps WHERE process_version_id = %s ORDER BY sequence ASC"
            cur.execute(query, (process_version_id,))
            rows = cur.fetchall()
            result = []
            for r in rows:
                sid = str(r["id"] if not self.use_postgres else r[0])
                eq_query = "SELECT e.evidence_key FROM step_evidence se JOIN evidence_items e ON e.id = se.evidence_id WHERE se.step_id = ?" if not self.use_postgres else "SELECT e.evidence_key FROM step_evidence se JOIN evidence_items e ON e.id = se.evidence_id WHERE se.step_id = %s"
                cur.execute(eq_query, (sid,))
                ekeys = [er[0] for er in cur.fetchall()]
                result.append({
                    "id": sid,
                    "process_version_id": str(r["process_version_id"] if not self.use_postgres else r[1]),
                    "step_key": r["step_key"] if not self.use_postgres else r[2],
                    "name": r["name"] if not self.use_postgres else r[3],
                    "actor": r["actor"] if not self.use_postgres else r[4],
                    "step_type": r["step_type"] if not self.use_postgres else r[5],
                    "sequence": r["sequence"] if not self.use_postgres else r[6],
                    "inputs": _jload(r["inputs"] if not self.use_postgres else r[7], []),
                    "outputs": _jload(r["outputs"] if not self.use_postgres else r[8], []),
                    "unknowns": _jload(r["unknowns"] if not self.use_postgres else r[9], []),
                    "automation": r["automation"] if not self.use_postgres else r[10],
                    "human_approval_required": bool(r["human_approval_required"] if not self.use_postgres else r[11]),
                    "evidence_keys": ekeys
                })
            return result

    # ----------------------------------------------------
    # Clarification Items (HITL)
    # ----------------------------------------------------
    def save_clarification_item(self, project_id: str, question: str, reason: str, kind: str, assigned_role: str, options: List[Dict[str, Any]], fingerprint: str, ai_suggestion: Optional[str] = None, run_id: Optional[str] = None, link_targets: Optional[List[Tuple[str, str]]] = None) -> Optional[Dict[str, Any]]:
        """Saves a clarification item enforcing unique fingerprint per project."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            # Check fingerprint
            chk_query = "SELECT id FROM clarification_items WHERE project_id = ? AND fingerprint = ?" if not self.use_postgres else "SELECT id FROM clarification_items WHERE project_id = %s AND fingerprint = %s"
            cur.execute(chk_query, (project_id, fingerprint))
            existing = cur.fetchone()
            if existing:
                return self.get_clarification_item(existing[0])

        q_key = self.mint_key(project_id, "Q")
        q_id = str(uuid.uuid4())
        created_at = now_iso()
        opt_s = json.dumps(options)
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO clarification_items (id, project_id, run_id, question_key, question, reason, kind, assigned_role, options, ai_suggestion, status, fingerprint, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s);
                """, (q_id, project_id, run_id, q_key, question, reason, kind, assigned_role, opt_s, ai_suggestion, fingerprint, created_at))
                if link_targets:
                    for ttype, tid in link_targets:
                        cur.execute("INSERT INTO clarification_links (clarification_id, target_type, target_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;", (q_id, ttype, tid))
            else:
                cur.execute("""
                    INSERT INTO clarification_items (id, project_id, run_id, question_key, question, reason, kind, assigned_role, options, ai_suggestion, status, fingerprint, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?);
                """, (q_id, project_id, run_id, q_key, question, reason, kind, assigned_role, opt_s, ai_suggestion, fingerprint, created_at))
                if link_targets:
                    for ttype, tid in link_targets:
                        cur.execute("INSERT OR IGNORE INTO clarification_links (clarification_id, target_type, target_id) VALUES (?, ?, ?);", (q_id, ttype, tid))
                conn.commit()

        self.log_audit_event(project_id, "question_asked", actor="system", subject=q_key, details={"kind": kind, "assigned_role": assigned_role})
        return self.get_clarification_item(q_id)

    # -- Clarification reads -------------------------------------------------
    # One JOINed query loads items together with their links and the full
    # evidence context brief 7.12 requires (quote, document file name, section
    # number and title, page number). Previously each item cost 2 extra queries
    # on its own connection: 29 questions meant 31 connections and 60 queries
    # (finding F1/N+1 in REVIEW_REPORT.md).
    _CLARIFICATION_SELECT = """
        SELECT c.id, c.project_id, c.run_id, c.question_key, c.question, c.reason,
               c.kind, c.assigned_role, c.options, c.ai_suggestion, c.status,
               c.answer, c.answered_by, c.answered_at, c.fingerprint, c.created_at,
               p.name, u.display_name,
               l.target_type, l.target_id,
               e.evidence_key, e.quote,
               s.section_index, s.section_title, s.page_number,
               d.filename
        FROM clarification_items c
        JOIN projects p ON p.id = c.project_id
        LEFT JOIN users u ON u.id = c.answered_by
        LEFT JOIN clarification_links l ON l.clarification_id = c.id
        LEFT JOIN evidence_items e ON l.target_type = 'evidence' AND e.id = l.target_id
        LEFT JOIN document_sections s ON s.id = e.document_section_id
        LEFT JOIN documents d ON d.id = s.document_id
    """

    # Column offsets for the projection above (same order on both engines).
    _C_ID, _C_PROJECT, _C_RUN, _C_KEY, _C_QUESTION, _C_REASON = 0, 1, 2, 3, 4, 5
    _C_KIND, _C_ROLE, _C_OPTIONS, _C_AI, _C_STATUS = 6, 7, 8, 9, 10
    _C_ANSWER, _C_ANSWERED_BY, _C_ANSWERED_AT, _C_FINGERPRINT, _C_CREATED = 11, 12, 13, 14, 15
    _C_PROJECT_NAME, _C_ANSWERER_NAME = 16, 17
    _C_TARGET_TYPE, _C_TARGET_ID = 18, 19
    _C_EVIDENCE_KEY, _C_EVIDENCE_QUOTE = 20, 21
    _C_SECTION_INDEX, _C_SECTION_TITLE, _C_PAGE_NUMBER, _C_FILENAME = 22, 23, 24, 25

    @staticmethod
    def _consequence_summary(kind: str, linked_rules: List[str]) -> str:
        """Plain description of what an answer will change (brief 7.12 item 6).

        Derived deterministically from stored records, never written by the model,
        and computed on read so no schema change is needed.
        """
        rebuilt = "The requirements and the BRD, FRD and PRD that depend on it are rebuilt."
        if kind == "conflicting_rules":
            if len(linked_rules) >= 2:
                return (
                    "The rule you choose is kept and confirmed by you; the other rule is "
                    f"marked superseded (never deleted). {rebuilt}"
                )
            return f"The rule you choose is kept and confirmed by you. {rebuilt}"
        if kind == "missing_actor":
            return (
                "The actor you name is recorded on this step and \"actor not stated\" is "
                f"removed from its unknowns. {rebuilt}"
            )
        if kind == "ambiguous_term":
            return (
                "Your definition is stored as a verified fact and used wherever this term "
                f"appears. {rebuilt}"
            )
        if kind == "missing_info":
            return f"Your answer is stored as a verified fact for this gap. {rebuilt}"
        return f"Your answer is stored as a verified fact. {rebuilt}"

    def _rows_to_clarification_items(self, rows) -> List[Dict[str, Any]]:
        """Group the LEFT JOIN result (one row per item x link) into item dicts."""
        items: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        seen_links = set()

        for r in rows:
            q_id = str(r[self._C_ID])
            if q_id not in items:
                order.append(q_id)
                options = r[self._C_OPTIONS]
                if isinstance(options, (str, bytes)):
                    options = json.loads(options)
                answered_by = r[self._C_ANSWERED_BY]
                answered_at = r[self._C_ANSWERED_AT]
                items[q_id] = {
                    "id": q_id,
                    "project_id": str(r[self._C_PROJECT]),
                    "project_name": r[self._C_PROJECT_NAME],
                    "run_id": str(r[self._C_RUN]) if r[self._C_RUN] else None,
                    "question_key": r[self._C_KEY],
                    "question": r[self._C_QUESTION],
                    "reason": r[self._C_REASON],
                    "kind": r[self._C_KIND],
                    "assigned_role": r[self._C_ROLE],
                    "options": options or [],
                    "ai_suggestion": r[self._C_AI],
                    "status": r[self._C_STATUS],
                    "answer": r[self._C_ANSWER],
                    "answered_by": str(answered_by) if answered_by else None,
                    "answered_by_name": r[self._C_ANSWERER_NAME],
                    "answered_at": str(answered_at) if answered_at else None,
                    "fingerprint": r[self._C_FINGERPRINT],
                    "created_at": str(r[self._C_CREATED]),
                    "linked_rules": [],
                    "linked_steps": [],
                    "linked_evidence": [],
                }

            ttype = r[self._C_TARGET_TYPE]
            if not ttype:
                continue
            tid = str(r[self._C_TARGET_ID])
            if (q_id, ttype, tid) in seen_links:
                continue
            seen_links.add((q_id, ttype, tid))

            if ttype == "rule":
                items[q_id]["linked_rules"].append(tid)
            elif ttype == "step":
                items[q_id]["linked_steps"].append(tid)
            elif ttype == "evidence":
                # Structured source block, not a bare id: brief 7.12 item 4.
                items[q_id]["linked_evidence"].append({
                    "id": tid,
                    "evidence_key": r[self._C_EVIDENCE_KEY],
                    "quote": r[self._C_EVIDENCE_QUOTE],
                    "document_name": r[self._C_FILENAME],
                    "section_index": r[self._C_SECTION_INDEX],
                    "section_title": r[self._C_SECTION_TITLE],
                    "page_number": r[self._C_PAGE_NUMBER],
                })

        result = []
        for q_id in order:
            item = items[q_id]
            item["consequence_summary"] = self._consequence_summary(
                item["kind"], item["linked_rules"]
            )
            result.append(item)
        return result

    def get_clarification_item(self, q_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            ph = "%s" if self.use_postgres else "?"
            cur.execute(
                self._CLARIFICATION_SELECT + f" WHERE c.id = {ph}",
                (q_id,),
            )
            rows = cur.fetchall()
        items = self._rows_to_clarification_items(rows)
        return items[0] if items else None

    def list_project_clarification_items(self, project_id: str, role: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        ph = "%s" if self.use_postgres else "?"
        conditions = [f"c.project_id = {ph}"]
        params: List[Any] = [project_id]
        if role:
            conditions.append(f"c.assigned_role = {ph}")
            params.append(role)
        if status:
            conditions.append(f"c.status = {ph}")
            params.append(status)

        where_clause = " AND ".join(conditions)
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                self._CLARIFICATION_SELECT
                + f" WHERE {where_clause} ORDER BY c.created_at ASC, c.question_key ASC",
                tuple(params),
            )
            rows = cur.fetchall()
        return self._rows_to_clarification_items(rows)

    def list_waiting_questions_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Inbox query from Part 8.5: open questions assigned to my active role across all my projects.

        Same membership-and-role join as before; it now reuses the shared
        clarification projection so the inbox carries the full source context
        (quote, document, section, page) in one query instead of N+1.
        """
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                self._CLARIFICATION_SELECT
                + f"""
                JOIN project_members m ON m.project_id = c.project_id AND m.user_id = {ph}
                     AND m.role = c.assigned_role AND m.status = 'active'
                WHERE c.status IN ('open', 'stale')
                ORDER BY c.created_at ASC, c.question_key ASC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
        return self._rows_to_clarification_items(rows)

    def record_clarification_answer(self, q_id: str, answer_kind: str, answer_text: Optional[str], answered_by: str, role: str) -> Dict[str, Any]:
        """Record human answer in history, mark old answer superseded, update question status."""
        q = self.get_clarification_item(q_id)
        if not q:
            raise ValueError("Clarification item not found")

        answered_at = now_iso()
        ans_id = str(uuid.uuid4())
        new_status = "answered" if answer_kind == "answer" else "unknown"

        with self.get_connection() as conn:
            cur = conn.cursor()
            # Mark previous answers superseded
            if self.use_postgres:
                cur.execute("UPDATE clarification_answers SET superseded = TRUE WHERE clarification_id = %s", (q_id,))
                cur.execute("""
                    INSERT INTO clarification_answers (id, clarification_id, answer_kind, answer_text, answered_by, role, answered_at, superseded)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE);
                """, (ans_id, q_id, answer_kind, answer_text, answered_by, role, answered_at))
                cur.execute("""
                    UPDATE clarification_items
                    SET status = %s, answer = %s, answered_by = %s, answered_at = %s
                    WHERE id = %s;
                """, (new_status, answer_text, answered_by, answered_at, q_id))
            else:
                cur.execute("UPDATE clarification_answers SET superseded = 1 WHERE clarification_id = ?", (q_id,))
                cur.execute("""
                    INSERT INTO clarification_answers (id, clarification_id, answer_kind, answer_text, answered_by, role, answered_at, superseded)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0);
                """, (ans_id, q_id, answer_kind, answer_text, answered_by, role, answered_at))
                cur.execute("""
                    UPDATE clarification_items
                    SET status = ?, answer = ?, answered_by = ?, answered_at = ?
                    WHERE id = ?;
                """, (new_status, answer_text, answered_by, answered_at, q_id))
                conn.commit()

        # If answer provided, create verified_fact and handle conflict resolution
        if answer_kind == "answer" and answer_text:
            fact_key = self.mint_key(q["project_id"], "FACT")
            fact_id = str(uuid.uuid4())
            with self.get_connection() as conn:
                cur = conn.cursor()
                if self.use_postgres:
                    cur.execute("""
                        INSERT INTO verified_facts (id, project_id, fact_key, statement, clarification_id, confirmed_by, confirmed_at, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'active');
                    """, (fact_id, q["project_id"], fact_key, answer_text, q_id, answered_by, answered_at))
                else:
                    cur.execute("""
                        INSERT INTO verified_facts (id, project_id, fact_key, statement, clarification_id, confirmed_by, confirmed_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'active');
                    """, (fact_id, q["project_id"], fact_key, answer_text, q_id, answered_by, answered_at))
                    conn.commit()

            # Handle conflict resolution: mark selected rule confirmed, superseding other rules
            if q["kind"] == "conflicting_rules" and q["linked_rules"]:
                selected_rule_id = None
                other_rule_ids = []
                for rid in q["linked_rules"]:
                    r_item = self.get_business_rule(rid)
                    if r_item and (answer_text.lower() in r_item["description"].lower() or any(answer_text.lower() in q.lower() for q in r_item["evidence_quotes"])):
                        selected_rule_id = rid
                    else:
                        other_rule_ids.append(rid)

                if selected_rule_id:
                    self.update_rule_status(selected_rule_id, "approved", approved_by=answered_by)
                    for orid in other_rule_ids:
                        self.update_rule_status(orid, "superseded", approved_by=answered_by, supersedes_rule_id=selected_rule_id)
                elif other_rule_ids:
                    # If answer text is an override, confirm first rule with new description and supersede others
                    first_rid = other_rule_ids[0]
                    self.update_rule_status(first_rid, "approved", approved_by=answered_by)
                    for orid in other_rule_ids[1:]:
                        self.update_rule_status(orid, "superseded", approved_by=answered_by, supersedes_rule_id=first_rid)

            # Handle missing actor resolution: update process step
            if q["kind"] == "missing_actor" and q["linked_steps"]:
                for sid in q["linked_steps"]:
                    with self.get_connection() as conn:
                        cur = conn.cursor()
                        if self.use_postgres:
                            cur.execute("UPDATE process_steps SET actor = %s, unknowns = '[]' WHERE id = %s", (answer_text, sid))
                        else:
                            cur.execute("UPDATE process_steps SET actor = ?, unknowns = '[]' WHERE id = ?", (answer_text, sid))
                            conn.commit()

        self.log_audit_event(q["project_id"], "answer_recorded", actor=answered_by, subject=q["question_key"], details={"answer_kind": answer_kind, "answer_text": answer_text, "role": role})
        return self.get_clarification_item(q_id)

    def escalate_question(self, q_id: str, escalated_by: str, reason: str):
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("UPDATE clarification_items SET assigned_role = 'process_owner' WHERE id = %s RETURNING project_id;", (q_id,))
                pid = cur.fetchone()[0]
            else:
                cur.execute("SELECT project_id FROM clarification_items WHERE id = ?", (q_id,))
                pid = cur.fetchone()[0]
                cur.execute("UPDATE clarification_items SET assigned_role = 'process_owner' WHERE id = ?", (q_id,))
                conn.commit()

        self.log_audit_event(pid, "question_escalated", actor=escalated_by, subject=q_id, details={"reason": reason, "new_role": "process_owner"})

    # ----------------------------------------------------
    # Requirements & Links
    # ----------------------------------------------------
    def save_requirement(self, project_id: str, req_type: str, statement: str, title: Optional[str] = None, priority: str = "Must", acceptance_criteria: Optional[List[str]] = None, status: str = "draft", links: Optional[List[Tuple[str, str, str]]] = None) -> Dict[str, Any]:
        req_key = self.mint_key(project_id, "REQ")
        req_id = str(uuid.uuid4())
        created_at = now_iso()
        ac_str = json.dumps(acceptance_criteria or [])
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO requirements (id, project_id, requirement_key, type, title, statement, priority, acceptance_criteria, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (req_id, project_id, req_key, req_type, title, statement, priority, ac_str, status, created_at))
                if links:
                    for target_type, target_id, link_type in links:
                        cur.execute("INSERT INTO requirement_links (requirement_id, target_type, target_id, link_type) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING;", (req_id, target_type, target_id, link_type))
            else:
                cur.execute("""
                    INSERT INTO requirements (id, project_id, requirement_key, type, title, statement, priority, acceptance_criteria, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (req_id, project_id, req_key, req_type, title, statement, priority, ac_str, status, created_at))
                if links:
                    for target_type, target_id, link_type in links:
                        cur.execute("INSERT OR IGNORE INTO requirement_links (requirement_id, target_type, target_id, link_type) VALUES (?, ?, ?, ?);", (req_id, target_type, target_id, link_type))
                conn.commit()

        return self.get_requirement(req_id)

    def get_requirement(self, req_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM requirements WHERE id = ?" if not self.use_postgres else "SELECT * FROM requirements WHERE id = %s"
            cur.execute(query, (req_id,))
            r = cur.fetchone()
            if not r:
                return None
            res = {
                "id": str(r["id"] if not self.use_postgres else r[0]),
                "project_id": str(r["project_id"] if not self.use_postgres else r[1]),
                "requirement_key": r["requirement_key"] if not self.use_postgres else r[2],
                "type": r["type"] if not self.use_postgres else r[3],
                "title": r["title"] if not self.use_postgres else r[4],
                "statement": r["statement"] if not self.use_postgres else r[5],
                "priority": r["priority"] if not self.use_postgres else r[6],
                "acceptance_criteria": _jload(r["acceptance_criteria"] if not self.use_postgres else r[7]),
                "status": r["status"] if not self.use_postgres else r[8],
                "approved_by": str(r["approved_by"] if not self.use_postgres else r[9]) if (r["approved_by"] if not self.use_postgres else r[9]) else None,
                "created_at": str(r["created_at"] if not self.use_postgres else r[10]),
                "supporting_rule_keys": [],
                "supporting_evidence_keys": [],
                "supporting_step_keys": [],
                "supporting_fact_keys": []
            }
            # Fetch links
            l_query = "SELECT target_type, target_id FROM requirement_links WHERE requirement_id = ?" if not self.use_postgres else "SELECT target_type, target_id FROM requirement_links WHERE requirement_id = %s"
            cur.execute(l_query, (req_id,))
            for ttype, tid in cur.fetchall():
                if ttype == "rule":
                    cur.execute("SELECT rule_key FROM business_rules WHERE id = ?" if not self.use_postgres else "SELECT rule_key FROM business_rules WHERE id = %s", (tid,))
                    br = cur.fetchone()
                    if br: res["supporting_rule_keys"].append(br[0])
                elif ttype == "evidence":
                    cur.execute("SELECT evidence_key FROM evidence_items WHERE id = ?" if not self.use_postgres else "SELECT evidence_key FROM evidence_items WHERE id = %s", (tid,))
                    ev = cur.fetchone()
                    if ev: res["supporting_evidence_keys"].append(ev[0])
                elif ttype == "step":
                    cur.execute("SELECT step_key FROM process_steps WHERE id = ?" if not self.use_postgres else "SELECT step_key FROM process_steps WHERE id = %s", (tid,))
                    st = cur.fetchone()
                    if st: res["supporting_step_keys"].append(st[0])
                elif ttype == "verified_fact":
                    cur.execute("SELECT fact_key FROM verified_facts WHERE id = ?" if not self.use_postgres else "SELECT fact_key FROM verified_facts WHERE id = %s", (tid,))
                    vf = cur.fetchone()
                    if vf: res["supporting_fact_keys"].append(vf[0])

            return res

    def flag_requirement_needs_clarification(self, project_id: str, requirement_key: str) -> bool:
        """Mark an ungrounded requirement needs_clarification with the brief's wording.

        Brief Phase 2 step 13: items with unresolved questions are "shown as
        'Not stated in the source documents. Needs clarification.'" This is the
        deterministic repair applied by the bounded repair loop (SPEC-09-04);
        it never invents a supporting link to make a problem disappear.
        """
        note = "Not stated in the source documents. Needs clarification."
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""UPDATE requirements
                    SET status = 'needs_clarification',
                        statement = CASE WHEN statement LIKE {ph} THEN statement
                                         ELSE statement || {ph} END
                    WHERE project_id = {ph} AND requirement_key = {ph}""",
                (f"%{note}", f"\n\n{note}", project_id, requirement_key),
            )
            changed = cur.rowcount
            if not self.use_postgres:
                conn.commit()
        return bool(changed and changed > 0)

    def list_project_requirements(self, project_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT id FROM requirements WHERE project_id = ? ORDER BY requirement_key ASC" if not self.use_postgres else "SELECT id FROM requirements WHERE project_id = %s ORDER BY requirement_key ASC"
            cur.execute(query, (project_id,))
            rows = cur.fetchall()
            req_ids = [r[0] for r in rows]
        return [self.get_requirement(rid) for rid in req_ids if rid]

    # ----------------------------------------------------
    # Artifacts & Traceability
    # ----------------------------------------------------
    def save_artifact(self, project_id: str, artifact_type: str, markdown: str, content_json: Optional[Dict[str, Any]] = None, version: Optional[int] = None, status: str = "draft", created_by: Optional[str] = None) -> Dict[str, Any]:
        """Store a generated artifact without ever discarding a human approval.

        Finding F8: this upserted version 1 with `status = EXCLUDED.status`, so
        regenerating an artifact silently reset an approved document back to
        `draft` and threw the reviewer's approval away. Now:

          * regenerating over an approved (or rejected) artifact creates the NEXT
            version instead of overwriting it, so the approved version survives
            in full and the approval record still points at it;
          * an unapproved draft of the same version is still updated in place,
            which is what repeated generation inside one run should do.

        An explicit `version` is honoured as before (that is how a human edit
        saves itself as a new version).
        """
        created_at = now_iso()
        cj_str = json.dumps(content_json) if content_json else None

        if version is None:
            current = self.get_artifact_by_type(project_id, artifact_type)
            if current and (current.get("approved_by") or current.get("status") in ("approved", "rejected")):
                version = int(current.get("version", 1)) + 1
                logger.info(
                    f"{artifact_type} v{current.get('version')} is {current.get('status')}; "
                    f"writing v{version} instead of overwriting it."
                )
            else:
                version = int(current["version"]) if current else 1

        art_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO artifacts (id, project_id, artifact_type, version, content_json, markdown, status, created_by, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (project_id, artifact_type, version)
                    DO UPDATE SET content_json = EXCLUDED.content_json,
                                  markdown = EXCLUDED.markdown,
                                  status = EXCLUDED.status
                    WHERE artifacts.approved_by IS NULL
                      AND artifacts.status NOT IN ('approved', 'rejected');
                """, (art_id, project_id, artifact_type, version, cj_str, markdown, status, created_by, created_at))
            else:
                cur.execute(
                    "SELECT id, status, approved_by FROM artifacts "
                    "WHERE project_id = ? AND artifact_type = ? AND version = ?",
                    (project_id, artifact_type, version),
                )
                existing = cur.fetchone()
                if existing is None:
                    cur.execute("""
                        INSERT INTO artifacts (id, project_id, artifact_type, version, content_json, markdown, status, created_by, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (art_id, project_id, artifact_type, version, cj_str, markdown, status, created_by, created_at))
                elif existing["approved_by"] is None and existing["status"] not in ("approved", "rejected"):
                    cur.execute(
                        "UPDATE artifacts SET content_json = ?, markdown = ?, status = ? WHERE id = ?",
                        (cj_str, markdown, status, existing["id"]),
                    )
                # An approved or rejected row of this exact version is left alone.
                conn.commit()

        return self.get_artifact_by_type(project_id, artifact_type)

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM artifacts WHERE id = ?" if not self.use_postgres else "SELECT * FROM artifacts WHERE id = %s"
            cur.execute(query, (artifact_id,))
            r = cur.fetchone()
            if not r:
                return None
            return {
                "id": str(r["id"] if not self.use_postgres else r[0]),
                "project_id": str(r["project_id"] if not self.use_postgres else r[1]),
                "artifact_type": r["artifact_type"] if not self.use_postgres else r[2],
                "version": r["version"] if not self.use_postgres else r[3],
                "content_json": _jload(r["content_json"] if not self.use_postgres else r[4], None),
                "markdown": r["markdown"] if not self.use_postgres else r[5],
                "status": r["status"] if not self.use_postgres else r[6],
                "approved_by": str(r["approved_by"] if not self.use_postgres else r[7]) if (r["approved_by"] if not self.use_postgres else r[7]) else None,
                "created_by": str(r["created_by"] if not self.use_postgres else r[8]) if (r["created_by"] if not self.use_postgres else r[8]) else None,
                "created_at": str(r["created_at"] if not self.use_postgres else r[9])
            }

    def get_artifact_by_type(self, project_id: str, artifact_type: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM artifacts WHERE project_id = ? AND artifact_type = ? ORDER BY version DESC LIMIT 1" if not self.use_postgres else "SELECT * FROM artifacts WHERE project_id = %s AND artifact_type = %s ORDER BY version DESC LIMIT 1"
            cur.execute(query, (project_id, artifact_type))
            r = cur.fetchone()
            if not r:
                return None
            return {
                "id": str(r["id"] if not self.use_postgres else r[0]),
                "project_id": str(r["project_id"] if not self.use_postgres else r[1]),
                "artifact_type": r["artifact_type"] if not self.use_postgres else r[2],
                "version": r["version"] if not self.use_postgres else r[3],
                "content_json": _jload(r["content_json"] if not self.use_postgres else r[4], None),
                "markdown": r["markdown"] if not self.use_postgres else r[5],
                "status": r["status"] if not self.use_postgres else r[6],
                "approved_by": str(r["approved_by"] if not self.use_postgres else r[7]) if (r["approved_by"] if not self.use_postgres else r[7]) else None,
                "created_by": str(r["created_by"] if not self.use_postgres else r[8]) if (r["created_by"] if not self.use_postgres else r[8]) else None,
                "created_at": str(r["created_at"] if not self.use_postgres else r[9])
            }

    def list_project_artifacts(self, project_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT id FROM artifacts WHERE project_id = ? ORDER BY artifact_type ASC" if not self.use_postgres else "SELECT id FROM artifacts WHERE project_id = %s ORDER BY artifact_type ASC"
            cur.execute(query, (project_id,))
            rows = cur.fetchall()
            art_ids = [r[0] for r in rows]
        return [self.get_artifact(aid) for aid in art_ids if aid]

    def update_artifact_status(self, artifact_id: str, status: str, approved_by: Optional[str] = None):
        if status == "approved" and not approved_by:
            raise ValueError("Artifact approval constraint violation: approved_by cannot be null when status is 'approved'")
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("UPDATE artifacts SET status = %s, approved_by = %s WHERE id = %s", (status, approved_by, artifact_id))
            else:
                cur.execute("UPDATE artifacts SET status = ?, approved_by = ? WHERE id = ?", (status, approved_by, artifact_id))
                conn.commit()

    # ----------------------------------------------------
    # Test Cases
    # ----------------------------------------------------
    def save_test_case(self, project_id: str, requirement_id: str, scenario: str, expected_result: str, kind: str = "positive", steps: Optional[List[str]] = None, preconditions: Optional[str] = None) -> Dict[str, Any]:
        test_key = self.mint_key(project_id, "TEST")
        test_id = str(uuid.uuid4())
        created_at = now_iso()
        steps_str = json.dumps(steps or [])
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO test_cases (id, project_id, test_key, requirement_id, kind, scenario, preconditions, steps, expected_result, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (test_id, project_id, test_key, requirement_id, kind, scenario, preconditions, steps_str, expected_result, created_at))
            else:
                cur.execute("""
                    INSERT INTO test_cases (id, project_id, test_key, requirement_id, kind, scenario, preconditions, steps, expected_result, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (test_id, project_id, test_key, requirement_id, kind, scenario, preconditions, steps_str, expected_result, created_at))
                conn.commit()

        return {
            "id": test_id,
            "project_id": project_id,
            "test_key": test_key,
            "requirement_id": requirement_id,
            "kind": kind,
            "scenario": scenario,
            "preconditions": preconditions,
            "steps": steps or [],
            "expected_result": expected_result,
            "created_at": created_at
        }

    def list_project_test_cases(self, project_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    SELECT t.*, r.requirement_key
                    FROM test_cases t
                    JOIN requirements r ON r.id = t.requirement_id
                    WHERE t.project_id = %s
                    ORDER BY t.test_key ASC;
                """, (project_id,))
            else:
                cur.execute("""
                    SELECT t.*, r.requirement_key
                    FROM test_cases t
                    JOIN requirements r ON r.id = t.requirement_id
                    WHERE t.project_id = ?
                    ORDER BY t.test_key ASC;
                """, (project_id,))
            rows = cur.fetchall()
            return [{
                "id": str(r["id"] if not self.use_postgres else r[0]),
                "project_id": str(r["project_id"] if not self.use_postgres else r[1]),
                "test_key": r["test_key"] if not self.use_postgres else r[2],
                "requirement_id": str(r["requirement_id"] if not self.use_postgres else r[3]),
                "kind": r["kind"] if not self.use_postgres else r[4],
                "scenario": r["scenario"] if not self.use_postgres else r[5],
                "preconditions": r["preconditions"] if not self.use_postgres else r[6],
                "steps": _jload(r["steps"] if not self.use_postgres else r[7]),
                "expected_result": r["expected_result"] if not self.use_postgres else r[8],
                "created_at": str(r["created_at"] if not self.use_postgres else r[9]),
                "requirement_key": r["requirement_key"] if not self.use_postgres else r[10]
            } for r in rows]

    # ----------------------------------------------------
    # Runs & Agent Runs
    # ----------------------------------------------------
    def create_run(self, project_id: str, started_by: Optional[str] = None) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    INSERT INTO runs (id, project_id, status, current_node, created_at, updated_at, started_by)
                    VALUES (%s, %s, 'running', 'start', %s, %s, %s);
                """, (run_id, project_id, created_at, created_at, started_by))
                cur.execute("UPDATE projects SET status = 'in_progress', updated_at = %s WHERE id = %s", (created_at, project_id))
            else:
                cur.execute("""
                    INSERT INTO runs (id, project_id, status, current_node, created_at, updated_at, started_by)
                    VALUES (?, ?, 'running', 'start', ?, ?, ?);
                """, (run_id, project_id, created_at, created_at, started_by))
                cur.execute("UPDATE projects SET status = 'in_progress', updated_at = ? WHERE id = ?", (created_at, project_id))
                conn.commit()

        self.log_audit_event(project_id, "run_started", actor=started_by or "system", subject=run_id)
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM runs WHERE id = ?" if not self.use_postgres else "SELECT * FROM runs WHERE id = %s"
            cur.execute(query, (run_id,))
            r = cur.fetchone()
            if not r:
                return None
            run_data = {
                "id": str(r["id"] if not self.use_postgres else r[0]),
                "project_id": str(r["project_id"] if not self.use_postgres else r[1]),
                "status": r["status"] if not self.use_postgres else r[2],
                "current_node": r["current_node"] if not self.use_postgres else r[3],
                "state_json": _jload(r["state_json"] if not self.use_postgres else r[4], {}),
                "last_error": r["last_error"] if not self.use_postgres else r[5],
                "started_by": str(r["started_by"] if not self.use_postgres else r[6]) if (r["started_by"] if not self.use_postgres else r[6]) else None,
                "created_at": str(r["created_at"] if not self.use_postgres else r[7]),
                "updated_at": str(r["updated_at"] if not self.use_postgres else r[8])
            }
            node = run_data.get("current_node", "start")
            st = run_data.get("status", "running")
            node_progress_map = {
                "start": 5,
                "ingest": 15,
                "evidence": 30,
                "as_is": 45,
                "rules": 60,
                "gaps": 75,
                "waiting_for_human": 75,
                "gaps_recheck": 78,
                "to_be": 85,
                "redesign": 85,
                "waiting_for_to_be_approval": 88,
                "requirements": 90,
                "testing": 95,
                "quality": 98,
                "repair_1": 98,
                "repair_2": 98,
                "needs_review": 100,
                "completed": 100
            }
            if st == "completed":
                run_data["progress"] = 100
            elif st in ("failed", "cancelled"):
                run_data["progress"] = node_progress_map.get(node, 0)
            else:
                run_data["progress"] = node_progress_map.get(node, 10)
            run_data["stage"] = node
            return run_data

    def get_active_project_run(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT id FROM runs WHERE project_id = ? AND status = 'running' ORDER BY created_at DESC LIMIT 1" if not self.use_postgres else "SELECT id FROM runs WHERE project_id = %s AND status = 'running' ORDER BY created_at DESC LIMIT 1"
            cur.execute(query, (project_id,))
            r = cur.fetchone()
            if not r:
                return None
            return self.get_run(r[0])

    def update_run_state(self, run_id: str, status: str, current_node: Optional[str] = None, state_json: Optional[Dict[str, Any]] = None, last_error: Optional[str] = None):
        updated_at = now_iso()
        s_json = json.dumps(state_json, default=str) if state_json else None
        with self.get_connection() as conn:
            cur = conn.cursor()
            if self.use_postgres:
                cur.execute("""
                    UPDATE runs
                    SET status = %s, current_node = COALESCE(%s, current_node),
                        state_json = COALESCE(%s, state_json), last_error = %s, updated_at = %s
                    WHERE id = %s
                    RETURNING project_id;
                """, (status, current_node, s_json, last_error, updated_at, run_id))
                pid = cur.fetchone()[0]
                # Update project status if waiting or completed
                if status in ("waiting_for_human", "completed"):
                    cur.execute("UPDATE projects SET status = %s, updated_at = %s WHERE id = %s", (status, updated_at, pid))
            else:
                cur.execute("SELECT project_id FROM runs WHERE id = ?", (run_id,))
                pid = cur.fetchone()[0]
                cur.execute("""
                    UPDATE runs
                    SET status = ?, current_node = COALESCE(?, current_node),
                        state_json = COALESCE(?, state_json), last_error = ?, updated_at = ?
                    WHERE id = ?;
                """, (status, current_node, s_json, last_error, updated_at, run_id))
                if status in ("waiting_for_human", "completed"):
                    cur.execute("UPDATE projects SET status = ?, updated_at = ? WHERE id = ?", (status, updated_at, pid))
                conn.commit()

    def list_verified_facts(self, project_id: str) -> List[Dict[str, Any]]:
        """Human-confirmed facts for a project (brief 7.2)."""
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""SELECT id, fact_key, statement, clarification_id, confirmed_by,
                           confirmed_at, status
                    FROM verified_facts
                    WHERE project_id = {ph} AND status = 'active'
                    ORDER BY fact_key ASC""",
                (project_id,),
            )
            return [
                {
                    "id": str(r[0]),
                    "project_id": project_id,
                    "fact_key": r[1],
                    "statement": r[2],
                    "clarification_id": str(r[3]) if r[3] else None,
                    "confirmed_by": str(r[4]) if r[4] else None,
                    "confirmed_at": str(r[5]) if r[5] else None,
                    "status": r[6],
                }
                for r in cur.fetchall()
            ]

    # ----------------------------------------------------
    # Idempotent extraction support (brief Phase 0: "remember results already
    # stored so a re-run does not repeat calls for unchanged sections")
    # ----------------------------------------------------
    def sections_already_extracted(self, project_id: str, extractor_version: str) -> set:
        """Section ids that already hold evidence from this extractor version.

        A re-run skips these sections entirely: no model call, no duplicate rows.
        Bumping EXTRACTOR_VERSION makes every section eligible again.
        """
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT DISTINCT e.document_section_id
                FROM evidence_items e
                JOIN document_sections s ON s.id = e.document_section_id
                WHERE e.project_id = {ph} AND s.extracted_by = {ph}
                """,
                (project_id, extractor_version),
            )
            return {str(r[0]) for r in cur.fetchall()}

    def sections_already_mined_for_rules(self, project_id: str, extractor_version: str) -> set:
        """Section ids that already produced business rules from this extractor version."""
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT DISTINCT e.document_section_id
                FROM business_rules br
                JOIN rule_evidence re ON re.rule_id = br.id
                JOIN evidence_items e ON e.id = re.evidence_id
                JOIN document_sections s ON s.id = e.document_section_id
                WHERE br.project_id = {ph} AND s.extracted_by = {ph}
                """,
                (project_id, extractor_version),
            )
            return {str(r[0]) for r in cur.fetchall()}

    def mark_section_extracted(self, section_id: str, extractor_version: str) -> None:
        """Stamp a section with the extractor version that last mined it."""
        ph = "%s" if self.use_postgres else "?"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE document_sections SET extracted_by = {ph} WHERE id = {ph}",
                (extractor_version, section_id),
            )
            if not self.use_postgres:
                conn.commit()

    def list_project_evidence_for_sections(self, project_id: str, section_ids: List[str]) -> List[Dict[str, Any]]:
        """Existing evidence rows for the given sections, in the agent's own shape."""
        if not section_ids:
            return []
        wanted = {str(s) for s in section_ids}
        return [
            e for e in self.list_project_evidence(project_id)
            if str(e.get("document_section_id")) in wanted
        ]

    def mark_dependants_stale(self, project_id: str, reason: str) -> Dict[str, int]:
        """Mark generated work that depends on changed sources as needing review.

        Brief 3.5 ("User edits an approved rule or To-Be step -> create a new
        version and mark dependent artifacts stale") and 8.4. Approved rows are
        moved to 'stale'/'needs_review' so nothing stays silently approved on top
        of changed evidence; nothing is ever deleted.
        """
        ph = "%s" if self.use_postgres else "?"
        counts = {"artifacts": 0, "requirements": 0, "process_versions": 0}
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE artifacts SET status = 'stale' "
                f"WHERE project_id = {ph} AND status IN ('draft', 'needs_review', 'approved')",
                (project_id,),
            )
            counts["artifacts"] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
            cur.execute(
                f"UPDATE requirements SET status = 'needs_review' "
                f"WHERE project_id = {ph} AND status IN ('draft', 'approved')",
                (project_id,),
            )
            counts["requirements"] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
            cur.execute(
                f"UPDATE process_versions SET status = 'stale' "
                f"WHERE project_id = {ph} AND status IN ('draft', 'needs_review', 'approved')",
                (project_id,),
            )
            counts["process_versions"] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
            if not self.use_postgres:
                conn.commit()
        self.log_audit_event(
            project_id, "dependants_marked_stale", actor="system",
            subject=reason, details=counts,
        )
        return counts

    def reconcile_interrupted_runs(self) -> int:
        """Fail runs left mid-flight by a server restart (F14).

        Background execution lives in the API process, so a restart used to leave
        a run row stuck at 'running' for ever with nothing to advance it.
        """
        ph = "%s" if self.use_postgres else "?"
        reason = (
            "The server restarted while this analysis was running. "
            "Start the analysis again."
        )
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, project_id FROM runs WHERE status = 'running'")
            stuck = [(str(r[0]), str(r[1])) for r in cur.fetchall()]
            if stuck:
                cur.execute(
                    f"UPDATE runs SET status = 'failed', last_error = {ph}, updated_at = {ph} "
                    "WHERE status = 'running'",
                    (reason, now_iso()),
                )
                if not self.use_postgres:
                    conn.commit()
        for run_id, project_id in stuck:
            self.log_audit_event(
                project_id, "run_reconciled_after_restart", actor="system", subject=run_id,
            )
        return len(stuck)

    def get_latest_project_run(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT id FROM runs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1" if not self.use_postgres else "SELECT id FROM runs WHERE project_id = %s ORDER BY created_at DESC LIMIT 1"
            cur.execute(query, (project_id,))
            r = cur.fetchone()
            if not r:
                return None
            return self.get_run(r[0])

# Global instance
db = DatabaseRepository()