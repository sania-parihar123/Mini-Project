"""Clarification items and human answers Pydantic models."""
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

QuestionKind = Literal[
    "conflicting_rules",
    "missing_actor",
    "ambiguous_term",
    "missing_info",
    "duplicate_step",       # [EXTENSION] a step the sources describe twice
    "parsing_error",
    "technical_conflict",
    "user_question"
]

QuestionRole = Literal["process_owner", "analyst", "technical_reviewer"]
AnswerKind = Literal["answer", "unknown"]

class ClarificationOption(BaseModel):
    """One answerable choice, with the source passage it came from (brief 7.12 item 5)."""
    label: str
    letter: Optional[str] = None          # A, B, ... matching the source badges
    quote: Optional[str] = None
    document_name: Optional[str] = None
    section_title: Optional[str] = None
    section_index: Optional[int] = None
    page_number: Optional[int] = None
    is_ai_suggestion: bool = False        # invented options must say so

class ClarificationSource(BaseModel):
    """A stored evidence passage behind a question (brief 7.12 item 4).

    Every field is read from stored records: the quote from `evidence_items`,
    the section from `document_sections`, the file name from `documents`.
    """
    id: str
    evidence_key: Optional[str] = None
    quote: Optional[str] = None
    document_name: Optional[str] = None
    section_index: Optional[int] = None
    section_title: Optional[str] = None
    page_number: Optional[int] = None

class ClarificationItemResponse(BaseModel):
    id: str
    project_id: str
    project_name: Optional[str] = None     # brief 7.12 item 1
    run_id: Optional[str] = None
    question_key: str
    question: str
    reason: Optional[str] = None
    kind: QuestionKind
    assigned_role: QuestionRole
    options: List[ClarificationOption] = []
    ai_suggestion: Optional[str] = None
    status: str
    answer: Optional[str] = None
    answered_by: Optional[str] = None
    answered_by_name: Optional[str] = None
    answered_at: Optional[datetime] = None
    fingerprint: str
    created_at: Optional[datetime] = None
    consequence_summary: Optional[str] = None   # brief 7.12 item 6
    linked_rules: List[str] = []
    linked_steps: List[str] = []
    linked_evidence: List[ClarificationSource] = []

class AnswerQuestionRequest(BaseModel):
    kind: AnswerKind = "answer"  # "answer" or "unknown"
    answer_text: Optional[str] = None

class EscalateQuestionRequest(BaseModel):
    reason: str = Field(..., min_length=3)

class VerifiedFactResponse(BaseModel):
    id: str
    project_id: str
    fact_key: str
    statement: str
    clarification_id: Optional[str] = None
    confirmed_by: str
    confirmed_by_name: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    status: str
