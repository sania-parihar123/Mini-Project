"""Document and parser Pydantic models."""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class DocumentSectionResponse(BaseModel):
    id: str
    document_id: str
    section_index: int
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    text: str
    read_from_image: bool = False

class DocumentResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    mime_type: str
    checksum: str
    version: int
    size_bytes: Optional[int] = None
    parse_status: str
    parse_warnings: List[str] = []
    created_at: Optional[datetime] = None
    sections_count: int = 0

class UploadResultLine(BaseModel):
    """One result line per uploaded file (review item 4)."""
    filename: str
    accepted: bool
    message: str
    document_id: Optional[str] = None
    sections_count: Optional[int] = None
    parse_warnings: List[str] = []
    status_code: Optional[int] = None


class BatchUploadResponse(BaseModel):
    results: List[UploadResultLine] = []
    accepted_count: int = 0
    rejected_count: int = 0


class UnderstandingFact(BaseModel):
    statement: str
    exact_quote: Optional[str] = None
    page_number: Optional[int] = None
    is_extracted_fact: bool = True  # True: exact extracted fact with quotation; False: AI interpretation
    quote_verified: bool = False    # the quote was checked against the stored section text

class DocumentUnderstandingResponse(BaseModel):
    document_id: str
    filename: str
    read_from_image: bool = False
    partially_read: bool = False        # at least one page could not be read
    model_is_mock: bool = False         # the content below was invented, not read
    unverified_quotes_dropped: int = 0  # quotes the model made up, discarded by code
    document_type: UnderstandingFact
    summary: UnderstandingFact
    required_documents: List[UnderstandingFact] = []
    process_steps: List[UnderstandingFact] = []
    fees: List[UnderstandingFact] = []
    dates_and_deadlines: List[UnderstandingFact] = []
    people_roles_responsibilities: List[UnderstandingFact] = []
    missing_or_uncertain_information: List[str] = []
