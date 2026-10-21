"""Business rule Pydantic models."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class ExtractedRuleItem(BaseModel):
    description: str = Field(..., description="Clear textual description of the business rule")
    condition: str = Field(..., description="Condition statement triggering the rule")
    outcome: str = Field(..., description="Required outcome or restriction")
    exceptions: List[str] = Field(default_factory=list, description="Any noted exceptions")
    evidence_quote: str = Field(..., description="Verbatim quote supporting this rule")

class SectionRulesExtraction(BaseModel):
    rules: List[ExtractedRuleItem] = []

class BusinessRuleResponse(BaseModel):
    id: str
    project_id: str
    rule_key: str
    description: str
    condition_json: Dict[str, Any] = {}
    status: str
    supersedes_rule_id: Optional[str] = None
    superseded_by_key: Optional[str] = None
    approved_by: Optional[str] = None
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    evidence_ids: List[str] = []
    evidence_quotes: List[str] = []
    document_name: Optional[str] = None
    section_title: Optional[str] = None
