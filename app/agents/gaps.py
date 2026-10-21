"""ProcessFoundry AI: Gap and Conflict Analysis Agent (A5).

All detection here is deterministic Python, never the model (brief step 9).
The checks are:

  * `missing_actor`     a step whose source names no actor
  * `conflicting_rules` two rules giving different values for the SAME subject
  * `ambiguous_term`    a vague word in an evidence quote
  * `missing_info`      a step carrying unknowns other than the actor
  * `duplicate_step`    the same step described twice ("Repeats step N")
  * `missing_info`      a process with no appeal or notification path

Nothing in this module is specific to any one college process: subjects, values
and wording are all derived from the stored text (Appendix rule 4).
"""
import hashlib
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from app.repositories.database import db

logger = logging.getLogger("processfoundry.agent.gaps")

VAGUE_TERMS = [
    "eligible", "appropriate", "as soon as possible", "timely", "proper", "reasonable", "as deemed fit"
]

CRITICAL_KINDS = ("conflicting_rules", "missing_actor")

# ---------------------------------------------------------------------------
# Subjects a conflict can be about. Each is a neutral noun plus the words that
# indicate a rule is talking about it. Editable in one place, like the routing
# table; no process name appears anywhere in it.
# ---------------------------------------------------------------------------
SUBJECT_CUES: Dict[str, Tuple[str, ...]] = {
    "deadline": ("deadline", "due date", "last date", "submit", "submitted", "submission",
                 "closes", "closing", "cut-off", "cutoff", "no later", "timeframe",
                 "accepted until", "until", "apply by", "lodge", "entertained", "late"),
    "fee": ("fee", "fees", "charge", "charges", "payment", "amount payable", "cost",
            "rupees", "inr", "usd", "dollar"),
    "limit": ("minimum", "maximum", "at least", "at most", "no more than", "no fewer than",
              "limit", "cap", "quota", "threshold", "percentage", "percent", "gpa",
              "grade point average", "marks", "score"),
    "duration": ("within", "days", "weeks", "months", "working days", "calendar days",
                 "duration", "period"),
}

# Value patterns, tried in order. The subject a value belongs to is decided by
# the surrounding words, not by the pattern.
VALUE_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("date", r"\b\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\b"),
    ("date", r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b"),
    ("date", r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    ("money", r"(?:rs\.?|inr|usd|\$|₹)\s?\d[\d,]*(?:\.\d+)?"),
    ("money", r"\b\d[\d,]*(?:\.\d+)?\s*(?:rupees|dollars)\b"),
    ("number", r"\b\d+(?:\.\d+)?\s*(?:per cent|percent|%)\b"),
    ("number", r"\b\d+(?:\.\d+)?\s*(?:calendar\s+days|working\s+days|days|weeks|months|years)\b"),
    ("number", r"\b\d+(?:\.\d+)?\b"),
)

# Words that show a process has a way to challenge or to tell people something.
APPEAL_CUES = ("appeal", "appeals", "grievance", "review of the decision", "reconsider",
               "objection", "complaint", "redress", "challenge the decision")
NOTIFY_CUES = ("notify", "notified", "notification", "inform", "informed", "intimate",
               "intimation", "communicate", "communicated", "e-mail the", "email the",
               "letter to", "notice to", "confirmation notice", "publish", "published")


def route_question_to_role(kind: str) -> str:
    """Deterministic routing table from Part 7.5."""
    if kind in ("conflicting_rules", "missing_actor", "ambiguous_term", "missing_info",
                "duplicate_step", "user_question"):
        return "process_owner"
    elif kind in ("parsing_error", "duplicate_evidence"):
        return "analyst"
    elif kind in ("technical_conflict", "architecture_issue"):
        return "technical_reviewer"
    return "process_owner"


def _letter(index: int) -> str:
    """Source badge letters A, B, C ... used by the question screen (brief 7.12 item 4)."""
    return chr(ord("A") + index) if 0 <= index < 26 else str(index + 1)


def _norm(text: Optional[str]) -> str:
    """Normalise free text for fingerprinting: lowercase, no punctuation, single spaces."""
    if not text:
        return ""
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", str(text).lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _source_key(src: Optional[Dict[str, Any]]) -> str:
    """Durable identity of a source passage: document plus section index."""
    if not src:
        return "nosource"
    return f"{_norm(src.get('document_name'))}#{src.get('section_index')}"


def fingerprint(kind: str, *parts: Any) -> str:
    """Build a fingerprint from durable identity, never from row UUIDs.

    Finding F3: fingerprints used to embed evidence/rule/step row ids. Every run
    re-created those rows with fresh UUIDs, so the same problem produced a new
    fingerprint, a new question, and a run that paused again for ever. Deriving
    the fingerprint from the document, the section index and the normalised text
    makes "the same problem" the same fingerprint across runs, which is what
    brief step 9 means by "Same problem twice = one question".
    """
    return "|".join([kind] + [_norm(str(p)) if not isinstance(p, int) else str(p) for p in parts])


def detect_subject(text: str) -> Optional[str]:
    """Which subject a rule is about, from its own words. None if unclear.

    Two rules are only compared when they are about the same subject, which is
    what stops the old O(n^2) sweep from inventing a conflict between every pair
    of unrelated numbers (finding F10).
    """
    lowered = (text or "").lower()
    best: Optional[str] = None
    best_hits = 0
    for subject, cues in SUBJECT_CUES.items():
        hits = sum(1 for cue in cues if cue in lowered)
        if hits > best_hits:
            best, best_hits = subject, hits
    return best


def extract_values(text: str, subject: Optional[str]) -> List[str]:
    """Comparable values in a rule, ordered by how specific the pattern is.

    Matched case-insensitively but returned with the source's own casing, so a
    question shows "31 March" exactly as the document wrote it.
    """
    source = text or ""
    wanted = {
        "deadline": ("date",),
        "fee": ("money", "number"),
        "limit": ("number", "money"),
        "duration": ("number",),
    }.get(subject or "", ("date", "money", "number"))

    found: List[str] = []
    seen = set()
    for kind, pattern in VALUE_PATTERNS:
        if kind not in wanted:
            continue
        for match in re.finditer(pattern, source, re.IGNORECASE):
            value = match.group(0).strip()
            key = _norm(value)
            if value and key not in seen:
                seen.add(key)
                found.append(value)
    return found


def _subject_for_value(value: str) -> str:
    """A neutral noun for a value whose rule gave no subject word."""
    lowered = value.lower()
    if re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december|/)", lowered):
        return "date"
    if re.search(r"(rs\.?|inr|usd|\$|₹|rupees|dollars)", lowered):
        return "amount"
    return "value"


def _same_statement(key_a: str, words_a: set, key_b: str, words_b: set) -> bool:
    """Whether two normalised sentences describe the same step."""
    if key_a == key_b:
        return True
    if key_a in key_b or key_b in key_a:
        return True
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / len(words_a | words_b)
    return overlap >= 0.75


def _values_conflict(a: str, b: str) -> bool:
    """Two values disagree if their numeric or textual content differs."""
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return False
    # "500" and "500 rupees" are the same amount stated differently.
    digits_a = re.sub(r"[^0-9.]", "", na)
    digits_b = re.sub(r"[^0-9.]", "", nb)
    if digits_a and digits_a == digits_b:
        return False
    return True


class GapAnalysisAgent:
    def detect_gaps_and_conflicts(
        self,
        project_id: str,
        process_steps: List[Dict[str, Any]],
        business_rules: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        run_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Run deterministic gap and conflict checks, generating structured questions."""
        questions_created: List[Dict[str, Any]] = []

        def record(item):
            if item:
                questions_created.append(item)

        # One query for the document/section context of every evidence item.
        ev_sources = db.get_evidence_sources(
            [str(e["id"]) for e in evidence_items if e.get("id")]
        )

        record_all = [
            self._check_missing_actors(project_id, process_steps, run_id),
            self._check_conflicting_rules(project_id, business_rules, run_id),
            self._check_ambiguous_terms(project_id, evidence_items, ev_sources, run_id),
            self._check_step_unknowns(project_id, process_steps, run_id),
            self._check_duplicate_steps(project_id, process_steps, run_id),
            self._check_duplicate_evidence(project_id, evidence_items, ev_sources, run_id),
            self._check_missing_paths(project_id, process_steps, evidence_items, ev_sources, run_id),
        ]
        for batch in record_all:
            for item in batch:
                record(item)

        return questions_created

    # -- Check 1: a step whose source names no actor -------------------------
    def _check_missing_actors(self, project_id, process_steps, run_id) -> List[Dict[str, Any]]:
        created = []
        for step in process_steps:
            if step.get("actor") is not None and "actor not stated" not in (step.get("unknowns") or []):
                continue

            step_name = step.get("name", "Unnamed Step")
            step_key = step.get("step_key", "Step")
            sources = db.get_step_sources(step["id"])
            fp = fingerprint(
                "missing_actor",
                _source_key(sources[0] if sources else None),
                _norm(step_name),
            )

            if sources:
                src = sources[0]
                reason = (
                    f"{step_key} in {src.get('document_name')} "
                    f"(section {src.get('section_index')}: {src.get('section_title')}) "
                    "does not say who does this."
                )
            else:
                reason = f"{step_key} does not say which role or actor is responsible."

            options = [{
                "label": "Name the role that does this",
                "letter": None,
                "is_ai_suggestion": False,
            }]
            for i, src in enumerate(sources[:3]):
                options.append({
                    "label": f"As stated in {src.get('document_name')}",
                    "letter": _letter(i),
                    "quote": src.get("quote"),
                    "document_name": src.get("document_name"),
                    "section_index": src.get("section_index"),
                    "section_title": src.get("section_title"),
                    "page_number": src.get("page_number"),
                    "is_ai_suggestion": False,
                })

            created.append(db.save_clarification_item(
                project_id=project_id,
                question=f"Who performs step '{step_name}'?",
                reason=reason,
                kind="missing_actor",
                assigned_role=route_question_to_role("missing_actor"),
                options=options,
                fingerprint=fp,
                ai_suggestion=(
                    "AI suggestion, not a fact: the source names no actor. Only the "
                    "Process Owner knows who really does this."
                ),
                run_id=run_id,
                link_targets=[("step", step["id"])] + [("evidence", s["id"]) for s in sources],
            ))
        return created

    # -- Check 2: two rules giving different values for the same subject -----
    def _check_conflicting_rules(self, project_id, business_rules, run_id) -> List[Dict[str, Any]]:
        """One question per subject, listing every distinct value (finding F10).

        The old version compared every pair of date-bearing rules and raised a
        question per differing pair, so the number of questions grew with the
        square of the number of rules (29 from one 20-section document), and it
        asserted "submission deadline" even when the dates were nothing of the
        kind. Now rules are grouped by the subject their own words identify, and
        each subject yields at most one question with one lettered option per
        distinct value, which is also what brief 7.12 item 5 asks for.
        """
        # subject -> normalised value -> (rule, display value)
        grouped: Dict[str, Dict[str, Tuple[Dict[str, Any], str]]] = {}
        for rule in business_rules:
            text = " ".join([
                rule.get("description") or "",
                " ".join(rule.get("evidence_quotes") or []),
                str((rule.get("condition_json") or {}).get("condition") or ""),
                str((rule.get("condition_json") or {}).get("outcome") or ""),
            ])
            values = []
            subject = detect_subject(text)
            if subject:
                values = extract_values(text, subject)
            if not values:
                # No subject word, but a date or an amount is still comparable:
                # fall back to the value's own type as a neutral subject noun.
                values = extract_values(text, None)
                if not values:
                    continue
                subject = _subject_for_value(values[0])
            bucket = grouped.setdefault(subject, {})
            key = _norm(values[0])
            bucket.setdefault(key, (rule, values[0]))

        created = []
        for subject, bucket in grouped.items():
            if len(bucket) < 2:
                continue
            entries = list(bucket.values())
            # Keep only genuinely different values ("500" vs "500 rupees" is one).
            distinct: List[Tuple[Dict[str, Any], str]] = []
            for rule, value in entries:
                if all(_values_conflict(value, kept_value) for _, kept_value in distinct):
                    distinct.append((rule, value))
            if len(distinct) < 2:
                continue
            created.append(self._raise_conflict(project_id, subject, distinct, run_id))
        return created

    def _raise_conflict(self, project_id, subject, entries: List[Tuple[Dict[str, Any], str]], run_id):
        """Build one conflict question with one lettered option per source."""
        options = []
        link_targets = []
        fingerprint_sides = []
        described = []

        for index, (rule, value) in enumerate(entries):
            src = (rule.get("sources") or [{}])[0]
            doc = src.get("document_name") or rule.get("document_name") or "the source document"
            sec = src.get("section_title") or rule.get("section_title") or "an untitled section"
            quote = src.get("quote") or (rule.get("evidence_quotes") or [rule.get("description")])[0]
            options.append({
                "label": value,
                "letter": _letter(index),
                "quote": quote,
                "document_name": doc,
                "section_index": src.get("section_index"),
                "section_title": sec,
                "page_number": src.get("page_number"),
                "is_ai_suggestion": False,
            })
            link_targets.append(("rule", rule["id"]))
            if src.get("id"):
                link_targets.append(("evidence", src["id"]))
            fingerprint_sides.append(f"{_source_key(src)}={_norm(value)}")
            described.append((value, doc, sec))

        options.append(
            {"label": f"Another {subject} or rule", "letter": None, "is_ai_suggestion": False}
        )

        values = [v for v, _, _ in described]
        question = f"Which {subject} is correct: " + " or ".join(values) + "?"

        docs = {d for _, d, _ in described}
        if len(docs) == 1:
            only_doc = next(iter(docs))
            places = ", ".join(f"'{v}' in section {s}" for v, _, s in described)
            reason = f"{len(described)} places in {only_doc} give different {subject}s: {places}."
        else:
            places = ", ".join(f"'{v}' in {d} ({s})" for v, d, s in described)
            reason = f"The sources give different {subject}s: {places}."

        return db.save_clarification_item(
            project_id=project_id,
            question=question,
            reason=reason,
            kind="conflicting_rules",
            assigned_role=route_question_to_role("conflicting_rules"),
            options=options,
            fingerprint=fingerprint("conflicting_rules", subject, *sorted(fingerprint_sides)),
            ai_suggestion=(
                "AI suggestion, not a fact: the sources disagree and the system cannot "
                "tell which is current. Only the Process Owner can decide."
            ),
            run_id=run_id,
            link_targets=link_targets,
        )

    # -- Check 3: vague terms ------------------------------------------------
    def _check_ambiguous_terms(self, project_id, evidence_items, ev_sources, run_id) -> List[Dict[str, Any]]:
        created = []
        for ev in evidence_items:
            quote_lower = (ev.get("quote") or "").lower()
            for term in VAGUE_TERMS:
                if not re.search(rf"\b{re.escape(term)}\b", quote_lower):
                    continue
                src = ev_sources.get(str(ev["id"]), {})
                where = ""
                if src.get("document_name"):
                    where = (
                        f" It appears in {src.get('document_name')}, "
                        f"section {src.get('section_index')}: {src.get('section_title')}."
                    )
                created.append(db.save_clarification_item(
                    project_id=project_id,
                    question=f'What does "{term}" mean here?',
                    reason=(
                        f'The source text says: "{ev.get("quote")}". '
                        f'The term "{term}" is open to subjective interpretation.{where}'
                    ),
                    kind="ambiguous_term",
                    assigned_role=route_question_to_role("ambiguous_term"),
                    options=[
                        {
                            "label": f'Define "{term}" for this process',
                            "letter": "A",
                            "quote": src.get("quote") or ev.get("quote"),
                            "document_name": src.get("document_name"),
                            "section_index": src.get("section_index"),
                            "section_title": src.get("section_title"),
                            "page_number": src.get("page_number"),
                            "is_ai_suggestion": False,
                        },
                        {
                            "label": "Leave it to the deciding officer's discretion",
                            "letter": None,
                            "is_ai_suggestion": False,
                        },
                    ],
                    fingerprint=fingerprint(
                        "ambiguous_term", _source_key(src), term, _norm(ev.get("quote"))
                    ),
                    ai_suggestion=(
                        f'AI suggestion, not a fact: a measurable criterion (a number, a '
                        f'document or a grade) would remove the ambiguity in "{term}".'
                    ),
                    run_id=run_id,
                    link_targets=[("evidence", ev["id"])],
                ))
                break  # at most one vague term per evidence item
        return created

    # -- Check 4: a step carrying unknowns other than the actor --------------
    def _check_step_unknowns(self, project_id, process_steps, run_id) -> List[Dict[str, Any]]:
        """`missing_info` questions, which brief step 9 and SPEC-07-01 require.

        This detector did not exist at all (finding F10), although the kind was
        already in the schema and in the Pydantic literal.
        """
        created = []
        for step in process_steps:
            unknowns = [u for u in (step.get("unknowns") or []) if u != "actor not stated"]
            if not unknowns:
                continue
            step_key = step.get("step_key", "Step")
            step_name = step.get("name", "this step")
            sources = db.get_step_sources(step["id"])
            src = sources[0] if sources else {}
            detail = "; ".join(str(u) for u in unknowns)

            created.append(db.save_clarification_item(
                project_id=project_id,
                question=f"What is missing for '{step_name}'?",
                reason=(
                    f"{step_key} is recorded with unresolved details: {detail}. "
                    + (
                        f"It comes from {src.get('document_name')}, section "
                        f"{src.get('section_index')}: {src.get('section_title')}."
                        if src.get("document_name") else
                        "The source does not state them."
                    )
                ),
                kind="missing_info",
                assigned_role=route_question_to_role("missing_info"),
                options=[
                    {"label": "Supply the missing detail", "letter": None, "is_ai_suggestion": False},
                    {
                        "label": f"As stated in {src.get('document_name')}" if src.get("document_name")
                                 else "Leave it unspecified",
                        "letter": "A" if src.get("quote") else None,
                        "quote": src.get("quote"),
                        "document_name": src.get("document_name"),
                        "section_index": src.get("section_index"),
                        "section_title": src.get("section_title"),
                        "page_number": src.get("page_number"),
                        "is_ai_suggestion": False,
                    },
                ],
                fingerprint=fingerprint(
                    "missing_info", _source_key(src), _norm(step_name), _norm(detail)
                ),
                ai_suggestion=None,
                run_id=run_id,
                link_targets=[("step", step["id"])] + [("evidence", s["id"]) for s in sources[:1]],
            ))
        return created

    # -- Check 5: the same step described twice ------------------------------
    def _check_duplicate_evidence(self, project_id, evidence_items, ev_sources, run_id) -> List[Dict[str, Any]]:
        """The same step stated in two different sections is a repeated step.

        Matching is deliberately tolerant: a document often repeats a step with a
        small lead-in ("After initial screening, the clerk cross-checks ..." vs
        "The clerk cross-checks ..."). Exact equality would miss that, so two
        passages count as the same step when one normalised sentence contains the
        other, or when they share at least 75% of their words.
        """
        candidates = []
        for ev in evidence_items:
            key = _norm(ev.get("quote"))
            if len(key) < 30:          # ignore short, incidental repeats
                continue
            src = ev_sources.get(str(ev["id"]), {})
            if src.get("section_index") is None:
                continue
            candidates.append((ev, src, key, set(key.split())))

        used = set()
        clusters = []
        for i, (ev_a, src_a, key_a, words_a) in enumerate(candidates):
            if i in used:
                continue
            cluster = [(ev_a, src_a, key_a)]
            for j in range(i + 1, len(candidates)):
                if j in used:
                    continue
                ev_b, src_b, key_b, words_b = candidates[j]
                if src_b.get("section_index") == src_a.get("section_index"):
                    continue   # one section repeating itself is not a process repeat
                if _same_statement(key_a, words_a, key_b, words_b):
                    cluster.append((ev_b, src_b, key_b))
                    used.add(j)
            if len(cluster) > 1:
                used.add(i)
                clusters.append(cluster)

        created = []
        for cluster in clusters:
            sources = [src for _, src, _ in cluster]
            sections = sorted(
                s.get("section_index") for s in sources if s.get("section_index") is not None
            )
            quote = cluster[0][0].get("quote")
            where = ", ".join(
                f"section {s.get('section_index')}: {s.get('section_title')}"
                for s in sources if s.get("section_index") is not None
            )
            # The shortest normalised form is the stable identity of the cluster.
            identity = min(key for _, _, key in cluster)

            created.append(db.save_clarification_item(
                project_id=project_id,
                question="Is this step really done twice, or is it written twice?",
                reason=(
                    f'The same step appears in more than one place: "{quote}" '
                    f"({where}). Repeats step {sections[0]}."
                ),
                kind="duplicate_step",
                assigned_role=route_question_to_role("duplicate_step"),
                options=[
                    {"label": "Yes, the work really happens twice", "letter": None, "is_ai_suggestion": False},
                    {"label": "No, it is the same work written twice", "letter": None, "is_ai_suggestion": False},
                ] + [
                    {
                        "label": f"As stated in section {s.get('section_index')}",
                        "letter": _letter(i),
                        "quote": s.get("quote"),
                        "document_name": s.get("document_name"),
                        "section_index": s.get("section_index"),
                        "section_title": s.get("section_title"),
                        "page_number": s.get("page_number"),
                        "is_ai_suggestion": False,
                    }
                    for i, s in enumerate(sources[:3])
                ],
                fingerprint=fingerprint("duplicate_step", "repeated_statement", identity),
                ai_suggestion=None,
                run_id=run_id,
                link_targets=[("evidence", ev["id"]) for ev, _, _ in cluster[:3]],
            ))
        return created

    def _check_duplicate_steps(self, project_id, process_steps, run_id) -> List[Dict[str, Any]]:
        """Report a repeated step with the "Repeats step N" note from brief 10.5.

        Both fixtures plant a repeated step and `manifest.json` records it, but
        nothing detected it (finding F10).
        """
        created = []
        seen: Dict[str, Dict[str, Any]] = {}
        for step in sorted(process_steps, key=lambda s: s.get("sequence") or 0):
            key = _norm(step.get("name"))
            if not key or len(key) < 10:
                continue
            if key not in seen:
                seen[key] = step
                continue

            first = seen[key]
            first_seq = first.get("sequence") or 0
            dup_seq = step.get("sequence") or 0
            sources = db.get_step_sources(step["id"]) or db.get_step_sources(first["id"])
            src = sources[0] if sources else {}

            created.append(db.save_clarification_item(
                project_id=project_id,
                question=(
                    f"Step {dup_seq} repeats step {first_seq}. Is it really done twice?"
                ),
                reason=(
                    f"'{step.get('name')}' appears as step {first_seq} and again as "
                    f"step {dup_seq}. Repeats step {first_seq}."
                    + (
                        f" Both come from {src.get('document_name')}."
                        if src.get("document_name") else ""
                    )
                ),
                kind="duplicate_step",
                assigned_role=route_question_to_role("duplicate_step"),
                options=[
                    {"label": "Yes, the work really happens twice", "letter": None, "is_ai_suggestion": False},
                    {"label": f"No, step {dup_seq} is the same work written twice", "letter": None, "is_ai_suggestion": False},
                    {
                        "label": "As stated in the source",
                        "letter": "A" if src.get("quote") else None,
                        "quote": src.get("quote"),
                        "document_name": src.get("document_name"),
                        "section_index": src.get("section_index"),
                        "section_title": src.get("section_title"),
                        "page_number": src.get("page_number"),
                        "is_ai_suggestion": False,
                    },
                ],
                fingerprint=fingerprint("duplicate_step", _source_key(src), key),
                ai_suggestion=None,
                run_id=run_id,
                link_targets=[("step", first["id"]), ("step", step["id"])],
            ))
        return created

    # -- Check 6: no appeal or notification path -----------------------------
    def _check_missing_paths(self, project_id, process_steps, evidence_items, ev_sources, run_id) -> List[Dict[str, Any]]:
        """Report a process with no way to appeal, or no way to tell anyone.

        `manifest.json` plants exactly this ("No appeal procedure for rejected
        applicants", "No room change appeal path") and nothing looked for it
        (finding F10).
        """
        if not process_steps and not evidence_items:
            return []

        haystack = " ".join(
            [_norm(s.get("name")) for s in process_steps]
            + [_norm(s.get("step_type")) for s in process_steps]
            + [_norm(e.get("quote")) for e in evidence_items]
            + [_norm(e.get("claim")) for e in evidence_items]
        )

        created = []
        for path_name, cues, question, what_is_missing in (
            (
                "appeal",
                APPEAL_CUES,
                "How can a person challenge the outcome of this process?",
                "No appeal, review or grievance path is described anywhere in the sources",
            ),
            (
                "notification",
                NOTIFY_CUES,
                "How is the outcome communicated to the person affected?",
                "No step describes notifying or informing the person of the outcome",
            ),
        ):
            if any(_norm(cue) in haystack for cue in cues):
                continue
            created.append(db.save_clarification_item(
                project_id=project_id,
                question=question,
                reason=(
                    f"{what_is_missing}. It would normally be stated alongside the "
                    "decision step, so either the sources are silent or a document is missing."
                ),
                kind="missing_info",
                assigned_role=route_question_to_role("missing_info"),
                options=[
                    {"label": f"Describe the {path_name} path", "letter": None, "is_ai_suggestion": False},
                    {"label": f"There is deliberately no {path_name} path", "letter": None, "is_ai_suggestion": False},
                    {"label": "It is in a document not yet uploaded", "letter": None, "is_ai_suggestion": False},
                ],
                fingerprint=fingerprint("missing_info", "process_path", path_name),
                ai_suggestion=None,
                run_id=run_id,
                link_targets=[],
            ))
        return created


gap_analysis_agent = GapAnalysisAgent()
