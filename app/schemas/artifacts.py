"""Artifacts and specifications Pydantic models."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

class ArtifactResponse(BaseModel):
    id: str
    project_id: str
    artifact_type: str
    version: int
    content_json: Optional[Dict[str, Any]] = None
    markdown: Optional[str] = None
    status: str
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None

class ArtifactUpdateRequest(BaseModel):
    markdown: str

class ApprovalDecisionRequest(BaseModel):
    decision: str  # "approve", "request_changes", "reject"
    comment: Optional[str] = None
