"""Testing and UAT Pydantic models."""
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel

TestKind = Literal["positive", "negative", "boundary", "exception", "permission", "journey"]

class TestCaseResponse(BaseModel):
    id: str
    project_id: str
    test_key: str
    requirement_id: str
    requirement_key: Optional[str] = None
    kind: TestKind
    scenario: str
    preconditions: Optional[str] = None
    steps: List[str] = []
    expected_result: str
    created_at: Optional[datetime] = None
