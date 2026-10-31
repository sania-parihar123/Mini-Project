"""FastAPI router for Interactive Prototype (08) endpoints."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.repositories.database import db
from app.schemas.prototypes import PrototypeSpecResponse, PrototypeSpecVersionSummary
from app.services.permissions import get_current_user, require_project_member
from app.services.prototype_builder import PrototypeBuildError, build_prototype_spec
from app.services.prototype_renderer import render_full_prototype

router = APIRouter(prefix="/api", tags=["Prototypes"])


@router.get(
    "/projects/{project_id}/prototype",
    response_model=PrototypeSpecResponse,
    status_code=status.HTTP_200_OK,
)
def get_latest_prototype(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Retrieve the latest interactive prototype specification for the project."""
    require_project_member(project_id, user)
    spec_row = db.get_latest_prototype_spec(project_id)
    if not spec_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interactive prototype has been generated for this project yet. Please generate one first.",
        )
    return spec_row


@router.post(
    "/projects/{project_id}/prototype/generate",
    response_model=PrototypeSpecResponse,
    status_code=status.HTTP_200_OK,
)
def generate_prototype(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """(Re)generate the interactive prototype specification from current project state."""
    my_role = require_project_member(project_id, user)
    if my_role not in ("analyst", "process_owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an Analyst or Process Owner can generate or update the interactive prototype.",
        )

    try:
        spec = build_prototype_spec(project_id, user_id=user["id"])
    except PrototypeBuildError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    spec_row = db.get_latest_prototype_spec(project_id)
    if not spec_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve saved prototype specification.",
        )
    return spec_row


@router.get(
    "/projects/{project_id}/prototype/html",
    response_class=Response,
    status_code=status.HTTP_200_OK,
)
def get_prototype_html(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Return the rendered self-contained HTML interactive prototype for viewing or downloading."""
    require_project_member(project_id, user)
    spec_row = db.get_latest_prototype_spec(project_id)
    if not spec_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No interactive prototype has been generated for this project yet.",
        )

    rendered_html = render_full_prototype(spec_row["spec_json"])
    return Response(content=rendered_html, media_type="text/html")


@router.get(
    "/projects/{project_id}/prototype/versions",
    response_model=List[PrototypeSpecVersionSummary],
    status_code=status.HTTP_200_OK,
)
def list_prototype_versions(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """List historical prototype specification versions (newest first)."""
    require_project_member(project_id, user)
    return db.list_prototype_spec_versions(project_id)
