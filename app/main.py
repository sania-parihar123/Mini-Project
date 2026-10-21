"""ProcessFoundry AI: FastAPI Backend Application Entrypoint."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from app.core.config import settings, validate_security_configuration
from app.repositories.database import db
from app.services.llm_service import llm_service

from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.documents import router as documents_router
from app.api.runs import router as runs_router
from app.api.questions import router as questions_router
from app.api.artifacts import router as artifacts_router
from app.api.team import router as team_router
from app.api.traceability import router as traceability_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate database configuration and initialize connection pool
    # Refuse to start without a trustworthy signing key (finding F7).
    try:
        validate_security_configuration()
    except Exception as e:
        logging.error(str(e))
        raise

    # Refuse to serve a configuration that would fabricate content (finding F5).
    try:
        llm_service.validate_configuration()
        logging.info(f"LLM gateway configured: provider={llm_service.provider}")
    except Exception as e:
        logging.error(f"LLM configuration invalid: {e}")
        raise

    try:
        db.init_pool()
        logging.info("ProcessFoundry AI database connection pool initialized.")
    except Exception as e:
        logging.error(f"Database initialization failed during startup: {e}")
        raise

    # Background runs live in this process, so a restart leaves any in-flight run
    # stuck at 'running' with nothing left to advance it (finding F14). Fail them
    # with a clear reason so the UI stops showing a spinner for ever.
    try:
        reconciled = db.reconcile_interrupted_runs()
        if reconciled:
            logging.warning(
                f"Marked {reconciled} analysis run(s) as failed: they were interrupted "
                "by a server restart."
            )
    except Exception as e:
        logging.error(f"Could not reconcile interrupted runs: {e}")

    yield
    # Shutdown: cleanly close connection pool
    logging.info("Closing ProcessFoundry AI database connection pool...")
    db.close_pool()

app = FastAPI(
    title="ProcessFoundry AI API",
    description="Enterprise Process Discovery, Redesign and Specification Platform",
    version="0.1.0",
    lifespan=lifespan
)

# CORS is limited to the app's own front end (finding F14). allow_origins=["*"]
# with allow_credentials=True let any site on the internet call this API from a
# visitor's browser and defeated origin-based defence in depth.
def _allowed_origins() -> list:
    origins = {settings.app_base_url.rstrip("/")}
    # The dev front end is reachable under both hostnames.
    if "localhost" in settings.app_base_url:
        origins.add(settings.app_base_url.replace("localhost", "127.0.0.1").rstrip("/"))
    if "127.0.0.1" in settings.app_base_url:
        origins.add(settings.app_base_url.replace("127.0.0.1", "localhost").rstrip("/"))
    return sorted(o for o in origins if o)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Mount all feature routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(documents_router)
app.include_router(runs_router)
app.include_router(questions_router)
app.include_router(artifacts_router)
app.include_router(team_router)
app.include_router(traceability_router)

@app.get("/api/health")
def health_check():
    """Service health, plus whether model output is real or invented.

    `model_is_mock` lets the UI show a standing warning when the configured
    provider fabricates content instead of reading documents (finding F5).
    """
    return {
        "status": "ok",
        "service": "ProcessFoundry AI",
        "version": "0.1.0",
        "llm_provider": llm_service.provider,
        "model_is_mock": llm_service.is_mock(),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
