"""Process modeling (As-Is & To-Be) Pydantic models."""
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

AutomationType = Literal["deterministic", "ai_assisted", "human", "hybrid"]

class ProcessStepInput(BaseModel):
    name: str = Field(..., description="Action name of the step")
    actor: Optional[str] = Field(None, description="Role performing the step, or None if unknown/unnamed")
    step_type: str = Field("task", description="Type of step e.g. form_submission, review, notification")
    sequence: int = Field(1, description="Sequential order")
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    automation: Optional[AutomationType] = None
    human_approval_required: bool = False
    supporting_evidence_quotes: List[str] = Field(default_factory=list)

class AsIsDiscoveryOutput(BaseModel):
    process_name: str
    steps: List[ProcessStepInput] = []
    overall_unknowns: List[str] = []

class ToBeRedesignOutput(BaseModel):
    process_name: str
    summary_of_changes: str
    steps: List[ProcessStepInput] = []

class ProcessStepResponse(BaseModel):
    id: str
    process_version_id: str
    step_key: str
    name: str
    actor: Optional[str] = None
    step_type: str
    sequence: int
    inputs: List[str] = []
    outputs: List[str] = []
    unknowns: List[str] = []
    automation: Optional[str] = None
    human_approval_required: bool = False
    evidence_keys: List[str] = []

class ProcessVersionResponse(BaseModel):
    id: str
    project_id: str
    version: int
    as_is_json: Optional[Dict[str, Any]] = None
    to_be_json: Optional[Dict[str, Any]] = None
    status: str
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    steps: List[ProcessStepResponse] = []
