"""Session-wide test isolation for ProcessFoundry AI.

Covers AC-TEST-01 (no test may reach a live database) and finding F2 of
REVIEW_REPORT.md: `pytest` on a machine with a populated `.env` used to write
rows into the production Supabase database, because

  * `app/core/config.py` loads `.env` through Pydantic Settings, so *unsetting*
    DATABASE_URL in the shell does not clear it, and
  * `tests/test_latency_benchmarks.py` had no database-isolation fixture and
    performed 24 write calls through `TestClient`, with no cleanup.

Everything in this module above the imports runs before any application module
is imported, which is the only point at which the module-level `settings` and
`db` singletons can still be redirected.
"""
import os
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Shut the door before the application can read anything real.
# ---------------------------------------------------------------------------
_TEST_TMP = Path(tempfile.mkdtemp(prefix="pfai-tests-"))

LIVE_DB_OPT_IN = "ALLOW_LIVE_DB_TESTS"
_OPTED_IN = os.environ.get(LIVE_DB_OPT_IN, "").strip().lower() in ("1", "true", "yes")

if not _OPTED_IN:
    # Ignore `.env` entirely: the process environment below is the only source.
    os.environ["PF_DISABLE_DOTENV"] = "1"
    # Explicitly empty, not merely unset, so no .env value can take its place.
    os.environ["DATABASE_URL"] = ""
os.environ["APP_ENV"] = "test"
os.environ["ALLOW_SQLITE"] = "true"
os.environ["PF_SQLITE_PATH"] = str(_TEST_TMP / "pfai_test.db")
os.environ["UPLOAD_DIR"] = str(_TEST_TMP / "uploads")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("SECRET_KEY", "pfai-test-only-signing-key-not-a-real-secret")

import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.repositories.database import db  # noqa: E402

class LiveDatabaseRefused(Exception):
    """Raised when the suite would be able to reach a non-temporary database."""


def check_no_live_database(database_url: str, use_postgres: bool, opted_in: bool) -> None:
    """Refuse to run when tests could reach a real database (AC-TEST-01).

    Kept as a pure function so it can be tested directly: in a normal run the
    environment block above has already forced isolation, which would otherwise
    make this guard unreachable dead code.
    """
    if opted_in:
        return
    if database_url.strip():
        raise LiveDatabaseRefused(
            "ProcessFoundry AI test suite refused to start: settings.database_url is "
            "not empty, so tests could write to a real database. Tests must run "
            f"against temporary SQLite. Set {LIVE_DB_OPT_IN}=1 only if you really "
            "intend to run against a throwaway database you are willing to lose."
        )
    if use_postgres:
        raise LiveDatabaseRefused(
            "ProcessFoundry AI test suite refused to start: the repository is in "
            "PostgreSQL mode. See tests/conftest.py."
        )


def pytest_configure(config):
    """Second line of defence: abort collection if isolation did not take effect."""
    try:
        check_no_live_database(settings.database_url, db.use_postgres, _OPTED_IN)
    except LiveDatabaseRefused as exc:
        raise pytest.UsageError(str(exc)) from exc


@pytest.fixture(scope="session", autouse=True)
def _forbid_postgres_connections():
    """Make any attempt to open a PostgreSQL pool a hard test failure (AC-TEST-01).

    This is the belt to `pytest_configure`'s braces: even if a test flipped
    `db.use_postgres` back on by hand, no socket can be opened.
    """
    import psycopg_pool

    real_pool = psycopg_pool.ConnectionPool

    class _ForbiddenConnectionPool:
        def __init__(self, *args, **kwargs):
            raise AssertionError(
                "A test tried to open a PostgreSQL connection pool. Tests must "
                "run against temporary SQLite only (see tests/conftest.py)."
            )

    psycopg_pool.ConnectionPool = _ForbiddenConnectionPool
    try:
        yield
    finally:
        psycopg_pool.ConnectionPool = real_pool


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Give every test its own empty SQLite database (AC-TEST-01).

    Autouse and unconditional, so a test file cannot forget it — which is
    exactly how `test_latency_benchmarks.py` came to use the live database.
    Per-test (not session) scope keeps tests independent of each other.
    """
    monkeypatch.setattr(db, "use_postgres", False)
    monkeypatch.setattr(db, "postgres_url", "")
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(db, "sqlite_path", str(tmp_path / "pfai_isolated.db"))
    monkeypatch.setattr(db, "_sqlite_ready_path", None)
    db._init_sqlite()
    yield db


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    """Keep uploaded test files out of the project's real uploads/ directory."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(settings, "upload_dir", str(upload_dir))
    yield upload_dir


@pytest.fixture(autouse=True)
def mock_llm_provider(monkeypatch):
    """Guarantee no test spends money or needs a network (SPEC-02-03)."""
    monkeypatch.setattr(settings, "llm_provider", "mock")
    from app.services.llm_service import llm_service
    monkeypatch.setattr(llm_service, "provider", "mock")
    monkeypatch.setattr(llm_service, "call_delay_seconds", 0.0, raising=False)
    yield
