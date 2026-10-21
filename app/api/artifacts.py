"""Artifacts, specification documents, and decision endpoints."""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, status, Response

from app.schemas.artifacts import ArtifactResponse, ArtifactUpdateRequest, ApprovalDecisionRequest
from app.repositories.database import db
from app.services.permissions import get_current_user, require_project_member, check_permission
from app.graph.build_graph import resume_run_after_to_be_approval

router = APIRouter(prefix="/api", tags=["Artifacts"])

@router.get("/projects/{project_id}/artifacts", response_model=List[ArtifactResponse])
def list_project_artifacts(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    return db.list_project_artifacts(project_id)

@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def get_artifact(artifact_id: str, user: dict = Depends(get_current_user)):
    art = db.get_artifact(artifact_id)
    if not art:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")
    require_project_member(art["project_id"], user)
    return art

@router.patch("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def update_artifact_markdown(
    artifact_id: str,
    req: ArtifactUpdateRequest,
    user: dict = Depends(get_current_user)
):
    art = db.get_artifact(artifact_id)
    if not art:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")
    my_role = require_project_member(art["project_id"], user)
    check_permission("edit_content", my_role)

    new_version = art["version"] + 1
    updated = db.save_artifact(
        project_id=art["project_id"],
        artifact_type=art["artifact_type"],
        markdown=req.markdown,
        content_json=art.get("content_json"),
        version=new_version,
        status="draft",
        created_by=user["id"]
    )
    db.log_audit_event(art["project_id"], "artifact_updated", actor=user["id"], subject=art["artifact_type"], details={"version": new_version})
    return updated

@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, user: dict = Depends(get_current_user)):
    art = db.get_artifact(artifact_id)
    if not art:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")
    require_project_member(art["project_id"], user)

    md_content = art.get("markdown") or ""
    filename = f"{art['artifact_type']}_v{art['version']}.md"
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/process-versions/{version_id}/decision", status_code=status.HTTP_200_OK)
def decide_process_version(
    version_id: str,
    req: ApprovalDecisionRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    pv = None
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT project_id FROM process_versions WHERE id = ?" if not db.use_postgres else "SELECT project_id FROM process_versions WHERE id = %s", (version_id,))
        row = cur.fetchone()
        if row:
            pv = {"project_id": row[0]}

    if not pv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Process version not found.")

    my_role = require_project_member(pv["project_id"], user)
    check_permission("approve_to_be", my_role)

    try:
        db.update_process_version_decision(
            pv_id=version_id,
            decision=req.decision,
            reviewer_id=user["id"],
            reviewer_role=my_role,
            comment=req.comment
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    # Brief 3.5 and 7.11 step 5: only after a human approves the To-Be may the
    # downstream documents be generated. The run is waiting at that gate, so
    # continue it in the background and let the UI poll.
    resumed = False
    if req.decision == "approve":
        latest_run = db.get_latest_project_run(pv["project_id"])
        if latest_run and latest_run["status"] == "waiting_for_human":
            background_tasks.add_task(
                resume_run_after_to_be_approval, latest_run["id"], pv["project_id"]
            )
            resumed = True

    return {
        "message": f"Process version decision '{req.decision}' recorded successfully.",
        "downstream_generation_started": resumed,
    }

@router.post("/artifacts/{artifact_id}/decision", status_code=status.HTTP_200_OK)
def decide_artifact(
    artifact_id: str,
    req: ApprovalDecisionRequest,
    user: dict = Depends(get_current_user)
):
    art = db.get_artifact(artifact_id)
    if not art:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")

    my_role = require_project_member(art["project_id"], user)
    check_permission("approve_artifact", my_role, artifact_type=art["artifact_type"])

    if req.decision != "approve" and (not req.comment or not req.comment.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment is required when rejecting or requesting changes.")

    new_status = "approved" if req.decision == "approve" else ("rejected" if req.decision == "reject" else "needs_review")
    approver = user["id"] if req.decision == "approve" else None
    db.update_artifact_status(artifact_id, new_status, approved_by=approver)
    db.log_audit_event(art["project_id"], "artifact_decision", actor=user["id"], subject=art["artifact_type"], details={"decision": req.decision, "comment": req.comment})
    return {"message": f"Artifact decision '{req.decision}' recorded."}
