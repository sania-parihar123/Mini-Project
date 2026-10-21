"""Discovery, rules, tests, and traceability report endpoints."""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from app.schemas.traceability import TraceabilityChain, TraceabilityValidationReport
from app.repositories.database import db
from app.services.permissions import get_current_user, require_project_member
from app.agents.quality import quality_agent

router = APIRouter(prefix="/api", tags=["Traceability & Models"])

@router.get("/projects/{project_id}/traceability", response_model=Dict[str, Any])
def get_project_traceability(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    requirements = db.list_project_requirements(project_id)
    rules = {r["id"]: r for r in db.list_project_business_rules(project_id)}
    evidence = {e["id"]: e for e in db.list_project_evidence(project_id)}
    tests = db.list_project_test_cases(project_id)
    validation = quality_agent.validate_traceability(project_id)

    chains = []
    for req in requirements:
        req_tests = [t for t in tests if t.get("requirement_id") == req["id"]]
        chains.append({
            "requirement_key": req["requirement_key"],
            "requirement_statement": req["statement"],
            "type": req["type"],
            "status": req["status"],
            "rule_keys": req.get("supporting_rule_keys", []),
            "evidence_keys": req.get("supporting_evidence_keys", []),
            "step_keys": req.get("supporting_step_keys", []),
            "test_keys": [t["test_key"] for t in req_tests],
            "test_scenarios": [t["scenario"] for t in req_tests]
        })

    return {
        "chains": chains,
        "validation_report": validation
    }

@router.get("/projects/{project_id}/discovery", response_model=Dict[str, Any])
def get_as_is_discovery(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    pv = db.get_latest_process_version(project_id)
    return pv or {"status": "not_started", "steps": []}

@router.get("/projects/{project_id}/rules", response_model=List[Dict[str, Any]])
def get_project_rules(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    return db.list_project_business_rules(project_id)

@router.get("/projects/{project_id}/evidence", response_model=List[Dict[str, Any]])
def get_project_evidence(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    return db.list_project_evidence(project_id)

@router.get("/projects/{project_id}/tests", response_model=List[Dict[str, Any]])
def get_project_tests(project_id: str, user: dict = Depends(get_current_user)):
    require_project_member(project_id, user)
    return db.list_project_test_cases(project_id)
