"""Traceability matrix Pydantic models."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class TraceabilityChain(BaseModel):
    requirement_key: str
    requirement_statement: str
    type: str
    status: str
    rule_keys: List[str] = []
    rule_descriptions: List[str] = []
    evidence_keys: List[str] = []
    evidence_quotes: List[str] = []
    document_names: List[str] = []
    section_titles: List[str] = []
    step_keys: List[str] = []
    step_names: List[str] = []
    test_keys: List[str] = []
    test_scenarios: List[str] = []
    verified_fact_keys: List[str] = []
    verified_fact_statements: List[str] = []

class TraceabilityValidationReport(BaseModel):
    total_requirements: int
    requirements_without_evidence_or_rules: List[str] = []
    tests_without_requirements: List[str] = []
    quotes_verified_count: int
    quotes_mismatch_count: int
    unresolved_questions_count: int
    is_valid: bool = True
