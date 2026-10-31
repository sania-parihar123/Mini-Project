"""Pure-Python spec builder for the Interactive Prototype feature (08).

Derives a validated PrototypeSpec purely from stored database records:
- To-Be process steps & actors
- Synthesized requirements and acceptance criteria
- Extracted business rules
- Evidence quotes for hints

Contains zero LLM calls, zero eval/exec, and zero invented requirements.
"""
import hashlib
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.repositories.database import db, now_iso
from app.schemas.prototypes import PrototypeField, PrototypeScreen, PrototypeSpec


class PrototypeBuildError(Exception):
    """Raised when prototype cannot be built due to missing or incomplete project data."""
    pass


FILE_RE = re.compile(
    r"document|certificate|proof|receipt|upload|marksheet|photo|scan|attachment|copy|letter|id card|aadhaar|statement|file|form",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"date|deadline|period|time|dob|timestamp", re.IGNORECASE)
NUMBER_RE = re.compile(r"income|amount|fee|salary|price|cost|count|number|percentage|score|marks|qty|quantity|rate", re.IGNORECASE)
TEXTAREA_RE = re.compile(r"description|reason|remarks|notes|justification|comment|statement|details|feedback", re.IGNORECASE)
SELECT_RE = re.compile(r"status|decision|type|category|mode|gender|grade", re.IGNORECASE)


def infer_field_type(name: str) -> tuple[str, List[str]]:
    """Infer field type and optional select options from input name."""
    clean_name = name.strip()
    if FILE_RE.search(clean_name):
        return "file", []
    if DATE_RE.search(clean_name):
        return "date", []
    if NUMBER_RE.search(clean_name):
        return "number", []
    if TEXTAREA_RE.search(clean_name):
        return "textarea", []
    if SELECT_RE.search(clean_name):
        if re.search(r"decision|approval", clean_name, re.IGNORECASE):
            return "select", ["Approved", "Rejected", "Pending Changes"]
        if re.search(r"status", clean_name, re.IGNORECASE):
            return "select", ["Pending", "In Progress", "Completed"]
        return "select", ["Standard", "Expedited", "Exempt"]
    return "text", []


def build_prototype_spec(project_id: str, user_id: Optional[str] = None) -> PrototypeSpec:
    """Derive and persist a PrototypeSpec for the given project."""
    # 1. Validate To-Be process version
    pv = db.get_latest_process_version(project_id)
    if not pv or not pv.get("to_be_json"):
        raise PrototypeBuildError("No approved To-Be process yet.")

    # 2. Validate workflow_json artifact
    wf_art = db.get_artifact_by_type(project_id, "workflow_json")
    if not wf_art or not wf_art.get("content_json"):
        raise PrototypeBuildError("Workflow JSON artifact is not available. Please run the analysis workflow first.")

    # 3. Validate requirements
    reqs = db.list_project_requirements(project_id)
    if not reqs:
        raise PrototypeBuildError("Requirements have not been synthesized yet.")

    # 4. Fetch rules, evidence, and project info
    rules = db.list_project_business_rules(project_id)
    evidence = db.list_project_evidence(project_id)
    project = db.get_project(project_id)

    process_name = (
        (project or {}).get("name")
        or pv.get("to_be_json", {}).get("process_name")
        or pv.get("to_be_json", {}).get("name")
        or "Process"
    )

    evidence_map = {}
    for ev in evidence:
        ekey = ev.get("evidence_key")
        quote = ev.get("quote") or ev.get("text")
        if ekey and quote:
            evidence_map[ekey] = quote

    # 5. Extract steps from process version (ordered by sequence)
    steps = pv.get("steps") or []
    if not steps:
        raw_steps = pv.get("to_be_json", {}).get("steps", [])
        steps = [
            {
                "id": s.get("id") or f"STEP-{i+1:03d}",
                "step_key": s.get("id") or f"STEP-{i+1:03d}",
                "name": s.get("name") or f"Step {i+1}",
                "actor": s.get("actor") or "Process Participant",
                "inputs": s.get("inputs") or [],
                "outputs": s.get("outputs") or [],
                "unknowns": s.get("unknowns") or [],
                "automation": s.get("automation") or "",
                "human_approval_required": bool(s.get("human_approval_required")),
                "evidence_keys": s.get("evidence_keys") or [],
            }
            for i, s in enumerate(raw_steps)
        ]

    # Map step_key -> linked requirements and rules
    step_reqs_map: Dict[str, List[Dict[str, Any]]] = {}
    for req in reqs:
        for sk in req.get("supporting_step_keys", []):
            step_reqs_map.setdefault(sk, []).append(req)

    screens: List[PrototypeScreen] = []
    actors_set: List[str] = []
    missing_info_notices: List[str] = []

    for idx, s in enumerate(steps):
        s_key = s.get("step_key") or s.get("id") or f"STEP-{idx+1:03d}"
        s_name = s.get("name") or f"Step {idx+1}"
        s_actor = s.get("actor") or "Actor not stated"
        s_automation = s.get("automation") or ""
        s_approval = bool(s.get("human_approval_required"))
        s_inputs = s.get("inputs") or []
        s_outputs = s.get("outputs") or []
        s_unknowns = s.get("unknowns") or []
        s_ev_keys = s.get("evidence_keys") or []

        if s_actor not in actors_set:
            actors_set.append(s_actor)

        if not s.get("actor") or s_actor == "Actor not stated":
            missing_info_notices.append(f"{s_key} ({s_name}): Actor is not stated in source documents.")

        for unk in s_unknowns:
            notice = f"{s_key} ({s_name}): {unk}"
            if notice not in missing_info_notices:
                missing_info_notices.append(notice)

        # Linked requirements
        linked_reqs = step_reqs_map.get(s_key, [])
        req_keys = [r.get("requirement_key") for r in linked_reqs if r.get("requirement_key")]

        # Linked business rules
        br_keys_set = set()
        for r in linked_reqs:
            for brk in r.get("supporting_rule_keys", []):
                br_keys_set.add(brk)
        br_keys = sorted(list(br_keys_set))

        # Build fields from step inputs and acceptance criteria
        fields: List[PrototypeField] = []
        seen_fields = set()

        # Step inputs
        for inp in s_inputs:
            field_name = str(inp).strip()
            if not field_name or field_name.lower() in seen_fields:
                continue
            seen_fields.add(field_name.lower())
            ftype, options = infer_field_type(field_name)
            # Find evidence hint if available
            hint = None
            if s_ev_keys:
                first_ev = s_ev_keys[0]
                if first_ev in evidence_map:
                    hint = f"Sourced from {first_ev}: \"{evidence_map[first_ev][:120]}...\""
            fields.append(
                PrototypeField(
                    name=field_name,
                    field_type=ftype,
                    options=options,
                    required=True,
                    hint=hint,
                )
            )

        # Check if acceptance criteria define additional explicit fields
        for r in linked_reqs:
            for ac in r.get("acceptance_criteria", []):
                if isinstance(ac, str) and (ac.lower().startswith("must capture") or ac.lower().startswith("requires")):
                    cleaned_ac = re.sub(r"^(must capture|requires|must include)\s+", "", ac, flags=re.IGNORECASE)
                    for item in cleaned_ac.split(","):
                        cand = item.strip().rstrip(".")
                        if 2 < len(cand) < 40 and cand.lower() not in seen_fields:
                            seen_fields.add(cand.lower())
                            ftype, options = infer_field_type(cand)
                            fields.append(
                                PrototypeField(
                                    name=cand,
                                    field_type=ftype,
                                    options=options,
                                    required=True,
                                    hint=f"Required by {r.get('requirement_key')}",
                                )
                            )

        screen = PrototypeScreen(
            screen_id=f"SCREEN-{idx+1:03d}",
            title=s_name,
            actor=s_actor,
            automation=s_automation,
            human_approval_required=s_approval,
            fields=fields,
            outputs=s_outputs,
            business_rule_keys=br_keys,
            requirement_keys=req_keys,
            unknowns=s_unknowns,
        )
        screens.append(screen)

    # 6. Formulate business rules catalogue for prototype display
    rule_items = []
    for r in rules:
        r_key = r.get("rule_key")
        r_desc = r.get("description") or r.get("statement") or ""
        if r_key and r_desc:
            rule_items.append({"key": r_key, "description": r_desc})

    # 7. Compute deterministic fingerprint
    wf_version = pv.get("version", 1)
    req_count = len(reqs)
    rule_count = len(rules)
    rule_keys_str = ",".join(sorted([r.get("rule_key", "") for r in rules]))
    fingerprint_seed = f"{project_id}|{wf_version}|{req_count}|{rule_count}|{rule_keys_str}"
    spec_fingerprint = hashlib.sha256(fingerprint_seed.encode("utf-8")).hexdigest()

    created_at = now_iso()

    spec = PrototypeSpec(
        project_id=project_id,
        process_name=process_name,
        actors=actors_set,
        screens=screens,
        business_rules=rule_items,
        missing_info_notices=missing_info_notices,
        generated_from_workflow_version=wf_version,
        spec_fingerprint=spec_fingerprint,
        created_at=created_at,
    )

    # 8. Persist in database
    db.save_prototype_spec(
        project_id=project_id,
        spec_fingerprint=spec_fingerprint,
        spec_json=spec.dict(),
        generated_by=user_id,
    )

    return spec
