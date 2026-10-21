"""Execution run orchestration endpoints."""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, status

from app.repositories.database import db
from app.services.permissions import get_current_user, require_project_member, check_permission
from app.graph.build_graph import execute_project_run_background

router = APIRouter(prefix="/api", tags=["Runs"])

@router.post("/projects/{project_id}/runs", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
def trigger_analysis_run(
    project_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    my_role = require_project_member(project_id, user)
    check_permission("start_run", my_role)

    docs = db.list_project_documents(project_id)
    if not docs or not any(d["parse_status"] == "parsed" for d in docs):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No source documents have been uploaded and parsed. Please upload at least one document before starting analysis."
        )

    # Return existing running run to prevent duplicate executions
    active_run = db.get_active_project_run(project_id)
    if active_run:
        return active_run

    run = db.create_run(project_id, started_by=user["id"])
    background_tasks.add_task(execute_project_run_background, run["id"], project_id, user["id"])
    return db.get_run(run["id"])

@router.get("/runs/{run_id}", response_model=Dict[str, Any])
def get_run_status(run_id: str, user: dict = Depends(get_current_user)):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    require_project_member(run["project_id"], user)
    return run

@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_run(run_id: str, user: dict = Depends(get_current_user)):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    my_role = require_project_member(run["project_id"], user)
    check_permission("cancel_run", my_role)

    db.update_run_state(run_id, status="cancelled")
    db.log_audit_event(run["project_id"], "run_cancelled", actor=user["id"], subject=run_id)
    return {"message": "Run cancelled."}
