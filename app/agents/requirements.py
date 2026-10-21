import json
import logging
from typing import List, Dict, Any, Optional

from app.repositories.database import db
from app.services.artifact_export import (
    generate_brd_markdown,
    generate_prd_markdown,
    generate_frd_markdown,
    generate_srs_markdown,
    generate_workflow_json
)

logger = logging.getLogger("processfoundry.agent.requirements")

class RequirementsAgent:
    def synthesize_requirements(
        self,
        project_id: str,
        as_is_steps: List[Dict[str, Any]],
        business_rules: List[Dict[str, Any]],
        verified_facts: List[Dict[str, Any]],
        to_be_model: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Synthesize structured requirement records from process steps, rules, and facts."""
        saved_reqs = []

        # Business Requirements from confirmed facts & major rules
        for r in business_rules[:6]:
            links = [("rule", r["id"], "derived_from")]
            req = db.save_requirement(
                project_id=project_id,
                req_type="business",
                title=f"Policy Compliance: {r.get('rule_key')}",
                statement=f"The system shall enforce: {r.get('description')}",
                priority="Must",
                acceptance_criteria=[
                    f"Given an applicant action, when evaluated against {r.get('rule_key')}, the condition '{r.get('condition_json', {}).get('condition', 'criteria')}' is checked."
                ],
                status="draft",
                links=links
            )
            saved_reqs.append(req)

        # Functional Requirements from process steps
        target_steps = to_be_model.get("steps", []) if to_be_model else as_is_steps
        for idx, s in enumerate(target_steps[:8]):
            s_name = s.get("name", "Process Step")
            s_actor = s.get("actor") or "Authorized User"
            links = []
            if s.get("id"):
                links.append(("step", s["id"], "supported_by"))

            status = "draft"
            if s.get("unknowns") and "actor not stated" in s.get("unknowns", []):
                status = "needs_clarification"

            req = db.save_requirement(
                project_id=project_id,
                req_type="functional",
                title=f"Activity Execution: {s_name[:35]}",
                statement=f"The system shall enable {s_actor} to perform {s_name}.",
                priority="Must",
                acceptance_criteria=[
                    f"Given {s_actor} navigates to the workflow screen, they can execute {s_name} with valid inputs."
                ],
                status=status,
                links=links
            )
            saved_reqs.append(req)

        # Workflow requirement
        wf_req = db.save_requirement(
            project_id=project_id,
            req_type="workflow",
            title="End-to-End Workflow State Progression",
            statement="The system shall advance application records sequentially through intake, review, and final disposition stages.",
            priority="Must",
            acceptance_criteria=["State changes are logged with user ID and timestamp in the audit chain."],
            status="draft"
        )
        saved_reqs.append(wf_req)

        return saved_reqs

    def generate_all_artifacts(self, project_id: str) -> List[Dict[str, Any]]:
        """Generate and persist BRD, PRD, FRD, Business Rules Catalogue, and Workflow JSON."""
        project = db.get_project(project_id)
        requirements = db.list_project_requirements(project_id)
        rules = db.list_project_business_rules(project_id)
        pv = db.get_latest_process_version(project_id)
        steps = pv.get("steps", []) if pv else []
        to_be = pv.get("to_be_json") if pv else None

        generated_artifacts = []

        # 1. BRD
        brd_md = generate_brd_markdown(project, requirements, rules, steps)
        brd = db.save_artifact(project_id, "brd", brd_md, content_json={"requirements_count": len(requirements)}, status="draft")
        generated_artifacts.append(brd)

        # 2. PRD
        prd_md = generate_prd_markdown(project, requirements, to_be)
        prd = db.save_artifact(project_id, "prd", prd_md, content_json={"features_count": len(requirements)}, status="draft")
        generated_artifacts.append(prd)

        # 3. FRD
        frd_md = generate_frd_markdown(project, requirements, rules, to_be)
        frd = db.save_artifact(project_id, "frd", frd_md, content_json={"rules_count": len(rules)}, status="draft")
        generated_artifacts.append(frd)

        # 4. SRS (Software Requirements Specification)
        srs_md = generate_srs_markdown(project, requirements, rules, steps)
        srs = db.save_artifact(project_id, "srs", srs_md, content_json={"requirements_count": len(requirements), "rules_count": len(rules)}, status="draft")
        generated_artifacts.append(srs)

        # 5. Business Rules Catalogue
        rules_md = f"# Business Rules Catalogue\n**Project:** {project.get('name')}\n**Status:** DRAFT / NEEDS REVIEW\n\n"
        rules_md += "| Rule ID | Description | Condition | Status |\n|---|---|---|---|\n"
        for r in rules:
            rules_md += f"| {r.get('rule_key')} | {r.get('description')} | {r.get('condition_json', {}).get('condition', '')} | {r.get('status')} |\n"
        rules_art = db.save_artifact(project_id, "rules_catalogue", rules_md, content_json={"rules": rules}, status="draft")
        generated_artifacts.append(rules_art)

        # 5. Roles & Permissions Matrix
        roles_md = f"""# Roles and Permissions Matrix
**Project:** {project.get('name')}
**Status:** DRAFT / NEEDS REVIEW

| Action | Process Owner | Analyst | Technical Reviewer |
|---|---|---|---|
| View Project & Evidence | Yes | Yes | Yes |
| Upload Documents | Yes | Yes | No |
| Start Analysis Run | Yes | Yes | No |
| Answer Assigned Questions | If assigned | If assigned | If assigned |
| Approve Business Rules | Yes | No | No |
| Approve To-Be Redesign | Yes | No | No |
| Approve BRD / PRD / FRD | Yes | No | No |
| Approve Architecture & Tests | No | No | Yes |
"""
        roles_art = db.save_artifact(project_id, "roles_matrix", roles_md, content_json={}, status="draft")
        generated_artifacts.append(roles_art)

        # 6. Workflow JSON
        wf_json = generate_workflow_json(project, steps, rules)
        wf_md = f"# Workflow Specification (JSON)\n```json\n{json.dumps(wf_json, indent=2)}\n```"
        wf_art = db.save_artifact(project_id, "workflow_json", wf_md, content_json=wf_json, status="draft")
        generated_artifacts.append(wf_art)

        return generated_artifacts

requirements_agent = RequirementsAgent()
