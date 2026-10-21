"""Human-in-the-loop clarification question endpoints."""
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, status, Query

from app.schemas.clarification import ClarificationItemResponse, AnswerQuestionRequest, EscalateQuestionRequest
from app.repositories.database import db
from app.services.permissions import get_current_user, require_project_member, check_permission
from app.graph.build_graph import resume_run_after_clarification

router = APIRouter(prefix="/api", tags=["Questions"])

@router.get("/projects/{project_id}/questions", response_model=List[ClarificationItemResponse])
def list_project_questions(
    project_id: str,
    role: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    user: dict = Depends(get_current_user)
):
    require_project_member(project_id, user)
    return db.list_project_clarification_items(project_id, role=role, status=status_filter)

@router.post("/questions/{question_id}/answer", response_model=ClarificationItemResponse)
def answer_question(
    question_id: str,
    req: AnswerQuestionRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    q = db.get_clarification_item(question_id)
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")

    project_id = q["project_id"]
    my_role = require_project_member(project_id, user)

    # Deterministic role check: submitter's role must match assigned_role
    if my_role != q["assigned_role"]:
        role_label = q["assigned_role"].replace("_", " ").title()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only a {role_label} can answer this question."
        )

    if req.kind == "answer" and not (req.answer_text and req.answer_text.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answer text cannot be blank.")

    updated_q = db.record_clarification_answer(
        q_id=question_id,
        answer_kind=req.kind,
        answer_text=req.answer_text.strip() if req.answer_text else None,
        answered_by=user["id"],
        role=my_role
    )

    # Check if all critical questions are now resolved (brief 7.11 step 4).
    open_critical = [
        item for item in db.list_project_clarification_items(project_id, status="open")
        if item["kind"] in ("conflicting_rules", "missing_actor")
    ]

    # Resume the SAME run, in the background, re-entering after the gap step.
    # This used to call start_or_resume_project_run, which created a new run and
    # re-entered at `ingest`: the run then re-extracted everything, regenerated
    # the same gap as a new question and paused again for ever (finding F3), and
    # it blocked this request while doing so.
    if not open_critical:
        latest_run = db.get_latest_project_run(project_id)
        if latest_run and latest_run["status"] == "waiting_for_human":
            background_tasks.add_task(
                resume_run_after_clarification, latest_run["id"], project_id
            )

    return updated_q

@router.post("/questions/{question_id}/escalate", status_code=status.HTTP_200_OK)
def escalate_question(
    question_id: str,
    req: EscalateQuestionRequest,
    user: dict = Depends(get_current_user)
):
    q = db.get_clarification_item(question_id)
    if not q:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")

    my_role = require_project_member(q["project_id"], user)
    check_permission("escalate_question", my_role)

    db.escalate_question(question_id, user["id"], req.reason)
    return {"message": "Question successfully escalated to Process Owner."}
