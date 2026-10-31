"""ProcessFoundry AI: As-Is Process Discovery Agent (A3)."""
import hashlib
import logging
import os
import re
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
    # "v2": the way evidence is chosen for the model changed, so models built the
    # old way are treated as out of date and rebuilt as a new version.
    return hashlib.sha256(("v2|" + "|".join(ids)).encode("utf-8")).hexdigest()

MAX_ITEMS_SIMPLE = 25  # at or below this many items, all of them are used as before


def select_evidence_for_prompt(evidence_items: List[Dict[str, Any]], max_chars: int) -> List[Dict[str, Any]]:
    """Choose which evidence the As-Is model sees.

    This used to be `evidence_items[:25]`: on a real 18-page SOP that meant only
    the contents page and phase headings were seen, so every step became a phase
    name with no actor, and the actions described later in the document (who
    verifies, who generates lots, who signs) never reached the model.

    Now action-bearing claims (step, actor) come first, then other claims, then
    the rest, each group in document order, until the size budget is used. The
    chosen items are returned in document order. Very short quotes (headings)
    are only used if there is room left.
    """
    if len(evidence_items) <= MAX_ITEMS_SIMPLE:
        return evidence_items

    def rank(e: Dict[str, Any]) -> int:
        ctype = (e.get("claim_type") or "").lower()
        quote = (e.get("quote") or "").strip()
        if len(quote) < 20:
            return 3
        if ctype in ("step", "actor"):
            return 0
        if ctype == "other":
            return 2
        return 1

    chosen, used = [], 0
    for e in sorted(evidence_items, key=lambda x: (rank(x), str(x.get("evidence_key") or ""))):
        size = len((e.get("quote") or "")) + 4
        if max_chars and used + size > max_chars:
            continue
        chosen.append(e)
        used += size
    chosen.sort(key=lambda x: str(x.get("evidence_key") or ""))
    return chosen


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
        default_cap = "14000" if llm_service.provider == "groq" else "40000"
        try:
            max_chars = int(os.getenv("LLM_ASIS_MAX_CHARS", default_cap))
        except ValueError:
            max_chars = 0
        prompt_evidence = select_evidence_for_prompt(evidence_items, max_chars)
        logger.info("As-Is prompt uses %d of %d evidence items.", len(prompt_evidence), len(evidence_items))
        evidence_summary = "\n".join([
            f"- {e['quote']}" for e in prompt_evidence
        ])

        prompt = (
            f"You are discovering the As-Is current state process for a college administrative procedure.\n"
            f"Project description: {process_description or 'General college process'}\n\n"
            f"Synthesize the following verified evidence into sequential steps:\n"
            f"{llm_service.wrap_source(evidence_summary)}\n\n"
            f"CRITICAL RULES:\n"
            f"1. Generate all process names, step names, actor descriptions, and unknowns in ENGLISH.\n"
            f"2. The actor is the one who PERFORMS the step. Name an actor only if a quote above says who does it:\n"
            f"   - active voice: 'NIC will segregate the applications' -> actor 'NIC'.\n"
            f"   - passive voice: 'applications are verified by the Institute/School' -> actor 'Institute/School'.\n"
            f"   - two performers: 'the checker and the DDO sign' -> actor 'Checker and DDO'.\n"
            f"   - the person something is done TO is not the actor: in 'the student is notified' the student is the receiver, so the actor is unknown.\n"
            f"   You may use a quote from a neighbouring sentence about the same step when the link is clear, "
            f"but never copy the previous step's actor just because it is nearby. If no quote says who does it "
            f"(e.g. 'The form is verified', 'Documents are checked'), you MUST set 'actor': null and add 'actor not stated' to 'unknowns'. "
            f"DO NOT GUESS OR INVENT AN ACTOR.\n"
            f"3. Link each step to its supporting quote from the evidence in its EXACT original language without translation.\n"
            f"4. Mark repeated or duplicate steps if observed in the source text.\n"
            f"5. A step is a concrete action (verify, reject, generate lots, sign, disburse). Do NOT make a step out of a "
            f"heading, a table-of-contents line or a title; use the actions described under those headings."
        )

        try:
            output = llm_service.complete_json(
                prompt=prompt,
                schema=AsIsDiscoveryOutput,
                system_instruction="Build the As-Is model in English strictly grounded in evidence. Keep supporting evidence quotes verbatim in their original language. Never guess an actor if not explicitly stated."
            )
        # except Exception as e:
        #     logger.error(f"Process discovery model call failed: {e}")
        #     output = AsIsDiscoveryOutput(
        #         process_name="Discovered Process",
        #         steps=[],
        #         overall_unknowns=["Discovery model execution error"]
        #     )
        except Exception:
            logger.exception(
                "As-Is discovery failed for project %s",
                project_id
            )
            raise

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
            # Also partial match across standard and Devanagari sentence boundaries
            for word in re.split(r"[.\u0964\u0965\n]+", e["quote"]):
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
