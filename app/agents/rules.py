"""ProcessFoundry AI: Business Rule Analysis Agent (A4)."""
import logging
from typing import List, Dict, Any

from app.schemas.rules import SectionRulesExtraction
from app.services.llm_service import llm_service, LLMQuotaExceeded
from app.services.quote_match import norm_ws
from app.repositories.database import db
from app.agents.evidence import EXTRACTOR_VERSION

logger = logging.getLogger("processfoundry.agent.rules")

class BusinessRuleAgent:
    def extract_section_rules(self, project_id: str, section: Dict[str, Any], evidence_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract candidate business rules for one section, linking to verified evidence."""
        section_text = section.get("text", "")
        if not section_text.strip():
            return []

        prompt = (
            f"Analyze the following process document section titled '{section.get('section_title', '')}'.\n"
            f"The source content may be written in Hindi, Marathi, English, or another language.\n"
            f"Extract all formal business rules, eligibility criteria, deadlines, fee requirements, and approval conditions.\n"
            f"Formulate all rule details (description, condition, outcome, exceptions) in ENGLISH.\n"
            f"For each rule, specify:\n"
            f"- description: clear rule statement in English\n"
            f"- condition: when this rule applies in English\n"
            f"- outcome: requirement, limitation, or consequence in English\n"
            f"- exceptions: any explicitly listed exceptions in English\n"
            f"- evidence_quote: EXACT verbatim sentence from the source text in its original language without translation\n\n"
            f"{llm_service.wrap_source(section_text)}"
        )

        try:
            extraction = llm_service.complete_json(
                prompt=prompt,
                schema=SectionRulesExtraction,
                system_instruction="Extract explicit business rules in English. Ground each rule in an exact verbatim quote from the original source without translation."
            )
        except LLMQuotaExceeded:
            raise
        except Exception as e:
            logger.warning(f"Rule extraction model call failed for section {section.get('id')}: {e}")
            return []

        db.supersede_section_rules(section["id"])  # only after a successful call

        # Find evidence IDs corresponding to the quotes or this section
        sec_evidence = [e for e in evidence_items if e.get("document_section_id") == section["id"]]
        ev_quote_map = {norm_ws(e["quote"]).lower(): e["id"] for e in sec_evidence}

        saved_rules = []
        unlinked = []
        for r in extraction.rules:
            matched_eids = []
            q_clean = norm_ws(r.evidence_quote).lower()
            if q_clean in ev_quote_map:
                matched_eids.append(ev_quote_map[q_clean])
            else:
                for k, eid in ev_quote_map.items():
                    if q_clean in k or k in q_clean:
                        matched_eids.append(eid)
                        break

            # Never attach a rule to evidence that does not support it. This
            # used to fall back to sec_evidence[0], i.e. whichever evidence item
            # happened to be first, which asserted support that did not exist
            # (finding F14). An unmatched rule is stored unlinked and reported.
            if not matched_eids:
                unlinked.append(r)

            cond_json = {
                "condition": r.condition,
                "outcome": r.outcome,
                "exceptions": r.exceptions,
                "quote": r.evidence_quote
            }

            try:
                saved = db.save_business_rule(
                    project_id=project_id,
                    description=r.description,
                    condition_json=cond_json,
                    evidence_ids=matched_eids
                )
                saved_rules.append(saved)
            except Exception as ex:
                logger.error(f"Failed to save business rule: {ex}")

        # A rule with no verifiable supporting quote is a parsing/extraction
        # problem, which brief 7.5 routes to the Analyst rather than silently
        # accepting an ungrounded rule.
        if unlinked:
            self._raise_unlinked_rule_question(project_id, section, unlinked)

        return saved_rules

    def _raise_unlinked_rule_question(self, project_id: str, section: Dict[str, Any], unlinked: List[Any]) -> None:
        """Ask the Analyst to check rules that could not be tied to a quote."""
        from app.agents.gaps import fingerprint, route_question_to_role, _norm

        titles = ", ".join(sorted({(u.description or "")[:60] for u in unlinked if u.description}))
        try:
            db.save_clarification_item(
                project_id=project_id,
                question=(
                    f"{len(unlinked)} candidate rule(s) from section "
                    f"'{section.get('section_title')}' could not be tied to an exact quote. "
                    "Are they really in the source?"
                ),
                reason=(
                    "The model proposed these rules but none of their quotations could be "
                    "verified against the stored section text, so they have no evidence "
                    f"link: {titles}"
                ),
                kind="parsing_error",
                assigned_role=route_question_to_role("parsing_error"),
                options=[
                    {"label": "The rules are correct; I will add the missing quotes", "is_ai_suggestion": False},
                    {"label": "The rules are not in the source; discard them", "is_ai_suggestion": False},
                ],
                fingerprint=fingerprint(
                    "parsing_error", _norm(section.get("section_title")), "unlinked_rules"
                ),
                ai_suggestion=None,
                run_id=None,
                link_targets=[],
            )
        except Exception as ex:
            logger.error(f"Could not record the unlinked-rule question: {ex}")

    def run_rules_pipeline(self, project_id: str, document_sections: List[Dict[str, Any]], evidence_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract rules for sections that have not produced rules yet.

        Same idempotence rule as the evidence pipeline (finding F6): a section
        that already produced rules under the current EXTRACTOR_VERSION is
        skipped, so a re-run costs no model calls and writes no duplicates.
        """
        done = db.sections_already_mined_for_rules(project_id, EXTRACTOR_VERSION)
        all_rules = [r for r in db.list_project_business_rules(project_id) if r.get("status") != "superseded"] if done else []
        if done:
            logger.info(f"Reusing stored rules for {len(done)} unchanged section(s).")

        for sec in document_sections:
            if str(sec["id"]) in done:
                continue
            sec_rules = self.extract_section_rules(project_id, sec, evidence_items)
            all_rules.extend(sec_rules)
        return all_rules

business_rule_agent = BusinessRuleAgent()
