"""Evidence structuring Pydantic models."""
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field

ClaimType = Literal["step", "actor", "rule", "date", "form", "deadline", "fee", "other"]

class ExtractedEvidenceClaim(BaseModel):
    claim: str = Field(..., description="Factual extracted claim")
    quote: str = Field(..., description="EXACT verbatim substring from the source section")
    claim_type: ClaimType = "other"
    confidence: float = Field(0.90, ge=0.0, le=1.0)

class SectionEvidenceExtraction(BaseModel):
    claims: List[ExtractedEvidenceClaim] = []

class EvidenceResponse(BaseModel):
    id: str
    project_id: str
    evidence_key: str
    document_section_id: str
    document_filename: Optional[str] = None
    section_title: Optional[str] = None
    section_index: Optional[int] = None
    page_number: Optional[int] = None
    claim: str
    quote: str
    claim_type: str
    confidence: float
    status: str
    created_at: Optional[datetime] = None
