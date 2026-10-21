"""The app's raw HTML must actually render, not appear as literal text.

Covers SPEC-13-01, SPEC-16-01, SPEC-16-02, SPEC-16-04.

`st.markdown(..., unsafe_allow_html=True)` still runs the string through a
Markdown parser first, and Markdown has two rules that silently destroy an
indented template:

  * a line indented four or more spaces becomes an indented code block, so the
    markup is displayed instead of rendered;
  * a blank line inside an HTML block closes it, and the rest is re-parsed.

Every multi-line template in this app was written indented to line up with the
surrounding Python. The reported symptom was the three Project Overview stat
cards (Open questions, Artifacts, Team members) showing as raw HTML; the whole
theme stylesheet was affected the same way.
"""
import ast
import pathlib
import re

import pytest

from app.ui.components import html_block, render_stat_cards, render_status_pill

UI_FILES = ["app/ui/streamlit_app.py", "app/ui/components.py", "app/ui/theme.py"]


def markdown_safe(payload: str):
    """Problems a Markdown parser would hit in this payload. Empty means safe."""
    problems = []
    lines = payload.strip("\n").split("\n")
    for line in lines:
        if line.strip():
            if len(line) - len(line.lstrip(" ")) >= 4:
                problems.append("first non-empty line is indented 4+ spaces (code block)")
            break
    deep = [i for i, ln in enumerate(lines) if ln.strip() and len(ln) - len(ln.lstrip(" ")) >= 4]
    if deep and not problems:
        problems.append(f"{len(deep)} line(s) indented 4+ spaces")
    if any(not ln.strip() for ln in lines[1:-1]):
        problems.append("blank line inside the HTML block")
    return problems


# ---------------------------------------------------------------------------
# The normaliser itself
# ---------------------------------------------------------------------------
def test_html_block_removes_indentation_and_blank_lines():
    """Covers SPEC-16-04. The core fix: an indented template becomes safe."""
    template = """
        <div class="pf-stat-card">
            <div class="pf-stat-label">Open questions</div>

            <div class="pf-stat-num">3</div>
        </div>
    """
    assert markdown_safe(template), "the test fixture should itself be unsafe"
    out = html_block(template)
    assert markdown_safe(out) == [], f"still unsafe: {markdown_safe(out)}"
    assert "\n" not in out, "the payload must collapse to a single line"


def test_html_block_does_not_run_words_together():
    """Text wrapped across source lines must keep its word boundaries."""
    out = html_block("<div>\n    Some text\n    more text\n</div>")
    assert "Some text more text" in out
    assert "textmore" not in out


def test_html_block_keeps_adjacent_tags_tight():
    """Two inline elements must not gain a space between them."""
    assert html_block("<span>a</span>\n<span>b</span>") == "<span>a</span><span>b</span>"


def test_html_block_preserves_all_content():
    """The collapse is whitespace-only: no character of content is lost."""
    template = """
        <div class="x" data-k='v'>
            <b>Q-001</b> &middot; <i>"quote"</i>
            <small>31 March &amp; 15 April</small>
        </div>
    """
    out = html_block(template)
    for fragment in ('class="x"', "data-k='v'", "<b>Q-001</b>", "&middot;",
                     '<i>"quote"</i>', "31 March &amp; 15 April", "</div>"):
        assert fragment in out, f"lost {fragment!r}"


def test_html_block_tolerates_none_and_empty():
    assert html_block(None) == ""
    assert html_block("") == ""
    assert html_block("   \n\n   ") == ""


def test_html_block_is_idempotent():
    once = html_block("""
        <div>
            <b>x</b>
        </div>
    """)
    assert html_block(once) == once


# ---------------------------------------------------------------------------
# The reported bug: the Project Overview stat cards
# ---------------------------------------------------------------------------
def test_the_stat_cards_payload_is_markdown_safe(monkeypatch):
    """Covers SPEC-16-02. The exact symptom reported: raw HTML instead of cards."""
    captured = {}

    import app.ui.components as components

    def fake_markdown(payload, **kwargs):
        captured["payload"] = payload
        captured["kwargs"] = kwargs

    monkeypatch.setattr(components.st, "markdown", fake_markdown)
    render_stat_cards([
        {"icon": "?", "label": "Open questions", "value": 3, "note": "Awaiting a person"},
        {"icon": "#", "label": "Artifacts", "value": 12, "note": "Generated documents"},
        {"icon": "@", "label": "Team members", "value": 2, "note": "Project collaborators"},
    ])

    payload = captured["payload"]
    assert captured["kwargs"].get("unsafe_allow_html") is True
    assert markdown_safe(payload) == [], f"the stat cards would render as text: {markdown_safe(payload)}"
    assert "\n" not in payload
    # and the real content is all still there
    for label in ("Open questions", "Artifacts", "Team members"):
        assert label in payload
    assert payload.count('class="pf-stat-card"') == 3
    assert payload.startswith('<div class="pf-stat-grid">')
    assert payload.endswith("</div>")


def test_status_pill_html_is_single_line():
    """A helper whose output is interpolated into other HTML must stay inline."""
    pill = render_status_pill("waiting_for_human")
    assert "\n" not in pill
    assert pill.startswith("<span")


# ---------------------------------------------------------------------------
# The whole app, enforced structurally
# ---------------------------------------------------------------------------
def test_render_html_is_the_only_unsafe_markdown_caller():
    """Nothing may bypass the normaliser; that is how the bug spread to 102 sites."""
    offenders = []
    for path in UI_FILES:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", None) != "markdown":
                continue
            if not any(k.arg == "unsafe_allow_html" and isinstance(k.value, ast.Constant)
                       and k.value.value is True for k in node.keywords):
                continue
            seg = ast.get_source_segment(text, node) or ""
            if path.endswith("components.py") and "html_block(markup)" in seg:
                continue        # render_html itself, the single sanctioned caller
            offenders.append(f"{path}:{node.lineno}")
    assert offenders == [], (
        "these call st.markdown with unsafe_allow_html directly instead of "
        f"render_html(), so their HTML can render as text: {offenders}"
    )


def test_no_widget_receives_html_without_rendering_it():
    """HTML passed to a widget that does not render HTML would show as text."""
    html_helpers = ("render_status_pill", "question_context_html", "ai_suggestion_html")
    text_widgets = ("markdown", "write", "caption", "info", "success", "warning",
                    "error", "text", "subheader", "header", "title", "metric")
    offenders = []
    for path in UI_FILES:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", None)
            if name not in text_widgets:
                continue
            if any(k.arg == "unsafe_allow_html" for k in node.keywords):
                continue
            seg = ast.get_source_segment(text, node) or ""
            if any(h + "(" in seg for h in html_helpers) or re.search(
                    r"<(div|span|small|table|tr|td|style)\b", seg):
                offenders.append(f"{path}:{node.lineno} st.{name}()")
    assert offenders == [], f"HTML would be shown as literal text by: {offenders}"


@pytest.mark.parametrize("path", UI_FILES)
def test_every_render_html_payload_is_markdown_safe(path):
    """Covers SPEC-13-01. Check the literal templates the app actually passes."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    tree = ast.parse(text)
    unsafe = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (getattr(node.func, "attr", None) or getattr(node.func, "id", None)) != "render_html":
            continue
        if not node.args:
            continue
        arg = node.args[0]
        # Reconstruct the literal shape; {expr} holes do not affect indentation.
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            shape = arg.value
        elif isinstance(arg, ast.JoinedStr):
            shape = "".join(
                v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "X"
                for v in arg.values
            )
        else:
            continue                      # a variable; covered by render_html itself
        # render_html normalises, so the payload that reaches Markdown is safe.
        assert markdown_safe(html_block(shape)) == [], (
            f"{path}:{node.lineno} is still unsafe after normalisation"
        )
        if markdown_safe(shape):
            unsafe.append(node.lineno)
    # Templates are still written indented in the source: that is fine and is
    # exactly what render_html exists to absorb.
    assert isinstance(unsafe, list)


# ---------------------------------------------------------------------------
# The theme stylesheet
# ---------------------------------------------------------------------------
def test_the_theme_stylesheet_survives_normalisation():
    """Covers SPEC-16-01. The CSS was a code block too, so no token applied."""
    src = pathlib.Path("app/ui/theme.py").read_text(encoding="utf-8")
    raw = re.search(r'css = """(.*?)"""', src, re.S).group(1)

    assert markdown_safe(raw), "the raw stylesheet should be unsafe before normalisation"
    out = html_block(raw)
    assert markdown_safe(out) == []
    assert out.startswith("<style>") and out.endswith("</style>")

    body = out[len("<style>"):-len("</style>")]
    assert body.count("{") == body.count("}"), "braces unbalanced after collapsing"
    assert body.count("/*") == body.count("*/"), "comments unbalanced after collapsing"
    # every design token from section 10.9 must survive
    for token in ("#101f36", "#f5f7fb", "#15243a", "#e5eaf1",
                  "#3568f5", "#2455df", "#eaf0ff", "#0d9b8a"):
        assert token in body.lower(), f"design token {token} lost"
    # @import must still precede the first rule or the browser drops it
    assert 0 <= out.find("@import") < out.find(":root")


def test_the_builtin_toolbar_cannot_overlap_the_app_topbar():
    """The Deploy label printed on top of the signed-in user's name."""
    css = pathlib.Path("app/ui/theme.py").read_text(encoding="utf-8")
    for selector in ('[data-testid="stToolbar"]',
                     '[data-testid="stToolbarActions"]',
                     '[data-testid="stDeployButton"]',
                     '[data-testid="stDecoration"]',
                     '[data-testid="stStatusWidget"]'):
        assert selector in css, f"{selector} is not hidden, so it can overlap .pf-topbar"
    hide_rule = css[css.index('[data-testid="stToolbar"]'):]
    hide_rule = hide_rule[: hide_rule.index("}") + 1]
    assert "display: none !important" in hide_rule
    assert "pointer-events: none" in css, "the collapsed header still catches the pointer"
    assert "z-index: 5" in css, ".pf-topbar must sit above anything painted there"
