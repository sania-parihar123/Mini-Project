# 04 Evidence Structuring
Status: agreed
Source: Part 3.1 (A2), Part 4.3, Part 6 Step 6, Part 8.4 [BASELINE + EXTENSION]

## Purpose
Extract factual claims and quotes from document sections using the LLM gateway, and strictly verify in deterministic code that each quote is an exact, verbatim substring of the section text before persisting.

## Requirements
- SPEC-04-01 For every document section, the system shall prompt the model for factual claims (steps, actors, rules, dates, forms, deadlines), each accompanied by a verbatim quote from that section.
- SPEC-04-02 Deterministic verification: The system shall discard any claim whose quote is NOT a verbatim substring of that section's text, logging a warning.
- SPEC-04-03 Verified evidence rows shall be assigned a project-unique readable key `EVD-nnn` minted via `project_counters`.
- SPEC-04-04 Each saved evidence record shall store `document_section_id`, `claim`, `quote`, `claim_type`, and `confidence` (0.00 - 1.00).

## Acceptance criteria
- AC-04-01 (covers SPEC-04-02) Given the model outputs a claim with a quote that does not appear verbatim in the section text, when the evidence validator runs, then that claim is discarded and not saved to `evidence_items`.
- AC-04-02 (covers SPEC-04-01/03/04) Given a section with text "Applications must be submitted by 31 March.", when evidence extraction runs, then a valid claim with exact quote "Applications must be submitted by 31 March." is saved as `EVD-001` linked to that section.

## Design notes
- Files: `app/agents/evidence.py`, `app/schemas/evidence.py`.
- Validation rule: `assert quote in section_text`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-04-01
  - `test_evidence_extraction_verbatim_quote_saved` (`tests/test_evidence.py`)
  - `test_understanding_quotes_are_verified_against_the_source` (`tests/test_llm_configuration.py`)
  - `test_the_evidence_quote_is_findable_in_the_response` (`tests/test_questions_endpoint.py`)
- SPEC-04-02
  - `test_evidence_rejection_when_quote_not_verbatim` (`tests/test_evidence.py`)
  - `test_quotes_are_reproducible_from_the_source` (`tests/test_fixture_defect_coverage.py`)
  - `test_a_fabricated_understanding_quote_is_dropped` (`tests/test_llm_configuration.py`)
  - `test_understanding_quotes_are_verified_against_the_source` (`tests/test_llm_configuration.py`)
  - `test_the_evidence_quote_is_findable_in_the_response` (`tests/test_questions_endpoint.py`)
  - `test_rules_are_never_linked_to_unrelated_evidence` (`tests/test_security_hardening.py`)
- SPEC-04-03
  - `test_evidence_extraction_verbatim_quote_saved` (`tests/test_evidence.py`)
  - `test_understanding_quotes_are_verified_against_the_source` (`tests/test_llm_configuration.py`)
  - `test_the_evidence_quote_is_findable_in_the_response` (`tests/test_questions_endpoint.py`)
- SPEC-04-04
  - `test_evidence_extraction_verbatim_quote_saved` (`tests/test_evidence.py`)
  - `test_understanding_quotes_are_verified_against_the_source` (`tests/test_llm_configuration.py`)
  - `test_the_evidence_quote_is_findable_in_the_response` (`tests/test_questions_endpoint.py`)
