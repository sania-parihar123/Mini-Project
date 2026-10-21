"""ProcessFoundry AI: Process Redesign (A7) and Automation Assessment (A8) Agent."""
import logging
from typing import List, Dict, Any, Optional

from app.schemas.process import ToBeRedesignOutput
from app.services.llm_service import llm_service
from app.repositories.database import db

logger = logging.getLogger("processfoundry.agent.redesign")

class RedesignAgent:
    def redesign_process(
        self,
        project_id: str,
        as_is_steps: List[Dict[str, Any]],
        business_rules: List[Dict[str, Any]],
        verified_facts: List[Dict[str, Any]],
        process_version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Propose candidate To-Be process and classify automation potentials."""
        steps_summary = "\n".join([
            f"- Step {s.get('sequence', idx+1)}: {s.get('name')} (Actor: {s.get('actor') or 'Unknown'})"
            for idx, s in enumerate(as_is_steps)
        ])
        rules_summary = "\n".join([
            f"- Rule {r.get('rule_key')}: {r.get('description')} (Status: {r.get('status')})"
            for r in business_rules[:15]
        ])
        facts_summary = "\n".join([
            f"- Confirmed Fact: {f.get('statement')}"
            for f in verified_facts
        ])

        prompt = (
            f"You are redesigning an administrative college process to create a modernized To-Be workflow.\n\n"
            f"Current As-Is Steps:\n{llm_service.wrap_source(steps_summary)}\n\n"
            f"Business Rules:\n{llm_service.wrap_source(rules_summary)}\n\n"
            f"Human-Confirmed Facts:\n{llm_service.wrap_source(facts_summary or 'No extra facts.')}\n\n"
            f"Redesign the process for digital efficiency:\n"
            f"1. Replace manual paper submissions with digital portal entry.\n"
            f"2. Classify each step's automation: 'deterministic', 'ai_assisted', 'human', or 'hybrid'.\n"
            f"3. Mark 'human_approval_required: true' for official financial, exception, or eligibility decisions.\n"
            f"4. Eliminate redundant verification or repeated manual handoffs."
        )

        try:
            output = llm_service.complete_json(
                prompt=prompt,
                schema=ToBeRedesignOutput,
                system_instruction="Propose an optimized To-Be process with strict automation classification. Critical business decisions must retain human approval."
            )
        except Exception as e:
            logger.error(f"Process redesign model call failed: {e}")
            output = ToBeRedesignOutput(
                process_name="Modernized College Process",
                summary_of_changes="Digital intake, automated eligibility calculation, and role-based human approval.",
                steps=[]
            )

        # Update process version in DB
        pv = db.get_latest_process_version(project_id)
        if pv:
            with db.get_connection() as conn:
                cur = conn.cursor()
                to_be_dump = output.model_dump()
                import json
                if db.use_postgres:
                    cur.execute("UPDATE process_versions SET to_be_json = %s, status = 'needs_review' WHERE id = %s", (json.dumps(to_be_dump), pv["id"]))
                else:
                    cur.execute("UPDATE process_versions SET to_be_json = ?, status = 'needs_review' WHERE id = ?", (json.dumps(to_be_dump), pv["id"]))
                    conn.commit()

        return output.model_dump()

redesign_agent = RedesignAgent()
