"""ProcessFoundry AI: process-specific artifact generators (design doc A10, A12, section 3).

Deterministic code only: no model calls, so no API quota is used.

These build the Roles & Permissions Matrix, the UAT Pack, the HLD and the Data
Model from the project's own approved process steps and rules, instead of fixed
text. Every function returns None when there are no steps, so the caller can keep
its existing output unchanged.

Nothing here invents facts: names come from the steps, and anything the process
did not state is labelled "To be confirmed".
"""
import re
from typing import Any, Dict, List, Optional

TBC = "To be confirmed"
UNASSIGNED = "Unassigned (actor not stated - needs clarification)"


def _lst(v: Any) -> List[str]:
    return [str(x).strip() for x in (v or []) if str(x).strip()]


def _cell(text: Any) -> str:
    """Make text safe inside a Markdown table cell."""
    return str(text or "").replace("|", "/").replace("\r", " ").replace("\n", " ").strip()


def _step_key(s: Dict[str, Any], idx: int) -> str:
    return s.get("step_key") or f"STEP-{idx + 1:03d}"


def _actor(s: Dict[str, Any]) -> str:
    return (s.get("actor") or "").strip() or UNASSIGNED


def _ordered(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(steps or [], key=lambda s: (s.get("sequence") or 0))


def _ident(text: str) -> str:
    """CamelCase-ish identifier safe for Mermaid."""
    words = re.findall(r"[A-Za-z0-9]+", text or "")
    out = "".join(w.capitalize() for w in words[:4])
    if not out or out[0].isdigit():
        out = "E" + out
    return out


def _mermaid_label(text: str, limit: int = 45) -> str:
    t = re.sub(r"[\"\[\]\(\)\{\}<>|]", "", str(text or "")).strip()
    return (t[:limit] + "...") if len(t) > limit else t


def as_appendix(legacy_md: str) -> str:
    """Re-use an older fixed-text document as a clearly labelled appendix."""
    lines = (legacy_md or "").strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    body = "\n".join(("#" + l) if l.startswith("## ") else l for l in lines)
    return "## Appendix: ProcessFoundry platform (reference)\n" + body + "\n"


def _header(title: str, project: Dict[str, Any]) -> str:
    return f"# {title}\n**Project:** {project.get('name')}\n**Status:** DRAFT / NEEDS REVIEW\n\n"


# ---------------------------------------------------------------------------
# Roles and Permissions Matrix
# ---------------------------------------------------------------------------
def roles_matrix_md(project: Dict[str, Any], steps: List[Dict[str, Any]],
                    rules: List[Dict[str, Any]], platform_table: str) -> Optional[str]:
    steps = _ordered(steps)
    if not steps:
        return None

    actors: Dict[str, Dict[str, List[str]]] = {}
    for i, s in enumerate(steps):
        a = actors.setdefault(_actor(s), {"performs": [], "approves": [], "reads": [], "produces": []})
        key = _step_key(s, i)
        label = f"{key} {_cell(s.get('name'))}"
        a["performs"].append(label)
        if s.get("human_approval_required"):
            a["approves"].append(label)
        a["reads"].extend(_lst(s.get("inputs")))
        a["produces"].extend(_lst(s.get("outputs")))

    md = _header("Roles and Permissions Matrix", project)
    md += "## 1. Process roles\n"
    md += ("Roles are taken from the actors named in the approved process steps. "
           "Permissions below are derived from what each actor does in the process; "
           "access to anything not listed is **not granted** until confirmed.\n\n")
    md += "| Process role | Performs steps | Approval responsibility | Data they use (inputs) | Data they create (outputs) |\n|---|---|---|---|---|\n"
    for name, a in actors.items():
        md += (f"| {_cell(name)} | {_cell('; '.join(a['performs']))} | "
               f"{_cell('; '.join(a['approves']) or 'None stated')} | "
               f"{_cell(', '.join(dict.fromkeys(a['reads'])) or TBC)} | "
               f"{_cell(', '.join(dict.fromkeys(a['produces'])) or TBC)} |\n")

    md += "\n## 2. Action-level permissions\n"
    names = list(actors.keys())
    md += "| Step | Action | " + " | ".join(_cell(n) for n in names) + " |\n"
    md += "|---|---|" + "---|" * len(names) + "\n"
    for i, s in enumerate(steps):
        who = _actor(s)
        row = []
        for n in names:
            if n == who:
                row.append("Approve" if s.get("human_approval_required") else "Perform")
            else:
                row.append("-")
        md += f"| {_step_key(s, i)} | {_cell(s.get('name'))} | " + " | ".join(row) + " |\n"

    unassigned = [f"{_step_key(s, i)}" for i, s in enumerate(steps) if _actor(s) == UNASSIGNED]
    if unassigned:
        md += ("\n## 3. Open items\n"
               f"- Steps with no stated actor: {', '.join(unassigned)}. "
               "Ask the Process Owner who performs them.\n")

    if rules:
        md += "\n## 4. Rules that constrain roles\n"
        for r in rules[:15]:
            md += f"- **{r.get('rule_key')}**: {_cell(r.get('description'))}\n"

    md += "\n## Appendix: ProcessFoundry platform roles\n" + platform_table
    return md


# ---------------------------------------------------------------------------
# UAT Pack
# ---------------------------------------------------------------------------
def uat_md(project: Dict[str, Any], steps: List[Dict[str, Any]],
           rules: List[Dict[str, Any]]) -> Optional[str]:
    steps = _ordered(steps)
    if not steps:
        return None

    md = _header("User Acceptance Testing (UAT) Pack", project)
    md += ("Scenarios are generated from the approved process steps and business rules. "
           "Reviewer outcome fields are blank until a person completes them.\n\n")
    md += "| Scenario ID | Linked to | User persona | Starting conditions | Action | Expected outcome | Actual outcome | Pass/Fail | Reviewer |\n"
    md += "|---|---|---|---|---|---|---|---|---|\n"

    n = 0
    prev_outputs: List[str] = []
    for i, s in enumerate(steps):
        n += 1
        start = _lst(s.get("inputs")) or prev_outputs
        outs = _lst(s.get("outputs"))
        expected = ", ".join(outs) if outs else TBC
        if s.get("human_approval_required"):
            expected += " (decision recorded with reviewer name and time)"
        md += (f"| UAT-{n:03d} | {_step_key(s, i)} | {_cell(_actor(s))} | "
               f"{_cell(', '.join(start) + ' available' if start else TBC)} | "
               f"{_cell(s.get('name'))} | {_cell(expected)} |  | [ ] |  |\n")
        prev_outputs = outs or prev_outputs

    for r in rules[:10]:
        cond = (r.get("condition_json") or {})
        n += 1
        md += (f"| UAT-{n:03d} | {r.get('rule_key')} | Any process participant | "
               f"{_cell(cond.get('condition') or TBC)} | Attempt the action the rule governs | "
               f"{_cell(cond.get('outcome') or r.get('description'))} |  | [ ] |  |\n")

    n += 1
    md += (f"| UAT-{n:03d} | Access control | Person not on the project | Signed in, not a project member | "
           "Open the project | Access denied |  | [ ] |  |\n")
    return md


# ---------------------------------------------------------------------------
# HLD
# ---------------------------------------------------------------------------
def hld_md(project: Dict[str, Any], steps: List[Dict[str, Any]],
           rules: List[Dict[str, Any]], platform_appendix: str) -> Optional[str]:
    steps = _ordered(steps)
    if not steps:
        return None

    all_text = " ".join(
        [str(s.get("name", "")) for s in steps]
        + [" ".join(_lst(s.get("inputs")) + _lst(s.get("outputs"))) for s in steps]
        + [str(s.get("step_type", "")) for s in steps]
    ).lower()
    actors = list(dict.fromkeys(_actor(s) for s in steps))
    has_docs = any(w in all_text for w in ("document", "certificate", "form", "upload", "proof", "receipt"))
    has_notify = any(w in all_text for w in ("notif", "email", "sms", "alert", "intimat", "inform"))
    has_payment = any(w in all_text for w in ("fee", "payment", "challan", "receipt", "refund"))
    has_approval = any(s.get("human_approval_required") for s in steps)
    automated = [s for s in steps if (s.get("automation") or "") in ("deterministic", "ai_assisted", "hybrid")]

    md = _header("Solution Architecture / High-Level Design (HLD)", project)
    md += "**Version:** 1.0\n\n"
    md += ("> Components below are proposed from the approved process. Integrations with college systems "
           "(ERP, payment gateway, identity) are **not assumed to exist**; they are listed as candidates to confirm.\n\n")

    md += "## 1. Process flow\n```mermaid\nflowchart TD\n"
    for i, s in enumerate(steps):
        node = f"S{i + 1}"
        md += f'    {node}["{_step_key(s, i)}: {_mermaid_label(s.get("name"))}<br/>({_mermaid_label(_actor(s), 30)})"]\n'
    for i in range(len(steps) - 1):
        md += f"    S{i + 1} --> S{i + 2}\n"
    md += "```\n\n"

    md += "## 2. Proposed components\n| Component | Why it is needed | Evidence in the process |\n|---|---|---|\n"
    md += "| Web portal | Actors interact with the process | Actors: " + _cell(", ".join(actors)) + " |\n"
    md += f"| Workflow engine | Moves requests between {len(steps)} steps | Step sequence above |\n"
    if rules:
        md += f"| Rule validation service | Enforces {len(rules)} business rule(s) deterministically | Rules catalogue |\n"
    if has_approval:
        md += "| Approval and decision log | Records who approved what and when | Steps requiring human approval |\n"
    if has_docs:
        md += "| Document storage | Holds submitted forms and supporting documents | Document-type inputs/outputs |\n"
    if has_notify:
        md += "| Notification service | Informs applicants/reviewers of status | Notification wording in steps |\n"
    if has_payment:
        md += "| Payment integration (candidate) | Fee handling is mentioned; confirm if online payment is in scope | Fee/payment wording |\n"
    if automated:
        md += f"| Automation layer | {len(automated)} step(s) classified for automation | Automation column in To-Be |\n"
    md += "| Audit log | Immutable record of actions | Required for approvals and traceability |\n"

    md += "\n## 3. Data flow\n"
    for i, s in enumerate(steps):
        ins = ", ".join(_lst(s.get("inputs"))) or TBC
        outs = ", ".join(_lst(s.get("outputs"))) or TBC
        md += f"- {_step_key(s, i)} ({_cell(_actor(s))}): **in** {_cell(ins)} -> **out** {_cell(outs)}\n"

    md += ("\n## 4. Security boundaries\n"
           "- Each actor sees only the steps and data listed in the Roles and Permissions Matrix.\n"
           "- Uploaded documents are stored under server-generated paths and treated as untrusted content.\n"
           "- Decisions on eligibility, fees or approvals stay with a named human role; the system records them.\n"
           "\n## 5. Failure handling\n"
           "- A step that cannot complete stays in its current state and is reported; requests are never silently dropped.\n"
           "- Validation failures return a clear message and leave the request editable.\n")
    md += "\n" + platform_appendix
    return md


# ---------------------------------------------------------------------------
# Data model / ERD
# ---------------------------------------------------------------------------
def data_model_md(project: Dict[str, Any], steps: List[Dict[str, Any]],
                  rules: List[Dict[str, Any]], platform_appendix: str) -> Optional[str]:
    steps = _ordered(steps)
    if not steps:
        return None

    # Candidate business entities = distinct step inputs/outputs, plus a core request.
    names: Dict[str, str] = {}
    for s in steps:
        for item in _lst(s.get("inputs")) + _lst(s.get("outputs")):
            ident = _ident(item)
            names.setdefault(ident, item)
    actors = list(dict.fromkeys(_actor(s) for s in steps if _actor(s) != UNASSIGNED))

    core = _ident(project.get("name") or "Request") + "Request"
    names.pop(core, None)
    entities = list(names.items())[:12]

    md = _header("Data Model & Entity Relationship Specification", project)
    md += ("> **Candidate model.** Entities are inferred from the inputs and outputs of the approved steps. "
           "Attributes marked 'To be confirmed' were not stated in the sources and need Process Owner review.\n\n")

    md += "## 1. Entity relationship diagram\n```mermaid\nerDiagram\n"
    md += f"    {core} {{\n        string id PK\n        string status\n        datetime created_at\n    }}\n"
    md += "    ProcessUser {\n        string id PK\n        string role\n    }\n"
    md += f"    ProcessUser ||--o{{ {core} : acts_on\n"
    for ident, _ in entities:
        md += f"    {ident} {{\n        string id PK\n        string request_id FK\n    }}\n"
        md += f"    {core} ||--o{{ {ident} : has\n"
    md += "    DecisionLog {\n        string id PK\n        string request_id FK\n        string decided_by\n        string decision\n        datetime decided_at\n    }\n"
    md += f"    {core} ||--o{{ DecisionLog : records\n```\n\n"

    md += "## 2. Entities\n| Entity | Source in process | Attributes |\n|---|---|---|\n"
    md += f"| {core} | The process request itself | id, status, created_at, applicant reference, {TBC} |\n"
    md += f"| ProcessUser | Actors: {_cell(', '.join(actors) or TBC)} | id, name, role |\n"
    for ident, label in entities:
        where = [_step_key(s, i) for i, s in enumerate(steps)
                 if label in _lst(s.get("inputs")) or label in _lst(s.get("outputs"))]
        md += f"| {ident} | '{_cell(label)}' in {', '.join(where)} | id, request_id, {TBC} |\n"
    md += "| DecisionLog | Steps requiring approval | id, request_id, decided_by, decision, decided_at, comment |\n"

    if rules:
        md += "\n## 3. Constraints from business rules\n"
        for r in rules[:15]:
            c = (r.get("condition_json") or {})
            md += f"- **{r.get('rule_key')}**: {_cell(r.get('description'))} (condition: {_cell(c.get('condition') or TBC)})\n"

    md += "\n" + platform_appendix
    return md
