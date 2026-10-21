"""ProcessFoundry AI: Database Connection and Table Verification Script."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings

EXPECTED_TABLES = [
    "users", "projects", "project_members", "project_invitations", "project_counters",
    "documents", "document_sections", "document_chunks", "document_understanding",
    "evidence_items",
    "process_versions", "process_steps", "step_evidence", "step_transitions",
    "business_rules", "rule_evidence", "runs", "clarification_items",
    "clarification_links", "clarification_answers", "verified_facts",
    "requirements", "requirement_links", "artifacts", "artifact_links",
    "test_cases", "approvals", "agent_runs", "audit_events"
]

def check_database() -> bool:
    db_url = settings.database_url.strip()
    if not db_url:
        print("[DATABASE NOTICE] DATABASE_URL is empty in .env.")
        print("ProcessFoundry AI will run in local resilient storage mode (SQLite fallback).")
        print("To connect to PostgreSQL/Supabase, set DATABASE_URL in your .env file.")
        return True

    print(f"[CHECKING DATABASE] Connecting to: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    try:
        import psycopg
        with psycopg.connect(db_url, connect_timeout=20) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public';
                """)
                existing = {row[0] for row in cur.fetchall()}

        missing = [t for t in EXPECTED_TABLES if t not in existing]
        if missing:
            print(f"[WARNING] Database connected, but {len(missing)} of {len(EXPECTED_TABLES)} expected tables are missing:")
            for m in missing:
                print(f"  - {m}")
            print("\nPlease execute `schema.sql` in your Supabase SQL Editor or PostgreSQL instance.")
            return False

        print(f"[SUCCESS] All {len(EXPECTED_TABLES)} expected tables verified in PostgreSQL database.")
        return True
    except Exception as e:
        print(f"[ERROR] Could not connect to PostgreSQL database: {e}")
        print("Please check your DATABASE_URL, network connectivity, and credentials.")
        return False

if __name__ == "__main__":
    success = check_database()
    sys.exit(0 if success else 1)
