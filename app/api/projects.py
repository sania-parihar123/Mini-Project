"""Project management and audit endpoints."""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status

from app.schemas.projects import ProjectCreateRequest, ProjectResponse
from app.repositories.database import db
from app.services.permissions import get_current_user, require_project_member, check_permission

router = APIRouter(prefix="/api", tags=["Projects"])

@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(req: ProjectCreateRequest, user: dict = Depends(get_current_user)):
    p = db.create_project(
        name=req.name,
        user_id=user["id"],
        role=req.role,
        process_type=req.process_type or "general",
        description=req.description or "",
        department=req.department or "",
        goals=req.goals or "",
        constraints=req.constraints or ""
    )
    return p

@router.get("/projects", response_model=List[ProjectResponse])
def list_my_projects(user: dict = Depends(get_current_user)):
    return db.list_user_projects(user["id"])

@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project_details(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    p = db.get_project(project_id, user["id"])
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return p

@router.delete("/projects/{project_id}", status_code=status.HTTP_200_OK)
def delete_project_endpoint(project_id: str, user: dict = Depends(get_current_user)):
    p = db.get_project(project_id, user["id"])
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    my_role = require_project_member(project_id, user)
    is_creator = (p.get("created_by") == user["id"])
    check_permission("delete_project", my_role, is_creator=is_creator)

    result = db.delete_project(project_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    return {
        "message": f"Project '{p['name']}' and all its associated data have been permanently deleted.",
        "project_id": project_id
    }

@router.get("/projects/{project_id}/audit", response_model=List[Dict[str, Any]])
def get_project_audit_log(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    return db.list_audit_events(project_id)
