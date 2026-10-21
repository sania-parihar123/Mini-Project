"""ProcessFoundry AI Configuration Settings."""
from pathlib import Path
import os

# ---------------------------------------------------------------------------
# .env loading control
#
# Pydantic Settings reads `.env` in addition to the process environment, so
# merely *unsetting* a shell variable does not stop a value in `.env` from
# being used. Automated tests must be able to guarantee that no real
# credential (above all DATABASE_URL) can leak in from a developer's `.env`.
#
# Setting PF_DISABLE_DOTENV=1 disables `.env` loading completely; the process
# environment then becomes the only source of configuration. `tests/conftest.py`
# sets this before importing any application module.
# ---------------------------------------------------------------------------
def dotenv_disabled() -> bool:
    return os.environ.get("PF_DISABLE_DOTENV", "").strip().lower() in ("1", "true", "yes")

_ENV_FILE = None if dotenv_disabled() else ".env"

# The signing key that must never be used: it used to be the hardcoded default
# in this file, so any deployment still carrying it is publicly forgeable.
RETIRED_DEFAULT_SECRET_KEY = "pfai_default_secret_key_8f3a9e2c1b7d4e5f6a0c8b9d"

try:
    from pydantic_settings import BaseSettings
    class Settings(BaseSettings):
        database_url: str = ""
        secret_key: str = ""
        llm_provider: str = "gemini"
        llm_api_key: str = ""
        llm_model: str = "gemini-2.5-flash"
        llm_timeout_seconds: int = 60
        llm_call_delay_seconds: float = 0.2
        llm_max_concurrent_calls: int = 2
        api_base_url: str = "http://localhost:8000"
        app_base_url: str = "http://localhost:8501"
        upload_dir: str = "uploads"
        max_upload_mb: int = 25
        smtp_host: str = ""
        smtp_port: int = 587
        smtp_user: str = ""
        smtp_password: str = ""
        smtp_from: str = "no-reply@processfoundry.ai"
        # Test-environment switches. Readable from .env as the README documents,
        # or from the process environment, which takes precedence.
        allow_sqlite: str = ""
        app_env: str = ""
        environment: str = ""

        class Config:
            env_file = _ENV_FILE
            env_file_encoding = "utf-8"
            extra = "ignore"
except ImportError:
    # Fallback to standard environment reader if pydantic_settings is not installed
    class Settings:
        def __init__(self):
            env_dict = {}
            if _ENV_FILE:
                env_path = Path(_ENV_FILE)
                if env_path.exists():
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            env_dict[k.strip().upper()] = v.strip()

            def get(name, default):
                # The process environment always wins over the .env file.
                if name in os.environ:
                    return os.environ[name]
                return env_dict.get(name, default)

            self.database_url = get("DATABASE_URL", "")
            self.secret_key = get("SECRET_KEY", "")
            self.llm_provider = get("LLM_PROVIDER", "gemini").lower()
            self.llm_api_key = get("LLM_API_KEY", "")
            self.llm_model = get("LLM_MODEL", "gemini-2.5-flash")
            self.llm_timeout_seconds = int(get("LLM_TIMEOUT_SECONDS", "60"))
            self.llm_call_delay_seconds = float(get("LLM_CALL_DELAY_SECONDS", "0.2"))
            self.llm_max_concurrent_calls = int(get("LLM_MAX_CONCURRENT_CALLS", "2"))
            self.api_base_url = get("API_BASE_URL", "http://localhost:8000")
            self.app_base_url = get("APP_BASE_URL", "http://localhost:8501")
            self.upload_dir = get("UPLOAD_DIR", "uploads")
            self.max_upload_mb = int(get("MAX_UPLOAD_MB", "25"))
            self.smtp_host = get("SMTP_HOST", "")
            self.smtp_port = int(get("SMTP_PORT", "587"))
            self.smtp_user = get("SMTP_USER", "")
            self.smtp_password = get("SMTP_PASSWORD", "")
            self.smtp_from = get("SMTP_FROM", "no-reply@processfoundry.ai")
            self.allow_sqlite = get("ALLOW_SQLITE", "")
            self.app_env = get("APP_ENV", "")
            self.environment = get("ENVIRONMENT", "")

settings = Settings()


def is_test_environment() -> bool:
    """True when the process is an automated test run or an explicit offline dev run.

    This is the single definition used by the database guard (SQLite fallback)
    and the LLM guard (mock provider), so the two cannot drift apart. Both the
    process environment and `.env` are honoured, which is what the README
    documents; the process environment wins because Pydantic prefers it.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True

    def flag(name: str) -> str:
        if name in os.environ:
            return os.environ[name].strip().lower()
        return str(getattr(settings, name.lower(), "") or "").strip().lower()

    if flag("ENVIRONMENT") in ("test", "testing"):
        return True
    if flag("APP_ENV") in ("test", "testing"):
        return True
    if flag("ALLOW_SQLITE") in ("true", "1", "yes"):
        return True
    return False


def validate_security_configuration() -> None:
    """Fail fast on a signing key that cannot be trusted (finding F7).

    The old default, `pfai_default_secret_key_...`, was hardcoded in this file,
    so any deployment still using it signs session tokens with a key that is
    public: anyone with the source could mint a token for any user id. There is
    now no default at all, and this check refuses to start without a real one.
    """
    key = (settings.secret_key or "").strip()
    if not key:
        raise RuntimeError(
            "ProcessFoundry AI Configuration Error: SECRET_KEY is not set. "
            "It signs sign-in tokens, so the application will not start without "
            "it. Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\" "
            "and put it in .env as SECRET_KEY=..."
        )
    if key == RETIRED_DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "ProcessFoundry AI Configuration Error: SECRET_KEY is still the old "
            "hardcoded default, which is published in the source history and can "
            "be used to forge a session for any account. Replace it with a fresh "
            "random value."
        )
    if len(key) < 16:
        raise RuntimeError(
            "ProcessFoundry AI Configuration Error: SECRET_KEY is too short "
            f"({len(key)} characters). Use at least 16, ideally 32 or more."
        )
