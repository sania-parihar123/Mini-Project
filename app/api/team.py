"""Team management, project membership, and invitations endpoints."""
import logging
import smtplib
from email.mime.text import MIMEText
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status

from app.schemas.projects import InvitationCreateRequest, InvitationResponse, ProjectMemberResponse
from app.schemas.clarification import ClarificationItemResponse
from app.repositories.database import db
from app.services.permissions import get_current_user, require_project_member, check_permission
from app.core.config import settings

logger = logging.getLogger("processfoundry.api.team")

router = APIRouter(prefix="/api", tags=["Team & Invitations"])

MAX_RESENDS_PER_INVITATION = 5      # brief 7.4
MAX_INVITATIONS_PER_PROJECT_PER_DAY = 20

def send_invitation_email(inviter_name: str, project_name: str, role: str, to_email: str) -> bool:
    """Send optional plain-text invitation email using smtplib over TLS (Part 7.4)."""
    if not settings.smtp_host:
        return False
    try:
        subject = f"{inviter_name} invited you to \"{project_name}\" on ProcessFoundry"
        body = (
            f"Hello,\n\n"
            f"{inviter_name} has invited you to join the process improvement project \"{project_name}\" as a {role}.\n\n"
            f"Create an account or sign in with this e-mail address to see the invitation on your dashboard.\n\n"
            f"Sign in at: {settings.app_base_url}\n\n"
            f"— The ProcessFoundry AI Team"
        )
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from or "no-reply@processfoundry.ai"
        msg["To"] = to_email

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as server:
            server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:
        # Brief 7.4: "Log the error without the password." The exception text is
        # logged; SMTP_PASSWORD is never included in it or in this message.
        logger.warning(
            "Invitation e-mail to %s could not be sent via %s:%s (%s: %s). "
            "The invitation itself was saved and still appears on the person's dashboard.",
            to_email, settings.smtp_host, settings.smtp_port,
            type(exc).__name__, str(exc).replace(settings.smtp_password or "\0", "***"),
        )
        return False

@router.post("/projects/{project_id}/invitations", response_model=InvitationResponse)
def invite_teammate(project_id: str, req: InvitationCreateRequest, user: dict = Depends(get_current_user)):
    p = db.get_project(project_id, user["id"])
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    my_role = require_project_member(project_id, user)
    is_creator = (p.get("created_by") == user["id"])
    check_permission("invite_member", my_role, is_creator=is_creator)

    target_email = req.email.strip().lower()
    if target_email == user["email"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot invite yourself.")

    # Check if target is already an active member
    members = db.list_project_members(project_id)
    if any(m["email"].lower() == target_email for m in members):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That person is already a member of this project.")

    # Check if duplicate pending invitation exists
    pending = db.list_project_invitations(project_id)
    if any(i["email"].lower() == target_email and i["status"] == "pending" for i in pending):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An invitation for that e-mail is already pending.")

    # Brief 7.4: at most 20 invitations per project per day.
    sent_today = db.count_invitations_created_today(project_id)
    if sent_today >= MAX_INVITATIONS_PER_PROJECT_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"This project has already created {sent_today} invitations today. "
                f"The daily limit is {MAX_INVITATIONS_PER_PROJECT_PER_DAY}. Try again tomorrow."
            ),
        )

    inv = db.create_invitation(project_id, target_email, req.role, user["id"])

    # Attempt to send email
    email_ok = send_invitation_email(user["display_name"], p["name"], req.role, target_email)
    if email_ok:
        with db.get_connection() as conn:
            cur = conn.cursor()
            if db.use_postgres:
                cur.execute("UPDATE project_invitations SET email_status = 'sent', email_sent_at = now() WHERE id = %s", (inv["id"],))
            else:
                cur.execute("UPDATE project_invitations SET email_status = 'sent', email_sent_at = datetime('now') WHERE id = ?", (inv["id"],))
                conn.commit()
        inv["email_status"] = "sent"

    return inv

@router.get("/projects/{project_id}/members", response_model=Dict[str, Any])
def get_project_team(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    members = db.list_project_members(project_id)
    invitations = db.list_project_invitations(project_id)
    return {
        "members": members,
        "invitations": [i for i in invitations if i["status"] == "pending"]
    }

@router.get("/me/invitations", response_model=List[InvitationResponse])
def get_my_invitations(user: dict = Depends(get_current_user)):
    return db.list_pending_invitations_for_email(user["email"])

@router.post("/invitations/{inv_id}/accept", response_model=InvitationResponse)
def accept_invitation(inv_id: str, user: dict = Depends(get_current_user)):
    inv = db.get_invitation(inv_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    if inv["email"].lower() != user["email"].lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only accept invitations sent to your exact email address.")

    if inv["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invitation is already {inv['status']}.")

    return db.accept_invitation(inv_id, user["id"])

@router.post("/invitations/{inv_id}/decline", status_code=status.HTTP_200_OK)
def decline_invitation(inv_id: str, user: dict = Depends(get_current_user)):
    inv = db.get_invitation(inv_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    if inv["email"].lower() != user["email"].lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    db.decline_invitation(inv_id, user["id"])
    return {"message": "Invitation declined."}

@router.post("/invitations/{inv_id}/resend", response_model=InvitationResponse)
def resend_invitation(inv_id: str, user: dict = Depends(get_current_user)):
    """Send the invitation e-mail again, within the limits in brief 7.4.

    At most 5 resends per invitation. Only people who may invite may resend.
    The dashboard invitation stays the source of truth either way.
    """
    inv = db.get_invitation(inv_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    p = db.get_project(inv["project_id"], user["id"])
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    my_role = require_project_member(inv["project_id"], user)
    is_creator = (p.get("created_by") == user["id"])
    check_permission("resend_invitation", my_role, is_creator=is_creator)

    if inv["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"That invitation is {inv['status']}, so there is nothing to resend.",
        )
    if int(inv.get("resend_count") or 0) >= MAX_RESENDS_PER_INVITATION:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"This invitation has already been resent {inv['resend_count']} times, "
                f"which is the limit of {MAX_RESENDS_PER_INVITATION}. Revoke it and "
                "invite the person again if the address was wrong."
            ),
        )

    email_ok = send_invitation_email(user["display_name"], p["name"], inv["role"], inv["email"])
    updated = db.record_invitation_resend(inv_id, email_ok)
    db.log_audit_event(
        inv["project_id"], "invitation_resent", actor=user["id"], subject=inv["email"],
        details={"email_status": "sent" if email_ok else "not_sent"},
    )
    return updated


@router.post("/invitations/{inv_id}/revoke", status_code=status.HTTP_200_OK)
def revoke_invitation(inv_id: str, user: dict = Depends(get_current_user)):
    inv = db.get_invitation(inv_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    p = db.get_project(inv["project_id"], user["id"])
    my_role = require_project_member(inv["project_id"], user)
    is_creator = (p.get("created_by") == user["id"])
    check_permission("revoke_invitation", my_role, is_creator=is_creator)

    db.revoke_invitation(inv_id, user["id"])
    return {"message": "Invitation revoked."}

@router.delete("/projects/{project_id}/members/{target_user_id}", status_code=status.HTTP_200_OK)
def remove_project_member(project_id: str, target_user_id: str, user: dict = Depends(get_current_user)):
    p = db.get_project(project_id, user["id"])
    my_role = require_project_member(project_id, user)
    is_creator = (p.get("created_by") == user["id"])
    check_permission("remove_member", my_role, is_creator=is_creator)

    db.remove_member(project_id, target_user_id)
    db.log_audit_event(project_id, "member_removed", actor=user["id"], subject=target_user_id)
    return {"message": "Member removed."}

@router.get("/me/questions", response_model=List[ClarificationItemResponse])
def get_waiting_for_me_questions(user: dict = Depends(get_current_user)):
    """Inbox of open questions assigned to current user's role across all active projects."""
    return db.list_waiting_questions_for_user(user["id"])
