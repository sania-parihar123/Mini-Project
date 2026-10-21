"""ProcessFoundry AI: As-Is Process Discovery Agent (A3)."""
import hashlib
import logging
from typing import List, Dict, Any, Optional

from app.schemas.process import AsIsDiscoveryOutput
from app.services.llm_service import llm_service
from app.repositories.database import db

logger = logging.getLogger("processfoundry.agent.discovery")


def evidence_signature(evidence_items: List[Dict[str, Any]]) -> str:
    """Stable fingerprint of the evidence an As-Is model was built from.

    Lets a re-run tell "same evidence, nothing to do" from "evidence changed,
    build a new version" without re-calling the model (finding F6).
    """
    ids = sorted(str(e.get("id")) for e in evidence_items if e.get("id"))
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()

class ProcessDiscoveryAgent:
    def discover_as_is(self, project_id: str, evidence_items: List[Dict[str, Any]], process_description: Optional[str] = "") -> Dict[str, Any]:
        """Synthesize verified evidence into an As-Is process model, preserving unknown actors as NULL.

        Idempotent: if the latest process version was built from exactly this
        evidence, it is returned unchanged with no model call and no duplicate
        step rows. If the evidence has changed, a NEW version is created and
        dependent artifacts are marked stale (brief 3.5), never overwritten.
        """
        signature = evidence_signature(evidence_items)
        latest = db.get_latest_process_version(project_id)
        if latest:
            existing_steps = db.list_process_steps(latest["id"])
            stored_sig = (latest.get("as_is_json") or {}).get("evidence_signature")
            if existing_steps and stored_sig == signature:
                logger.info(
                    "As-Is model is already current for this evidence; reusing "
                    f"{latest.get('version')} with {len(existing_steps)} step(s), no model call."
                )
                reused = dict(latest)
                reused["steps"] = existing_steps
                return reused

        # Brief 9.2: keep evidence IDs as metadata only. They used to be written
        # into the summarised text, and came back out inside step names
        # ("- [EVD-001] Quote: ..."), which also broke duplicate detection.
        evidence_summary = "\n".join([
            f"- {e['quote']}" for e in evidence_items[:25]
        ])

        prompt = (
            f"You are discovering the As-Is current state process for a college administrative procedure.\n"
            f"Project description: {process_description or 'General college process'}\n\n"
            f"Synthesize the following verified evidence into sequential steps:\n"
            f"{llm_service.wrap_source(evidence_summary)}\n\n"
            f"CRITICAL RULES:\n"
            f"1. If a step's source sentence does NOT explicitly name an actor (e.g. 'The form is verified', 'Documents are checked'), "
            f"you MUST set 'actor': null and add 'actor not stated' to 'unknowns'. DO NOT GUESS OR INVENT AN ACTOR.\n"
            f"2. Link each step to its supporting quote from the evidence.\n"
            f"3. Mark repeated or duplicate steps if observed in the source text."
        )

        try:
            output = llm_service.complete_json(
                prompt=prompt,
                schema=AsIsDiscoveryOutput,
                system_instruction="Build the As-Is model strictly grounded in evidence. Never guess an actor if not explicitly stated."
            )
        except Exception as e:
            logger.error(f"Process discovery model call failed: {e}")
            output = AsIsDiscoveryOutput(
                process_name="Discovered Process",
                steps=[],
                overall_unknowns=["Discovery model execution error"]
            )

        # A changed evidence set means a new version, not an overwrite, and
        # anything generated from the previous version becomes stale.
        next_version = (latest["version"] + 1) if latest else 1
        as_is_json = output.model_dump()
        as_is_json["evidence_signature"] = signature
        pv = db.create_process_version(
            project_id=project_id,
            version=next_version,
            as_is_json=as_is_json,
            status="draft"
        )
        if latest:
            db.mark_dependants_stale(
                project_id,
                f"As-Is process rebuilt as version {next_version} from changed evidence",
            )

        # Map quotes back to evidence IDs
        quote_to_ev_id = {e["quote"].strip().lower(): e["id"] for e in evidence_items}
        for e in evidence_items:
            # Also partial match
            for word in e["quote"].split("."):
                if len(word.strip()) > 15:
                    quote_to_ev_id[word.strip().lower()] = e["id"]

        saved_steps = []
        for s in output.steps:
            # Strict code enforcement: if actor is empty string, convert to None
            actor = s.actor.strip() if (s.actor and s.actor.strip().lower() not in ("none", "null", "unknown", "")) else None
            unknowns = list(s.unknowns)
            if actor is None and "actor not stated" not in unknowns:
                unknowns.append("actor not stated")

            # Match supporting evidence
            matched_eids = []
            for q in s.supporting_evidence_quotes:
                q_clean = q.strip().lower()
                if q_clean in quote_to_ev_id:
                    matched_eids.append(quote_to_ev_id[q_clean])
                else:
                    for k, eid in quote_to_ev_id.items():
                        if q_clean in k or k in q_clean:
                            matched_eids.append(eid)
                            break

            if not matched_eids and evidence_items:
                matched_eids.append(evidence_items[0]["id"])

            step = db.save_process_step(
                project_id=project_id,
                process_version_id=pv["id"],
                name=s.name,
                actor=actor,
                step_type=s.step_type,
                sequence=s.sequence,
                inputs=s.inputs,
                outputs=s.outputs,
                unknowns=unknowns,
                automation=s.automation,
                human_approval_required=s.human_approval_required,
                evidence_ids=matched_eids
            )
            saved_steps.append(step)

        pv["steps"] = saved_steps
        return pv

discovery_agent = ProcessDiscoveryAgent()
