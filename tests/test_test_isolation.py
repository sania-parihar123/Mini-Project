"""Tests that the test suite itself cannot reach a live database.

Covers AC-TEST-01 (SPEC-01-06). Finding F2 of REVIEW_REPORT.md: running
`pytest` on a developer machine with a populated `.env` wrote rows into the
production Supabase database.
"""
import os

import psycopg_pool
import pytest

from app.core.config import Settings, dotenv_disabled, is_test_environment
from app.repositories.database import db


def test_dotenv_is_disabled_during_tests():
    """AC-TEST-01: `.env` must not be read while tests run, so no real credential loads."""
    assert os.environ.get("PF_DISABLE_DOTENV") == "1"
    assert dotenv_disabled() is True


def test_settings_cannot_see_a_database_url_from_dotenv():
    """AC-TEST-01: a freshly constructed Settings must still have an empty DATABASE_URL.

    This is the specific hole that caused F2: `env -u DATABASE_URL` did not stop
    Pydantic Settings from reading the value out of `.env`.

    Covers SPEC-01-06.
    """
    fresh = Settings()
    assert fresh.database_url.strip() == "", (
        "Settings picked up a DATABASE_URL despite PF_DISABLE_DOTENV=1; "
        "tests could reach a real database."
    )


def test_repository_is_in_sqlite_mode_with_a_temporary_path(tmp_path):
    """AC-TEST-01: the shared repository singleton runs on throwaway SQLite.

    Covers SPEC-01-06.
    """
    assert db.use_postgres is False
    assert db.postgres_url == ""
    # The autouse isolated_database fixture points it inside pytest's tmp_path.
    assert "pfai_isolated.db" in db.sqlite_path


def test_guard_refuses_a_non_empty_database_url_without_opt_in():
    """AC-TEST-01: the suite aborts rather than run against a configured database."""
    from conftest import LiveDatabaseRefused, check_no_live_database

    with pytest.raises(LiveDatabaseRefused, match="refused to start"):
        check_no_live_database(
            "postgresql://user:pw@aws-0-ap-northeast-1.pooler.example.com:5432/postgres",
            use_postgres=True,
            opted_in=False,
        )


def test_guard_refuses_postgres_mode_without_opt_in():
    """AC-TEST-01: PostgreSQL mode alone is enough to abort, even with no URL."""
    from conftest import LiveDatabaseRefused, check_no_live_database

    with pytest.raises(LiveDatabaseRefused, match="PostgreSQL mode"):
        check_no_live_database("", use_postgres=True, opted_in=False)


def test_guard_allows_the_isolated_configuration():
    """AC-TEST-01: an empty URL in SQLite mode is the only configuration allowed by default."""
    from conftest import check_no_live_database

    assert check_no_live_database("", use_postgres=False, opted_in=False) is None


def test_guard_can_be_overridden_only_by_explicit_opt_in():
    """AC-TEST-01: ALLOW_LIVE_DB_TESTS=1 is the single documented escape hatch."""
    from conftest import check_no_live_database

    assert check_no_live_database(
        "postgresql://user:pw@localhost:5432/throwaway", use_postgres=True, opted_in=True
    ) is None


def test_opening_a_postgres_pool_is_blocked(tmp_path):
    """AC-TEST-01: even a direct attempt to open a PostgreSQL pool must fail loudly."""
    with pytest.raises(AssertionError, match="tried to open a PostgreSQL connection pool"):
        psycopg_pool.ConnectionPool(conninfo="postgresql://user:pw@example.invalid:5432/db")


def test_init_pool_never_opens_postgres_during_tests(monkeypatch):
    """AC-TEST-01: db.init_pool() in PostgreSQL mode is stopped by the guard, not by luck."""
    monkeypatch.setattr(db, "use_postgres", True)
    monkeypatch.setattr(db, "postgres_url", "postgresql://user:pw@example.invalid:5432/db")
    monkeypatch.setattr(db, "_pool", None)
    with pytest.raises(RuntimeError) as exc:
        db.init_pool()
    assert "tried to open a PostgreSQL connection pool" in str(exc.value)


def test_uploads_are_redirected_away_from_the_project(isolated_uploads):
    """AC-TEST-01: test uploads must not land in the project's real uploads/ directory."""
    from app.core.config import settings
    assert str(isolated_uploads) == settings.upload_dir
    assert "uploads" in settings.upload_dir
    assert os.path.isdir(settings.upload_dir)


def test_is_test_environment_detects_this_run():
    """SPEC-01-06: the shared test-environment predicate must recognise a pytest run."""
    assert is_test_environment() is True


def test_importing_the_repository_does_not_create_the_default_database():
    """F14: importing app.repositories.database used to create data/processfoundry.db.

    The schema is now created lazily, so a bare import has no filesystem effect.
    """
    from app.repositories.database import DatabaseRepository
    repo = DatabaseRepository(db_path="/tmp/pfai-never-created-by-import.db")
    assert repo._sqlite_ready_path is None
    assert not os.path.exists("/tmp/pfai-never-created-by-import.db")
