"""Requirements engineering Pydantic models."""
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field

RequirementType = Literal["business", "functional", "non_functional", "workflow"]
PriorityType = Literal["Must", "Should", "Could", "Wont"]

class RequirementResponse(BaseModel):
    id: str
    project_id: str
    requirement_key: str
    type: RequirementType
    title: Optional[str] = None
    statement: str
    priority: Optional[PriorityType] = "Must"
    acceptance_criteria: List[str] = []
    status: str
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    supporting_rule_keys: List[str] = []
    supporting_evidence_keys: List[str] = []
    supporting_step_keys: List[str] = []
    supporting_fact_keys: List[str] = []
