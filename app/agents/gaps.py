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
import unicodedata
from typing import List, Dict, Any, Optional, Tuple

from app.repositories.database import db

logger = logging.getLogger("processfoundry.agent.gaps")

VAGUE_TERMS = [
    "eligible", "appropriate", "as soon as possible", "timely", "proper", "reasonable", "as deemed fit",
    # Hindi and Marathi vague subjective criteria
    "\u092a\u093e\u0924\u094d\u0930",       # patra (eligible)
    "\u092f\u094b\u0917\u094d\u092f",       # yogya (appropriate)
    "\u0932\u0935\u0915\u0930\u093e\u0924 \u0932\u0935\u0915\u0930",  # lavkarat lavkar (ASAP)
    "\u092f\u0925\u093e\u0936\u0940\u0918\u094d\u0930",  # yathasighra (promptly)
    "\u0935\u093e\u091c\u0935\u0940",       # vajavi (reasonable)
    "\u0909\u091a\u093f\u0924",             # uchit (appropriate)
    "\u0935\u0947\u0933\u0947\u0935\u0930", # velevara (on time)
    "\u0938\u092e\u092f\u092c\u0926\u094d\u0927",  # samayabaddha (time-bound)
    "\u092f\u094b\u0917\u094d\u092f \u0935\u093e\u091f\u0947\u0932 \u0924\u094d\u092f\u093e\u0928\u0941\u0938\u093e\u0930",  # as deemed fit
    "\u092f\u0925\u093e\u092f\u094b\u0917\u094d\u092f",  # yathayogya (as appropriate)
]

CRITICAL_KINDS = ("conflicting_rules", "missing_actor")

# ---------------------------------------------------------------------------
# Subjects a conflict can be about. Each is a neutral noun plus the words that
# indicate a rule is talking about it. Editable in one place, like the routing
# table; no process name appears anywhere in it.
# ---------------------------------------------------------------------------
SUBJECT_CUES: Dict[str, Tuple[str, ...]] = {
    "deadline": (
        "deadline", "due date", "last date", "submit", "submitted", "submission",
        "closes", "closing", "cut-off", "cutoff", "no later", "timeframe",
        "accepted until", "until", "apply by", "lodge", "entertained", "late",
        # Hindi and Marathi cues
        "\u0905\u0902\u0924\u093f\u092e \u0924\u093e\u0930\u0940\u0916",     # antim tarik (last date)
        "\u0936\u0947\u0935\u091f\u091a\u0940 \u0924\u093e\u0930\u0940\u0916",  # shevtachi tarik
        "\u092e\u0941\u0926\u0924",             # mudat (deadline)
        "\u0905\u0902\u0924\u093f\u092e \u092e\u0941\u0926\u0924",           # antim mudat
        "\u0905\u0902\u0924\u093f\u092e \u0926\u093f\u0928\u093e\u0902\u0915",  # antim dinank
        "\u0938\u093e\u0926\u0930",             # sadar (submit)
        "\u0938\u094d\u0935\u0940\u0915\u093e\u0930",  # swikara (accept)
        "\u0905\u0930\u094d\u091c \u0915\u0930\u0923\u094d\u092f\u093e\u091a\u0940 \u0924\u093e\u0930\u0940\u0916",  # arj karnyachi tarik
        "\u0935\u093f\u0932\u0902\u092c",       # vilamb (delay/late)
        "\u0928\u0902\u0924\u0930",             # nantar (after)
    ),
    "fee": (
        "fee", "fees", "charge", "charges", "payment", "amount payable", "cost",
        "rupees", "inr", "usd", "dollar",
        # Hindi and Marathi cues
        "\u0936\u0941\u0932\u094d\u0915",       # shulka (fee)
        "\u092b\u0940",                         # fee
        "\u0930\u0915\u094d\u0915\u092e",       # rakkam (amount)
        "\u0930\u0941\u092a\u092f\u0947",       # rupaye (rupees)
        "\u0930\u0941\u092a\u092f\u093e",       # rupaya
        "\u0930\u0941.",                        # ru. (rupee abbr)
        "\u0930\u0941",                         # ru
        "\u0916\u0930\u094d\u091a",             # kharch (expense)
        "\u0926\u0947\u092f",                   # dey (payable)
    ),
    "limit": (
        "minimum", "maximum", "at least", "at most", "no more than", "no fewer than",
        "limit", "cap", "quota", "threshold", "percentage", "percent", "gpa",
        "grade point average", "marks", "score",
        # Hindi and Marathi cues
        "\u0915\u093f\u092e\u093e\u0928",       # kiman (minimum)
        "\u0915\u092e\u093e\u0932",             # kamal (maximum)
        "\u092e\u0930\u094d\u092f\u093e\u0926\u093e",  # maryada (limit)
        "\u091f\u0915\u094d\u0915\u0947",       # takke (percent)
        "\u091f\u0915\u094d\u0915\u0947\u0935\u093e\u0930\u0940",  # takkevari (percentage)
        "\u0917\u0941\u0923",                   # gun (marks)
        "\u0915\u092e\u0940\u0924 \u0915\u092e\u0940",  # kamit kami (at least)
        "\u091c\u093e\u0938\u094d\u0924\u0940\u0924 \u091c\u093e\u0938\u094d\u0924",  # jastit jast (at most)
    ),
    "duration": (
        "within", "days", "weeks", "months", "working days", "calendar days",
        "duration", "period",
        # Hindi and Marathi cues
        "\u0915\u093e\u0932\u093e\u0935\u0927\u0940",  # kalavadhi (period)
        "\u0926\u093f\u0935\u0938",             # divas (days)
        "\u0906\u0920\u0935\u0921\u0947",       # aathavade (weeks)
        "\u092e\u0939\u093f\u0928\u0947",       # mahine (months)
        "\u0915\u093e\u0930\u094d\u092f\u0926\u093f\u0928",  # karyadina (working days)
        "\u0915\u093e\u092e\u093e\u091a\u0947 \u0926\u093f\u0935\u0938",  # kamache divas
        "\u0926\u093f\u0935\u0938\u093e\u0902\u091a\u094d\u092f\u093e \u0906\u0924",  # divasanachya aat (within days)
        "\u092e\u0941\u0926\u0924\u0940\u0924",  # mudatit (within deadline)
    ),
}

# Value patterns, tried in order. The subject a value belongs to is decided by
# the surrounding words, not by the pattern. Supports English, Hindi, and Marathi formats.
_MONTHS_EN = r"january|february|march|april|may|june|july|august|september|october|november|december"
_MONTHS_HI_MR = (
    # Marathi month names
    "\u091c\u093e\u0928\u0947\u0935\u093e\u0930\u0940|\u092b\u0947\u092c\u094d\u0930\u0941\u0935\u093e\u0930\u0940"
    "|\u092e\u093e\u0930\u094d\u091a|\u090f\u092a\u094d\u0930\u093f\u0932|\u092e\u0947|\u091c\u0942\u0928"
    "|\u091c\u0941\u0932\u0948|\u0911\u0917\u0938\u094d\u091f|\u0938\u092a\u094d\u091f\u0947\u0902\u092c\u0930"
    "|\u0911\u0915\u094d\u091f\u094b\u092c\u0930|\u0928\u094b\u0935\u094d\u0939\u0947\u0902\u092c\u0930"
    "|\u0921\u093f\u0938\u0947\u0902\u092c\u0930|"
    # Hindi month names
    "\u091c\u0928\u0935\u0930\u0940|\u092b\u0930\u0935\u0930\u0940|\u092b\u093c\u0930\u0935\u0930\u0940"
    "|\u092e\u093e\u0930\u094d\u091a|\u0905\u092a\u094d\u0930\u0948\u0932|\u092e\u0908|\u091c\u0942\u0928"
    "|\u091c\u0941\u0932\u093e\u0908|\u0905\u0917\u0938\u094d\u0924|\u0938\u093f\u0924\u0902\u092c\u0930"
    "|\u0905\u0915\u094d\u091f\u0942\u092c\u0930|\u0928\u0935\u0902\u092c\u0930|\u0926\u093f\u0938\u0902\u092c\u0930"
)
_MONTHS_ALL = rf"(?:{_MONTHS_EN}|{_MONTHS_HI_MR})"

VALUE_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("date", rf"(?<![\w\u0900-\u097F])[0-9\u0966-\u096F]{{1,2}}\s+{_MONTHS_ALL}(?![\w\u0900-\u097F])"),
    ("date", rf"(?<![\w\u0900-\u097F]){_MONTHS_ALL}\s+[0-9\u0966-\u096F]{{1,2}}(?![\w\u0900-\u097F])"),
    ("date", r"(?<![\w\u0900-\u097F])[0-9\u0966-\u096F]{1,2}[/-][0-9\u0966-\u096F]{1,2}[/-][0-9\u0966-\u096F]{2,4}(?![\w\u0900-\u097F])"),
    ("money", r"(?:rs\.?|inr|usd|\$|\u20b9|\u0930\u0941\.?|\u0930\u0941)\s?[0-9\u0966-\u096F][0-9\u0966-\u096F,]*(?:\.[0-9\u0966-\u096F]+)?"),
    ("money", r"(?<![\w\u0900-\u097F])[0-9\u0966-\u096F][0-9\u0966-\u096F,]*(?:\.[0-9\u0966-\u096F]+)?\s*(?:rupees|dollars|\u0930\u0941\u092a\u092f\u0947|\u0930\u0941\u092a\u092f\u093e)(?![\w\u0900-\u097F])"),
    ("number", r"(?<![\w\u0900-\u097F])[0-9\u0966-\u096F]+(?:\.[0-9\u0966-\u096F]+)?\s*(?:per cent|percent|%|\u091f\u0915\u094d\u0915\u0947|\u091f\u0915\u094d\u0915\u0947\u0935\u093e\u0930\u0940)(?![\w\u0900-\u097F])"),
    ("number", r"(?<![\w\u0900-\u097F])[0-9\u0966-\u096F]+(?:\.[0-9\u0966-\u096F]+)?\s*(?:calendar\s+days|working\s+days|days|weeks|months|years|\u0926\u093f\u0935\u0938|\u0915\u093e\u0930\u094d\u092f\u0926\u093f\u0928|\u0906\u0920\u0935\u0921\u0947|\u092e\u0939\u093f\u0928\u0947|\u0935\u0930\u094d\u0937)(?![\w\u0900-\u097F])"),
    ("number", r"(?<![\w\u0900-\u097F])[0-9\u0966-\u096F]+(?:\.[0-9\u0966-\u096F]+)?(?![\w\u0900-\u097F])"),
)

# Words that show a process has a way to challenge or to tell people something.
APPEAL_CUES = (
    "appeal", "appeals", "grievance", "review of the decision", "reconsider",
    "objection", "complaint", "redress", "challenge the decision",
    # Hindi and Marathi cues
    "\u0905\u092a\u0940\u0932",             # appeal
    "\u0924\u0915\u094d\u0930\u093e\u0930", # taksrar (complaint)
    "\u0906\u0915\u094d\u0937\u0947\u092a", # aksep (objection)
    "\u092b\u0947\u0930\u0935\u093f\u091a\u093e\u0930",  # feravichar (reconsideration)
    "\u092a\u0941\u0928\u0930\u094d\u0935\u093f\u091a\u093e\u0930",  # punarvichar (reconsideration)
    "\u0928\u093f\u0935\u093e\u0930\u0923",  # nivaran (redress)
    "\u0926\u093e\u0926",                   # daad (redress/relief)
)
NOTIFY_CUES = (
    "notify", "notified", "notification", "inform", "informed", "intimate",
    "intimation", "communicate", "communicated", "e-mail the", "email the",
    "letter to", "notice to", "confirmation notice", "publish", "published",
    # Hindi and Marathi cues
    "\u0915\u0933\u0935\u0923\u0947",       # kalavane (to notify)
    "\u0915\u0933\u0935\u0932\u0947",       # kalavale (notified)
    "\u0938\u0942\u091a\u093f\u0924",       # suchit (intimated)
    "\u0938\u0942\u091a\u0928\u093e",       # suchana (notice/notification)
    "\u0908\u092e\u0947\u0932",             # email
    "\u092a\u0924\u094d\u0930",             # patra (letter)
    "\u092a\u094d\u0930\u0938\u093f\u0926\u094d\u0927",  # prasiddha (published)
    "\u092e\u093e\u0939\u093f\u0924\u0940", # mahiti (information)
    "\u0938\u0902\u0926\u0947\u0936",       # sandesh (message)
    "\u0905\u0935\u0917\u0924",             # avgat (informed)
)


# Use code-point arithmetic to avoid encoding issues in the source file.
_DEVANAGARI_DIGITS = str.maketrans({chr(0x0966 + i): str(i) for i in range(10)})


def _to_ascii_digits(text: str) -> str:
    """Normalize Devanagari numerals to standard ASCII digits."""
    return text.translate(_DEVANAGARI_DIGITS)


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
    """Normalise free text for fingerprinting: lowercase, no punctuation, single spaces.

    Preserves Unicode letters, combining marks/matras, and digits across scripts.
    """
    if not text:
        return ""
    # Keep Unicode letters (L), marks/matras (M), numbers (N); convert punctuation/symbols to space
    chars = [
        c if (unicodedata.category(c)[0] in ("L", "M", "N") or c.isspace()) else " "
        for c in str(text).lower()
    ]
    return re.sub(r"\s+", " ", "".join(chars)).strip()


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
            # A bare four-digit year (2017, 1988) names a period or a law, it is
            # not a deadline, fee or limit, so it is never compared as a value.
            if kind == "number" and re.fullmatch(r"[0-9]{4}", _to_ascii_digits(value)) \
                    and 1900 <= int(_to_ascii_digits(value)) <= 2100:
                continue
            if value and key not in seen:
                seen.add(key)
                found.append(value)
    return found


def _subject_for_value(value: str) -> str:
    """A neutral noun for a value whose rule gave no subject word."""
    lowered = value.lower()
    if re.search(
        rf"(?:{_MONTHS_ALL}|/|-)",
        lowered,
    ):
        return "date"
    if re.search(
        r"(rs\.?|inr|usd|\$|\u20b9|rupees|dollars|\u0930\u0941\u092a\u092f\u0947|\u0930\u0941\u092a\u092f\u093e|\u0930\u0941\.?|\u0930\u0941)",
        lowered,
    ):
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
    # Normalize Devanagari digits to ASCII digits
    na_digits = _to_ascii_digits(na)
    nb_digits = _to_ascii_digits(nb)
    if na_digits == nb_digits:
        return False
    # "500", "500 rupees", and "\u096b\u0966\u0966 \u0930\u0941\u092a\u092f\u0947" are the same amount stated differently.
    digits_a = re.sub(r"[^0-9.]", "", na_digits)
    digits_b = re.sub(r"[^0-9.]", "", nb_digits)
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
            # A step whose only source is its own heading (e.g. a phase title) has
            # no action text to name an actor in; the real actions are separate steps.
            if sources and _norm(sources[0].get("quote")) == _norm(step_name):
                continue
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
            # Only real source text may be shown as a quote. The rule's own
            # description is the model's wording, so it is never used here.
            quote = src.get("quote") or (rule.get("evidence_quotes") or [None])[0]
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
        asked_terms = set()   # one question per term; the answer defines it everywhere
        for ev in evidence_items:
            quote_lower = (ev.get("quote") or "").lower()
            for term in VAGUE_TERMS:
                if term in asked_terms:
                    continue
                if not re.search(rf"(?<![\w\u0900-\u097F]){re.escape(term)}(?![\w\u0900-\u097F])", quote_lower):
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
                asked_terms.add(term)
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
            unknowns = [
                u for u in (step.get("unknowns") or [])
                if u != "actor not stated" and "duplicate step" not in str(u).lower()
            ]
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
            # Rules, dates, deadlines and fees repeated in the text are not a step
            # done twice; conflicting values are caught by the rule checks.
            if (ev.get("claim_type") or "other") in ("rule", "date", "deadline", "fee"):
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
                # Text that recurs in five or more sections is a running header or
                # a title, not a step, so it is not worth a question.
                distinct_sections = {c[1].get("section_index") for c in cluster}
                if len(distinct_sections) >= 5:
                    continue
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
