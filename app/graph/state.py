"""ProcessFoundry AI: LangGraph Workflow State Definition."""
from typing import TypedDict, List, Dict, Any, Optional

class ProcessFoundryState(TypedDict, total=False):
    project_id: str
    run_id: str
    process_description: str
    source_document_ids: List[str]
    extracted_sections: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    as_is_process: Dict[str, Any]
    candidate_rules: List[Dict[str, Any]]
    issues: List[Dict[str, Any]]
    clarification_answers: List[Dict[str, Any]]
    verified_facts: List[Dict[str, Any]]
    to_be_process: Dict[str, Any]
    automation_assessment: List[Dict[str, Any]]
    requirements: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]
    validation_errors: List[Dict[str, Any]]
    validation_report: Dict[str, Any]
    approval_status: str
    next_action: str
    retry_count: int
    is_paused: bool
