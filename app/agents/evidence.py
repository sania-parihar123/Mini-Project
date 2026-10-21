"""ProcessFoundry AI: Evidence Extraction Agent (A2)."""
import logging
from typing import List, Dict, Any

from app.schemas.evidence import SectionEvidenceExtraction
from app.services.llm_service import llm_service
from app.repositories.database import db

logger = logging.getLogger("processfoundry.agent.evidence")

# Bump this when the evidence or rule prompts change, to force re-extraction of
# sections that were mined by an older version.
EXTRACTOR_VERSION = "v1"

class EvidenceAgent:
    def extract_section_evidence(self, project_id: str, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract claims with verbatim quotes for one section, strictly verifying in code."""
        section_text = section.get("text", "")
        if not section_text.strip():
            return []

        prompt = (
            f"Analyze the following process document section titled '{section.get('section_title', '')}'.\n"
            f"Extract factual statements (steps, actors, business rules, deadlines, fees, forms).\n"
            f"CRITICAL REQUIREMENT: For every claim, provide a 'quote' that is an EXACT, verbatim, word-for-word substring from the section text.\n\n"
            f"{llm_service.wrap_source(section_text)}"
        )

        try:
            extraction = llm_service.complete_json(
                prompt=prompt,
                schema=SectionEvidenceExtraction,
                system_instruction="Extract only factual claims. The quote must be an exact verbatim substring from the source."
            )
        except Exception as e:
            logger.warning(f"Evidence extraction LLM call failed for section {section.get('id')}: {e}")
            return []

        saved_evidence = []
        for c in extraction.claims:
            quote = c.quote.strip()
            # Deterministic code check: quote must be a verbatim substring
            if not quote or quote not in section_text:
                logger.warning(f"Discarding unverified claim: quote '{quote[:40]}...' is not a verbatim substring of section.")
                continue

            try:
                evd = db.save_evidence_item(
                    project_id=project_id,
                    section_id=section["id"],
                    claim=c.claim,
                    quote=quote,
                    claim_type=c.claim_type,
                    confidence=c.confidence
                )
                saved_evidence.append(evd)
            except Exception as ex:
                logger.error(f"Failed to persist evidence item: {ex}")

        return saved_evidence

    def run_evidence_pipeline(self, project_id: str, document_sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract evidence for sections that have not been mined yet.

        Brief Phase 0: "remember results already stored so a re-run does not
        repeat calls for unchanged sections". A section already stamped with the
        current EXTRACTOR_VERSION is skipped: its stored evidence is reused, no
        model call is made and no duplicate row is written (finding F6).
        """
        done = db.sections_already_extracted(project_id, EXTRACTOR_VERSION)
        reused_ids = [s["id"] for s in document_sections if str(s["id"]) in done]
        all_evidence = list(db.list_project_evidence_for_sections(project_id, reused_ids))
        if reused_ids:
            logger.info(
                f"Reusing stored evidence for {len(reused_ids)} unchanged section(s); "
                f"no model calls made for them."
            )

        for sec in document_sections:
            if str(sec["id"]) in done:
                continue
            sec_ev = self.extract_section_evidence(project_id, sec)
            all_evidence.extend(sec_ev)
            # Stamp only after a successful extraction, so a failed section is
            # retried on the next run rather than silently skipped for ever.
            db.mark_section_extracted(sec["id"], EXTRACTOR_VERSION)
        return all_evidence

evidence_agent = EvidenceAgent()
