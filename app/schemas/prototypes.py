"""Pydantic schemas for the Interactive Prototype feature (08)."""
from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field


class PrototypeField(BaseModel):
    name: str
    field_type: Literal["text", "date", "file", "select", "number", "textarea"]
    options: List[str] = Field(default_factory=list)
    required: bool = True
    hint: Optional[str] = None


class PrototypeScreen(BaseModel):
    screen_id: str
    title: str
    actor: Optional[str] = None
    automation: Optional[str] = None
    human_approval_required: bool = False
    fields: List[PrototypeField] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    business_rule_keys: List[str] = Field(default_factory=list)
    requirement_keys: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)


class PrototypeSpec(BaseModel):
    project_id: str
    process_name: str
    actors: List[str] = Field(default_factory=list)
    screens: List[PrototypeScreen] = Field(default_factory=list)
    business_rules: List[Dict[str, Any]] = Field(default_factory=list)
    missing_info_notices: List[str] = Field(default_factory=list)
    generated_from_workflow_version: int = 1
    spec_fingerprint: str
    created_at: str


class PrototypeSpecResponse(BaseModel):
    id: str
    project_id: str
    spec_fingerprint: str
    spec_json: PrototypeSpec
    spec_version: int
    generated_by: Optional[str] = None
    created_at: str


class PrototypeSpecVersionSummary(BaseModel):
    id: str
    project_id: str
    spec_fingerprint: str
    spec_version: int
    generated_by: Optional[str] = None
    created_at: str
