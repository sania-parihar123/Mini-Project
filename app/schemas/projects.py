"""Project and team membership Pydantic models."""
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field

RoleType = Literal["process_owner", "analyst", "technical_reviewer"]
ProjectStatus = Literal["created", "in_progress", "waiting_for_human", "completed", "archived"]

class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    process_type: Optional[str] = "general"
    description: Optional[str] = ""
    department: Optional[str] = ""
    goals: Optional[str] = ""
    constraints: Optional[str] = ""
    role: RoleType = "analyst"  # Role the creator assigns to themselves

class ProjectResponse(BaseModel):
    id: str
    name: str
    process_type: Optional[str] = "general"
    description: Optional[str] = ""
    department: Optional[str] = ""
    goals: Optional[str] = ""
    constraints: Optional[str] = ""
    stakeholders: List[dict] = []
    status: ProjectStatus = "created"
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    my_role: Optional[str] = None
    members_count: int = 1
    waiting_count: int = 0

class ProjectMemberResponse(BaseModel):
    project_id: str
    user_id: str
    display_name: str
    email: str
    role: RoleType
    status: str
    created_at: Optional[datetime] = None

class InvitationCreateRequest(BaseModel):
    email: str
    role: RoleType

class InvitationResponse(BaseModel):
    id: str
    project_id: str
    project_name: Optional[str] = None
    email: str
    role: RoleType
    status: str
    invited_by: str
    inviter_name: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    email_status: str = "not_sent"
    resend_count: int = 0
