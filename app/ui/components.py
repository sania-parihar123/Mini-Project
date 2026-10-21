"""ProcessFoundry AI: Reusable UI Components and Layout Frames."""
import html
import streamlit as st
from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# Markdown-safe HTML injection
#
# st.markdown(..., unsafe_allow_html=True) still runs the string through a
# Markdown parser first, and Markdown has two rules that silently destroy an
# indented HTML template:
#
#   * a line indented four or more spaces becomes an indented CODE BLOCK, so the
#     markup is shown as literal text instead of being rendered;
#   * a blank line inside an HTML block closes that block, and what follows is
#     parsed as Markdown again.
#
# Every multi-line template in this app was written indented to line up with the
# surrounding Python, which is why the Project Overview stat cards (and much
# else, including the whole theme stylesheet) appeared as raw text.
#
# html_block() collapses a template onto a single line, so no line-level
# Markdown construct can exist at all, and render_html() is the only thing in
# the app allowed to call st.markdown with unsafe_allow_html.
#
# The collapse is whitespace-only and changes no content. Lines are joined
# tightly where one tag ends and the next begins, so adjacent inline elements
# keep their exact spacing, and with a single space otherwise, so text wrapped
# across source lines does not have its words run together. HTML collapses runs
# of whitespace anyway, and this app contains no <pre>, <textarea> or
# white-space: pre, so nothing in it is whitespace-sensitive.
# ---------------------------------------------------------------------------
def html_block(markup: str) -> str:
    """Collapse an indented, multi-line HTML or CSS template into one safe line."""
    if markup is None:
        return ""
    parts: List[str] = []
    for line in str(markup).splitlines():
        line = line.strip()
        if not line:
            continue                      # a blank line would close the HTML block
        if parts and not (parts[-1].endswith(">") and line.startswith("<")):
            parts.append(" ")
        parts.append(line)
    return "".join(parts)


def render_html(markup: str) -> None:
    """Render raw HTML through Streamlit, normalised so Markdown cannot eat it.

    This is the one place that may call st.markdown with unsafe_allow_html.
    """
    st.markdown(html_block(markup), unsafe_allow_html=True)


def render_topbar(user: Dict[str, Any], active_project: Optional[Dict[str, Any]] = None, current_page: str = "My projects"):
    """Render the persistent top navigation bar."""
    display_name = user.get("display_name", "User")
    initials = "".join([part[0] for part in display_name.split()[:2]]).upper() or "U"
    role_label = (active_project.get("my_role") or "Analyst").replace("_", " ").title() if active_project else "Workspace User"
    project_name = active_project.get("name") if active_project else None

    crumb_html = f"Workspace / <b>{html.escape(current_page)}</b>"
    if project_name:
        crumb_html = f"Projects / <b>{html.escape(project_name)}</b> / <span style='color:var(--muted)'>{html.escape(current_page)}</span>"

    topbar_html = f"""
    <div class="pf-topbar">
        <div class="pf-crumb">{crumb_html}</div>
        <div class="pf-userline">
            <div class="pf-avatar">{initials}</div>
            <div class="pf-user-info">
                <b>{html.escape(display_name)}</b>
                <small>{html.escape(role_label)}</small>
            </div>
        </div>
    </div>
    """
    render_html(topbar_html)

def render_sidebar_brand():
    """Render the sidebar brand mark."""
    brand_html = """
    <div style="display:flex;align-items:center;gap:11px;padding:12px 6px 20px 6px;">
        <div style="width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#5b8cff,#5ad2c0);display:grid;place-items:center;color:#102039;font-weight:900;font-size:18px;">P</div>
        <div>
            <div style="color:#ffffff;font-weight:800;font-size:16px;letter-spacing:-0.3px;">ProcessFoundry AI</div>
            <div style="color:#8291aa;font-size:9.5px;letter-spacing:1.4px;font-weight:700;">PROCESS INTELLIGENCE</div>
        </div>
    </div>
    """
    render_html(brand_html)

def render_sidebar_status():
    """Render the sidebar system health indicator."""
    status_html = """
    <div style="margin-top:30px;padding:16px 8px;border-top:1px solid #1c2e4a;color:#8291aa;font-size:12px;">
        <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#50d5b2;margin-right:7px;"></span>
        All systems operational<br>
        <span style="font-size:10px;color:#596b82;display:block;margin-top:4px;">ProcessFoundry Core v0.1.0</span>
    </div>
    """
    render_html(status_html)

def render_stat_cards(stats: List[Dict[str, Any]]):
    """Render 4-column metric cards."""
    cards_html = '<div class="pf-stat-grid">'
    for s in stats:
        icon = s.get("icon", "▦")
        label = s.get("label", "")
        num = str(s.get("value", 0))
        note = s.get("note", "")
        cards_html += f"""
        <div class="pf-stat-card">
            <div class="pf-stat-icon">{icon}</div>
            <div class="pf-stat-label">{html.escape(label)}</div>
            <div class="pf-stat-num">{html.escape(num)}</div>
            <div class="pf-stat-note">{html.escape(note)}</div>
        </div>
        """
    cards_html += '</div>'
    render_html(cards_html)

def render_status_pill(status_str: str) -> str:
    """Format status string into styled pill HTML."""
    s = (status_str or "").lower()
    if any(w in s for w in ["approve", "complete", "verified", "active"]):
        cls = "pf-pill-green"
    elif any(w in s for w in ["wait", "critical", "pending"]):
        cls = "pf-pill-amber"
    elif any(w in s for w in ["fail", "reject", "cancel"]):
        cls = "pf-pill-red"
    elif any(w in s for w in ["progress", "analysis", "running"]):
        cls = "pf-pill-blue"
    else:
        cls = "pf-pill-gray"
    label = status_str.replace("_", " ").title()
    return f'<span class="pf-pill {cls}">{html.escape(label)}</span>'


def question_context_html(q: Dict[str, Any], show_project: bool = True) -> str:
    """Everything brief 7.12 requires a question to show, from stored records only.

    1 project name and question key, 2 the plain question, 3 why it matters,
    4 every source (letter, exact quote, file name, section number and title,
    page number), 5 the other choices, 6 what happens after the answer.
    """
    e = html.escape
    parts = []

    header = f"<b>{e(q.get('question_key') or '')}</b>"
    if show_project and q.get("project_name"):
        header += f' <span style="color:var(--muted);font-size:12px;">· {e(q["project_name"])}</span>'
    role = (q.get("assigned_role") or "").replace("_", " ").title()
    if role:
        header += f' <span style="color:var(--muted);font-size:12px;">· you answer as {e(role)}</span>'
    parts.append(f'<div style="font-size:12.5px;margin-bottom:4px;">{header}</div>')

    parts.append(
        f'<div style="font-size:15px;font-weight:700;margin:6px 0 4px 0;">{e(q.get("question") or "")}</div>'
    )
    if q.get("reason"):
        parts.append(
            '<div style="color:var(--muted);font-size:12.5px;margin-bottom:10px;">'
            f'<i>Why this matters:</i> {e(q["reason"])}</div>'
        )

    # Item 4: the source passages, with their badge letters.
    sources = q.get("linked_evidence") or []
    if sources:
        parts.append('<div style="font-size:12.5px;font-weight:700;margin:8px 0 4px 0;">Where this comes from</div>')
        for i, src in enumerate(sources):
            letter = chr(ord("A") + i)
            where_bits = []
            if src.get("document_name"):
                where_bits.append(e(str(src["document_name"])))
            if src.get("section_index") is not None or src.get("section_title"):
                where_bits.append(
                    "section " + e(f"{src.get('section_index')}: {src.get('section_title')}")
                )
            if src.get("page_number") is not None:
                where_bits.append("page " + e(str(src["page_number"])))
            if src.get("evidence_key"):
                where_bits.append(e(str(src["evidence_key"])))
            parts.append(f'''
            <div style="background:#fffdf0;border-left:3px solid #d1343f;padding:8px 12px;margin:6px 0;border-radius:4px;font-size:12.5px;">
                <span style="display:inline-block;background:#d1343f;color:#fff;font-weight:700;border-radius:3px;padding:0 6px;margin-right:6px;">{letter}</span>
                <i>&ldquo;{e(str(src.get("quote") or ""))}&rdquo;</i><br>
                <small style="color:var(--muted);">{" · ".join(where_bits)}</small>
            </div>''')

    # Item 5: the other choices.
    options = q.get("options") or []
    if options:
        parts.append('<div style="font-size:12.5px;font-weight:700;margin:10px 0 4px 0;">Your choices</div>')
        for opt in options:
            label = e(str(opt.get("label") or ""))
            letter = opt.get("letter")
            badge = (
                f'<span style="display:inline-block;background:#eef2fd;color:#1f4fd8;font-weight:700;border-radius:3px;padding:0 6px;margin-right:6px;">{e(str(letter))}</span>'
                if letter else ""
            )
            style = "border:1px dashed #aebac3;background:#fafbfc;" if opt.get("is_ai_suggestion") else "border:1px solid var(--line);background:#fff;"
            suffix = ' <small style="color:var(--muted);">(AI suggestion, not a fact)</small>' if opt.get("is_ai_suggestion") else ""
            quote = opt.get("quote")
            parts.append(f'''
            <div style="{style}padding:7px 11px;margin:5px 0;border-radius:6px;font-size:12.5px;">
                {badge}<b>{label}</b>{suffix}
                {f'<br><i style="color:var(--muted);">&ldquo;{e(str(quote))}&rdquo;</i>' if quote else ''}
            </div>''')

    # Item 6: the consequences, written by code from stored records.
    if q.get("consequence_summary"):
        parts.append(f'''
        <div style="background:#eef2fd;border-left:3px solid #1f4fd8;padding:8px 12px;margin:10px 0 2px 0;border-radius:4px;font-size:12.5px;">
            <b>When you confirm</b><br>{e(q["consequence_summary"])}
        </div>''')

    return "".join(parts)


def ai_suggestion_html(text: str) -> str:
    """AI output always in a dashed box and always labelled (brief 10.1)."""
    return f'''
    <div style="border:1px dashed #aebac3;border-radius:8px;padding:10px 14px;background:#fafbfc;margin:12px 0;font-size:12.5px;color:#5a6878;">
        {html.escape(text)}
    </div>'''
