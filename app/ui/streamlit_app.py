"""ProcessFoundry AI: Streamlit Interactive SaaS Application.

Recreates the professional SaaS visual language from
processfoundry_ai_professional_clickable_prototype.html and Section 10.9.
"""
import html
import json
import time
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.ui.theme import apply_theme
from app.ui.components import (
    render_topbar,
    render_sidebar_brand,
    render_sidebar_status,
    render_stat_cards,
    render_status_pill,
    question_context_html,
    ai_suggestion_html,
    render_html
)
from app.ui.api_client import api_client
from app.services import workflow_preview

# -------------------------------------------------------------------------
# Cached API Client Wrappers (P0 Latency Optimization)
# Prevents duplicate network round-trips to remote backend on Streamlit reruns
# -------------------------------------------------------------------------
@st.cache_data(ttl=30, show_spinner=False)
def fetch_project(tok: str, pid: str) -> Optional[Dict[str, Any]]:
    return api_client.get_project(tok, pid)

@st.cache_data(ttl=20, show_spinner=False)
def fetch_waiting_for_me(tok: str) -> List[Dict[str, Any]]:
    return api_client.get_waiting_for_me(tok)

@st.cache_data(ttl=20, show_spinner=False)
def fetch_my_invitations(tok: str) -> List[Dict[str, Any]]:
    return api_client.get_my_invitations(tok)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_projects(tok: str) -> List[Dict[str, Any]]:
    return api_client.list_projects(tok)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_documents(tok: str, pid: str) -> List[Dict[str, Any]]:
    return api_client.list_documents(tok, pid)

@st.cache_data(ttl=20, show_spinner=False)
def fetch_questions(tok: str, pid: str) -> List[Dict[str, Any]]:
    return api_client.list_questions(tok, pid)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_artifacts(tok: str, pid: str) -> List[Dict[str, Any]]:
    return api_client.list_artifacts(tok, pid)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_team(tok: str, pid: str) -> Dict[str, Any]:
    return api_client.get_team(tok, pid)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_evidence(tok: str, pid: str) -> List[Dict[str, Any]]:
    return api_client.get_evidence(tok, pid)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_discovery(tok: str, pid: str) -> Dict[str, Any]:
    return api_client.get_discovery(tok, pid)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_rules(tok: str, pid: str) -> List[Dict[str, Any]]:
    return api_client.get_rules(tok, pid)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_traceability(tok: str, pid: str) -> Dict[str, Any]:
    return api_client.get_traceability(tok, pid)

@st.cache_data(ttl=30, show_spinner=False)
def fetch_audit_log(tok: str, pid: str) -> List[Dict[str, Any]]:
    return api_client.get_audit_log(tok, pid)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_document_understanding(tok: str, doc_id: str, checksum: str) -> Dict[str, Any]:
    """Cached per document content, so expanding the panel is not a model call.

    The backend also persists this per checksum; the checksum in the cache key
    means a replaced document is recomputed rather than served stale.
    """
    return api_client.get_document_understanding(tok, doc_id)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_health() -> Dict[str, Any]:
    return api_client.health()

st.set_page_config(
    page_title="ProcessFoundry AI — Process Intelligence Platform",
    page_icon="P",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS design tokens
apply_theme()

# -------------------------------------------------------------------------
# Session State Initialization
# -------------------------------------------------------------------------
if "token" not in st.session_state:
    st.session_state["token"] = None
if "user" not in st.session_state:
    st.session_state["user"] = None
if "active_project_id" not in st.session_state:
    st.session_state["active_project_id"] = None
if "active_page" not in st.session_state:
    st.session_state["active_page"] = "My projects"
if "auth_mode" not in st.session_state:
    st.session_state["auth_mode"] = "signin"
if "auth_error" not in st.session_state:
    st.session_state["auth_error"] = None
if "auth_success" not in st.session_state:
    st.session_state["auth_success"] = None

def sign_out():
    st.cache_data.clear()
    st.session_state["token"] = None
    st.session_state["user"] = None
    st.session_state["active_project_id"] = None
    st.session_state["active_page"] = "My projects"
    st.session_state["auth_mode"] = "signin"
    st.session_state["auth_error"] = None
    st.rerun()

# -------------------------------------------------------------------------
# Split-Screen Authentication (Section 10.9)
# -------------------------------------------------------------------------
def render_auth_screen():
    col_left, col_right = st.columns([1, 1.1], gap="large")

    with col_left:
        render_html("""
        <div style="display:flex;align-items:center;gap:11px;margin-bottom:28px;">
            <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#5b8cff,#5ad2c0);display:grid;place-items:center;color:#102039;font-weight:900;font-size:19px;">P</div>
            <div>
                <b style="font-size:18px;color:#15243a;letter-spacing:-0.4px;">ProcessFoundry AI</b>
                <small style="display:block;font-size:9.5px;letter-spacing:1.5px;color:#8b9ab0;font-weight:700;">PROCESS INTELLIGENCE</small>
            </div>
        </div>
        """)

        mode = st.session_state["auth_mode"]
        if mode == "signup":
            render_html("<div style='color:#3568f5;font-size:11px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;'>GET STARTED</div>")
            render_html("<h1 style='font-size:30px;letter-spacing:-0.9px;margin:4px 0 10px 0;'>Create your account</h1>")
            render_html("<p style='color:#64748b;font-size:14px;margin-bottom:22px;'>Set up your account to collaborate on process improvement projects.</p>")

            if st.session_state["auth_error"]:
                st.error(st.session_state["auth_error"])

            with st.form("signup_form"):
                display_name = st.text_input("Display Name", placeholder="e.g. Aditi Sharma")
                email = st.text_input("Work Email", placeholder="you@college.edu")
                password = st.text_input("Password", type="password", placeholder="At least 8 characters")
                repeat_password = st.text_input("Repeat Password", type="password", placeholder="Re-enter password")
                submitted = st.form_submit_button("Create account →", type="primary", use_container_width=True)

                if submitted:
                    try:
                        res = api_client.register(display_name, email, password, repeat_password)
                        st.cache_data.clear()
                        st.session_state["token"] = res["access_token"]
                        st.session_state["user"] = res["user"]
                        st.session_state["auth_error"] = None
                        st.rerun()
                    except Exception as e:
                        st.session_state["auth_error"] = str(e)
                        st.rerun()

            render_html("<div style='text-align:center;font-size:13px;color:#64748b;margin-top:14px;'>Already have an account?</div>")
            if st.button("Sign in instead", use_container_width=True):
                st.session_state["auth_mode"] = "signin"
                st.session_state["auth_error"] = None
                st.rerun()

        else:
            render_html("<div style='color:#3568f5;font-size:11px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;'>SECURE WORKSPACE</div>")
            render_html("<h1 style='font-size:30px;letter-spacing:-0.9px;margin:4px 0 10px 0;'>Welcome back</h1>")
            render_html("<p style='color:#64748b;font-size:14px;margin-bottom:22px;'>Sign in to continue to your projects and team decisions.</p>")

            if st.session_state["auth_error"]:
                st.error(st.session_state["auth_error"])

            with st.form("signin_form"):
                email = st.text_input("Email address", placeholder="e.g. aditi@example.com")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Sign in →", type="primary", use_container_width=True)

                if submitted:
                    try:
                        res = api_client.login(email, password)
                        st.cache_data.clear()
                        st.session_state["token"] = res["access_token"]
                        st.session_state["user"] = res["user"]
                        st.session_state["auth_error"] = None
                        st.rerun()
                    except Exception as e:
                        st.session_state["auth_error"] = str(e)
                        st.rerun()

            render_html("<div style='text-align:center;font-size:13px;color:#64748b;margin-top:14px;'>New to ProcessFoundry AI?</div>")
            if st.button("Create an account", use_container_width=True):
                st.session_state["auth_mode"] = "signup"
                st.session_state["auth_error"] = None
                st.rerun()

            # Prototype demo accounts notice (from prototype)
            render_html("""
            <div style="background:#f4f7fc;border:1px solid #e2eaf5;border-radius:10px;padding:14px;margin-top:24px;font-size:12px;color:#5a6b82;">
                <b style="color:#1b2a40;display:block;margin-bottom:4px;">Demo Test Accounts (Part 7.10)</b>
                • <code>aditi@example.com</code> · Analyst<br>
                • <code>rao@example.com</code> · Process Owner<br>
                • <code>anil@example.com</code> · Technical Reviewer<br>
                Password for all: <b>Process123!</b>
            </div>
            """)

    with col_right:
        render_html("""
        <div style="background:radial-gradient(circle at 80% 15%,#2d5485 0,transparent 40%),linear-gradient(145deg,#10203a,#172f4c 65%,#0d4b55);border-radius:20px;padding:44px 38px;color:#ffffff;min-height:560px;display:flex;flex-direction:column;justify-content:center;">
            <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#82ded0;font-weight:800;margin-bottom:12px;">FROM EVIDENCE TO CLARITY</div>
            <h2 style="font-size:36px;line-height:1.15;letter-spacing:-1.2px;margin:0 0 16px 0;color:#ffffff;">Turn complex processes into clear, actionable change.</h2>
            <p style="color:#b8c9db;font-size:14px;line-height:1.75;margin-bottom:28px;">
                Bring your documents, people and decisions into one workspace. ProcessFoundry AI helps college teams discover how administrative and academic work happens today and shape what happens next.
            </p>
            <div style="display:grid;gap:14px;margin-bottom:34px;">
                <div style="display:flex;align-items:center;gap:12px;color:#d7e3ef;font-size:13px;">
                    <div style="width:24px;height:24px;border-radius:7px;border:1px solid #45637d;display:grid;place-items:center;color:#79d9c9;font-weight:800;">✓</div>
                    AI-assisted process discovery grounded in verbatim source quotes
                </div>
                <div style="display:flex;align-items:center;gap:12px;color:#d7e3ef;font-size:13px;">
                    <div style="width:24px;height:24px;border-radius:7px;border:1px solid #45637d;display:grid;place-items:center;color:#79d9c9;font-weight:800;">✓</div>
                    Clear ownership for business and technical clarification questions
                </div>
                <div style="display:flex;align-items:center;gap:12px;color:#d7e3ef;font-size:13px;">
                    <div style="width:24px;height:24px;border-radius:7px;border:1px solid #45637d;display:grid;place-items:center;color:#79d9c9;font-weight:800;">✓</div>
                    Human-approved requirements, BRD/FRD/PRD, and traceability
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                <div style="padding:10px 12px;border:1px solid #45627b;background:#203b56;border-radius:8px;font-size:11px;color:#dbe9f4;">Evidence</div>
                <div style="height:1px;width:18px;background:#69bdb9;"></div>
                <div style="padding:10px 12px;border:1px solid #45627b;background:#203b56;border-radius:8px;font-size:11px;color:#dbe9f4;">AI Discovery</div>
                <div style="height:1px;width:18px;background:#69bdb9;"></div>
                <div style="padding:10px 12px;border:1px solid #45627b;background:#203b56;border-radius:8px;font-size:11px;color:#dbe9f4;">Human Review</div>
                <div style="height:1px;width:18px;background:#69bdb9;"></div>
                <div style="padding:10px 12px;border:1px solid #45627b;background:#203b56;border-radius:8px;font-size:11px;color:#dbe9f4;">Approved Change</div>
            </div>
        </div>
        """)

# -------------------------------------------------------------------------
# Signed-In Workspace Frame (Section 10.9)
# -------------------------------------------------------------------------
if not st.session_state["token"]:
    render_auth_screen()
    st.stop()

token = st.session_state["token"]

# Finding F5: with LLM_PROVIDER=mock the application invents document content and
# To-Be processes. That must never be mistaken for analysis of a real document.
try:
    _health = fetch_health()
except Exception:
    _health = {}
if _health.get("model_is_mock"):
    render_html("""
        <div style="background:#fff4d9;border:1px solid #f0c46a;border-left:5px solid #d1343f;
                    padding:12px 16px;border-radius:6px;margin:0 0 14px 0;font-size:13px;color:#7a4a05;">
            <b>Offline demonstration mode — the content below is not read from your documents.</b><br>
            No AI model is configured (<code>LLM_PROVIDER=mock</code>), so evidence, rules, questions
            and the redesigned process are placeholder text generated offline. Set
            <code>LLM_PROVIDER=gemini</code> with a valid <code>LLM_API_KEY</code> for real analysis.
        </div>
        """)
user = st.session_state["user"]
active_project_id = st.session_state["active_project_id"]
active_project = None

if active_project_id:
    try:
        active_project = fetch_project(token, active_project_id)
    except Exception:
        st.session_state["active_project_id"] = None
        active_project = None

# Render Sidebar Navigation
with st.sidebar:
    render_sidebar_brand()

    render_html("<div style='font-size:10px;text-transform:uppercase;letter-spacing:1.4px;color:#8291aa;padding:0 8px;margin-bottom:6px;'>WORKSPACE</div>")

    if st.button("▦  My projects", use_container_width=True):
        st.session_state["active_page"] = "My projects"
        st.rerun()

    if st.button("＋  Create a project", use_container_width=True):
        st.session_state["active_page"] = "Create a project"
        st.rerun()

    # Waiting for me with badge
    waiting_qs = fetch_waiting_for_me(token)
    waiting_label = f"◎  Waiting for me ({len(waiting_qs)})" if waiting_qs else "◎  Waiting for me"
    if st.button(waiting_label, use_container_width=True):
        st.session_state["active_page"] = "Waiting for me"
        st.rerun()

    invitations = fetch_my_invitations(token)
    inv_label = f"♧  Team & invitations ({len(invitations)})" if invitations else "♧  Team & invitations"
    if st.button(inv_label, use_container_width=True):
        st.session_state["active_page"] = "Team & invitations"
        st.rerun()

    if st.button("◷  Audit log", use_container_width=True):
        st.session_state["active_page"] = "Audit log"
        st.rerun()

    if active_project:
        render_html("<hr style='margin:16px 0;border-color:#1c2e4a;'>")
        render_html(f"<div style='font-size:10px;text-transform:uppercase;letter-spacing:1.4px;color:#8291aa;padding:0 8px;margin-bottom:6px;'>PROJECT: {html.escape(active_project['name'][:18])}</div>")

        if st.button("01  Overview & Uploads", use_container_width=True):
            st.session_state["active_page"] = "Overview & Uploads"
            st.rerun()
        if st.button("02  Sources & Evidence", use_container_width=True):
            st.session_state["active_page"] = "Sources & Evidence"
            st.rerun()
        if st.button("03  As-Is Discovery", use_container_width=True):
            st.session_state["active_page"] = "As-Is Discovery"
            st.rerun()
        if st.button("04  Questions & Rules", use_container_width=True):
            st.session_state["active_page"] = "Questions & Rules"
            st.rerun()
        if st.button("05  Process Redesign", use_container_width=True):
            st.session_state["active_page"] = "Process Redesign"
            st.rerun()
        if st.button("06  Requirements & Specs", use_container_width=True):
            st.session_state["active_page"] = "Requirements & Specs"
            st.rerun()
        if st.button("07  Workflow & Traceability", use_container_width=True):
            st.session_state["active_page"] = "Workflow & Traceability"
            st.rerun()

        if st.button("←  Switch project", use_container_width=True):
            st.session_state["active_project_id"] = None
            st.session_state["active_page"] = "My projects"
            st.rerun()

    render_html("<hr style='margin:16px 0;border-color:#1c2e4a;'>")
    if st.button("Sign out", use_container_width=True):
        sign_out()

    render_sidebar_status()

# Render Sticky Topbar
render_topbar(user, active_project, current_page=st.session_state["active_page"])

# -------------------------------------------------------------------------
# Page 1: My Projects
# -------------------------------------------------------------------------
if st.session_state["active_page"] == "My projects":
    projects = fetch_projects(token)

    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        render_html("<div style='font-size:11px;font-weight:800;letter-spacing:1.5px;color:var(--blue);text-transform:uppercase;'>YOUR WORKSPACE</div>")
        render_html("<h1 style='font-size:28px;letter-spacing:-0.8px;margin:3px 0 6px 0;'>My projects</h1>")
        render_html("<p style='color:var(--muted);font-size:13.5px;margin:0 0 20px 0;'>A focused view of the college processes and decisions you are part of.</p>")
    with head_col2:
        if st.button("＋ Create a project", type="primary", use_container_width=True):
            st.session_state["active_page"] = "Create a project"
            st.rerun()

    # Stat cards
    stats = [
        {"icon": "▦", "label": "Active projects", "value": len(projects), "note": "Projects you belong to"},
        {"icon": "◉", "label": "Waiting for you", "value": len(waiting_qs), "note": "Assigned to your current role"},
        {"icon": "♧", "label": "Pending invitations", "value": len(invitations), "note": "Awaiting your response"},
        {"icon": "✓", "label": "System Status", "value": "Operational", "note": "Engine online"}
    ]
    render_stat_cards(stats)

    # Invitations Card (if any pending)
    if invitations:
        render_html("""
        <div style="background:linear-gradient(120deg,#eaf0ff,#effbf9);border:1px solid #dce7ff;border-radius:12px;padding:18px;margin-bottom:20px;">
            <b style="font-size:15px;color:#183259;display:block;margin-bottom:4px;">Pending Project Invitations</b>
            <span style="color:#576b85;font-size:12.5px;">You have been invited to collaborate with designated roles in the following projects:</span>
        </div>
        """)
        for inv in invitations:
            ic1, ic2, ic3, ic4 = st.columns([3, 2, 1, 1])
            with ic1:
                render_html(f"<b>{html.escape(inv.get('project_name') or 'Project')}</b><br><small style='color:var(--muted)'>Invited by {html.escape(inv.get('inviter_name') or 'Teammate')}</small>")
            with ic2:
                role_pill = render_status_pill(inv.get("role", "analyst"))
                render_html(f"Role: {role_pill}")
            with ic3:
                if st.button("Accept", key=f"acc_{inv['id']}", type="primary"):
                    try:
                        api_client.accept_invitation(token, inv["id"])
                        st.cache_data.clear()
                        st.success("Invitation accepted!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with ic4:
                if st.button("Decline", key=f"dec_{inv['id']}"):
                    try:
                        api_client.decline_invitation(token, inv["id"])
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    # Projects List Card
    render_html('<div class="pf-card"><div class="pf-card-head"><h3>Recent projects</h3></div>')
    if not projects:
        render_html("""
        <div style="text-align:center;padding:40px 20px;color:var(--muted);">
            <div style="font-size:32px;margin-bottom:8px;">▦</div>
            <b style="color:var(--ink);font-size:15px;display:block;margin-bottom:4px;">No projects yet</b>
            <p style="font-size:13px;margin-bottom:16px;">Create a new project workspace or ask a team member to invite you.</p>
        </div>
        """)
    else:
        for p in projects:
            p_col1, p_col2, p_col3, p_col4 = st.columns([3, 2, 1.5, 1])
            with p_col1:
                code = "".join([w[0] for w in p["name"].split()[:2]]).upper() or "PR"
                render_html(f"""
                <div style="display:flex;align-items:center;gap:12px;">
                    <div class="pf-project-icon">{html.escape(code)}</div>
                    <div>
                        <b style="font-size:14px;color:var(--ink);">{html.escape(p['name'])}</b>
                        <small style="display:block;color:var(--muted);font-size:11.5px;">Type: {html.escape(p.get('process_type') or 'General')} · {p.get('members_count', 1)} members</small>
                    </div>
                </div>
                """)
            with p_col2:
                role_pill = render_status_pill(p.get("my_role") or "analyst")
                render_html(f"Your role: {role_pill}")
            with p_col3:
                status_pill = render_status_pill(p.get("status") or "created")
                render_html(status_pill)
            with p_col4:
                if st.button("Open →", key=f"open_p_{p['id']}", use_container_width=True):
                    st.session_state["active_project_id"] = p["id"]
                    st.session_state["active_page"] = "Overview & Uploads"
                    st.rerun()

    render_html('</div>')

# -------------------------------------------------------------------------
# Page 2: Create a Project
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Create a project":
    render_html("<div style='font-size:11px;font-weight:800;letter-spacing:1.5px;color:var(--blue);text-transform:uppercase;'>NEW WORKSPACE</div>")
    render_html("<h1 style='font-size:28px;letter-spacing:-0.8px;margin:3px 0 6px 0;'>Create a project</h1>")
    render_html("<p style='color:var(--muted);font-size:13.5px;margin:0 0 20px 0;'>Start an isolated process discovery workspace and define your role.</p>")

    with st.form("create_project_form"):
        p_name = st.text_input("Project Name *", placeholder="e.g. Merit Scholarship Modernization")
        p_role = st.selectbox("Your Role in this Project *", ["analyst", "process_owner", "technical_reviewer"], format_func=lambda r: {
            "analyst": "Analyst (Uploads evidence, leads discovery & questions)",
            "process_owner": "Process Owner (Domain authority, approves rules & To-Be)",
            "technical_reviewer": "Technical Reviewer (Reviews architecture, data model & tests)"
        }[r])
        p_type = st.text_input("Process Type", placeholder="e.g. scholarship, hostel_allotment, admission, NOC")
        p_desc = st.text_area("Process Description", placeholder="Summarize the college procedure, purpose, and key problems to solve.")
        p_dept = st.text_input("Department", placeholder="e.g. Student Affairs, Academic Office")
        p_goals = st.text_area("Goals", placeholder="What improvements or digital milestones are desired?")
        p_constraints = st.text_area("Constraints", placeholder="Any institutional constraints, regulations or deadlines?")

        submitted = st.form_submit_button("Create project →", type="primary")
        if submitted:
            if not p_name.strip():
                st.error("Project name cannot be empty.")
            else:
                try:
                    new_proj = api_client.create_project(
                        token=token,
                        name=p_name.strip(),
                        role=p_role,
                        process_type=p_type.strip() or "general",
                        description=p_desc.strip(),
                        department=p_dept.strip(),
                        goals=p_goals.strip(),
                        constraints=p_constraints.strip()
                    )
                    st.cache_data.clear()
                    st.session_state["active_project_id"] = new_proj["id"]
                    st.session_state["active_page"] = "Overview & Uploads"
                    st.success("Project created successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

# -------------------------------------------------------------------------
# Page 3: Overview & Uploads (First-class file upload per Section 10.9)
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Overview & Uploads":
    if not active_project:
        st.warning("Please select a project first.")
        st.stop()

    pid = active_project["id"]
    render_html(f"<div style='font-size:11px;font-weight:800;letter-spacing:1.5px;color:var(--blue);text-transform:uppercase;'>PROJECT OVERVIEW</div>")
    render_html(f"<h1 style='font-size:28px;letter-spacing:-0.8px;margin:3px 0 6px 0;'>{html.escape(active_project['name'])}</h1>")
    render_html(f"<p style='color:var(--muted);font-size:13.5px;margin:0 0 20px 0;'>{html.escape(active_project.get('description') or 'College process intelligence workspace.')}</p>")

    # Summary metrics
    docs = fetch_documents(token, pid)
    questions = fetch_questions(token, pid)
    open_qs = [q for q in questions if q["status"] == "open"]
    critical_qs = [q for q in open_qs if q["kind"] in ("conflicting_rules", "missing_actor")]
    artifacts = fetch_artifacts(token, pid)
    team_data = fetch_team(token, pid)

    stats = [
        {"icon": "📄", "label": "Uploaded sources", "value": len(docs), "note": "Documents on file"},
        {"icon": "❓", "label": "Open questions", "value": len(open_qs), "note": f"{len(critical_qs)} critical"},
        {"icon": "📋", "label": "Artifacts drafted", "value": len(artifacts), "note": "Generated specifications"},
        {"icon": "👥", "label": "Team members", "value": len(team_data.get("members", [])), "note": "Project collaborators"}
    ]
    render_stat_cards(stats)

    # Status Banner
    p_status = active_project.get("status", "created")
    if p_status == "waiting_for_human" or critical_qs:
        render_html(f"""
        <div class="pf-banner-warning">
            <b>The AI found {len(critical_qs)} critical issue(s) requiring human clarification.</b><br>
            Analysis is currently waiting for the Process Owner to answer conflicting rules or unnamed actors.
        </div>
        """)
    elif p_status == "in_progress":
        render_html("""
        <div class="pf-banner">
            <b>Analysis is running.</b> Evidence extraction and rule discovery in progress.
        </div>
        """)
    elif p_status == "completed":
        render_html("""
        <div class="pf-banner" style="border-left-color:var(--teal);background:#e9faf5;">
            <b>Analysis & specification generation completed.</b> All specifications drafted and traceable.
        </div>
        """)

    # Workflow Execution & Background Progress Polling (SPEC-03)
    active_run_id = st.session_state.get(f"active_run_{pid}")

    action_col1, action_col2 = st.columns([2, 1])
    with action_col1:
        st.markdown("### Workflow Execution")
    with action_col2:
        can_run = active_project.get("my_role") in ("process_owner", "analyst")
        if not active_run_id:
            if st.button("🚀 Start / Resume Analysis Run", type="primary", disabled=not can_run, use_container_width=True):
                try:
                    run_res = api_client.trigger_run(token, pid)
                    st.cache_data.clear()
                    st.session_state[f"active_run_{pid}"] = run_res.get("id")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            if not can_run:
                st.caption("Only an Analyst or Process Owner can trigger analysis.")

    # If an active run is in progress for this project, poll its status
    if active_run_id:
        try:
            run_data = api_client.get_run(token, active_run_id)
            current_status = run_data.get("status", "running")
            stage = run_data.get("stage", run_data.get("current_node", "start"))
            progress_pct = int(run_data.get("progress", 10))

            render_html(f"""
            <div style="background:#f0f9ff;border:1px solid #bae6fd;padding:16px;border-radius:10px;margin:12px 0;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <b style="color:#0369a1;font-size:14px;">🔄 Analysis Pipeline In Progress</b>
                    <span style="font-size:12px;color:#0284c7;font-weight:600;">Stage: {html.escape(stage)} ({progress_pct}%)</span>
                </div>
            </div>
            """)

            st.progress(progress_pct / 100.0)

            c_col1, c_col2 = st.columns([3, 1])
            with c_col2:
                if st.button("🛑 Cancel Run", key=f"cancel_{active_run_id}", use_container_width=True):
                    api_client.cancel_run(token, active_run_id)
                    st.session_state[f"active_run_{pid}"] = None
                    st.cache_data.clear()
                    st.warning("Run cancellation requested.")
                    st.rerun()

            if current_status == "running":
                time.sleep(1.5)
                st.rerun()
            elif current_status == "completed":
                st.success("🎉 Analysis Run completed successfully!")
                st.session_state[f"active_run_{pid}"] = None
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            elif current_status == "waiting_for_human":
                # Two different waits share this status, because the schema allows
                # only one "a person must act" value. current_node says which.
                if run_data.get("current_node") == "waiting_for_to_be_approval":
                    st.info(
                        "⏸️ Analysis paused: the redesigned process (To-Be) is proposed and "
                        "waiting for a Process Owner to approve it. Open **Process Redesign** "
                        "to approve, request changes or reject. The documents are generated "
                        "only after approval."
                    )
                else:
                    st.info("⏸️ Analysis paused: Waiting for clarification on open critical questions.")
                st.session_state[f"active_run_{pid}"] = None
                st.cache_data.clear()
                st.rerun()
            elif current_status == "failed":
                st.error(f"❌ Analysis failed: {run_data.get('last_error', 'Unknown error')}")
                st.session_state[f"active_run_{pid}"] = None
            elif current_status == "cancelled":
                st.warning("⚠️ Analysis run was cancelled.")
                st.session_state[f"active_run_{pid}"] = None

        except Exception as e:
            st.error(f"Error checking run progress: {e}")
            st.session_state[f"active_run_{pid}"] = None

    # FIRST-CLASS EVIDENCE & DOCUMENTS UPLOAD SECTION (Section 10.9)
    render_html('<div class="pf-card">')
    st.markdown("### Evidence & Source Documents")
    render_html("<p style='color:var(--muted);font-size:13px;margin-bottom:10px;'>Upload official college SOPs, circulars, handbooks or guidelines. Text is extracted and partitioned into verifiable sections with exact character offset tracking.</p>")

    render_html("""
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin:0 0 16px 0;font-size:12px;color:var(--muted);">
        <span style="background:#f1f5f9;padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;">📁 Formats: <b>.pdf, .docx, .txt, .md</b></span>
        <span style="background:#f1f5f9;padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;">⚖️ Max size: <b>25 MB</b></span>
        <span style="background:#f1f5f9;padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;">🔒 Integrity: <b>SHA-256 Hashed</b></span>
        <span style="background:#f1f5f9;padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;">🔍 Ground Truth: <b>Verbatim Substring Verified</b></span>
    </div>
    """)

    render_html("""
        <div style="background:#eef2fd;border-left:3px solid #1f4fd8;padding:8px 12px;
                    border-radius:4px;margin:0 0 12px 0;font-size:12.5px;color:#28457f;">
            Text from your documents is sent to Google Gemini. Use only non-sensitive documents.
        </div>
        """)

    up_col1, up_col2 = st.columns([3, 1])
    with up_col1:
        uploaded_files = st.file_uploader(
            "Choose or drag and drop source document files",
            type=["pdf", "docx", "txt", "md"],
            accept_multiple_files=True,
            help=(
                "Select several files at once. Each is validated on the server, "
                "partitioned into sections and hashed with SHA-256. A file that "
                "fails does not stop the others."
            ),
        )
    with up_col2:
        render_html("<div style='height:28px;'></div>")
        if st.button("Upload & Parse", type="primary", use_container_width=True):
            if not uploaded_files:
                st.warning("Please select at least one file to upload.")
            else:
                progress = st.progress(0.0, text=f"Uploading {len(uploaded_files)} file(s)...")
                try:
                    payload = []
                    for i, uf in enumerate(uploaded_files, start=1):
                        payload.append((uf.name, uf.read(), uf.type or "application/octet-stream"))
                        progress.progress(
                            i / (len(uploaded_files) + 1),
                            text=f"Reading {uf.name} ({i} of {len(uploaded_files)})",
                        )
                    batch = api_client.upload_documents_batch(token, pid, payload)
                    progress.progress(1.0, text="Upload complete.")
                    st.cache_data.clear()
                    st.session_state[f"upload_results_{pid}"] = batch
                    st.rerun()
                except Exception as e:
                    progress.empty()
                    st.error(str(e))

    # One result line per file, kept until the next upload (review item 4).
    batch = st.session_state.get(f"upload_results_{pid}")
    if batch:
        st.markdown(
            f"**Upload results:** {batch.get('accepted_count', 0)} stored, "
            f"{batch.get('rejected_count', 0)} not stored"
        )
        for line in batch.get("results", []):
            name = html.escape(str(line.get("filename", "")))
            message = html.escape(str(line.get("message", "")))
            if line.get("accepted"):
                render_html(f'<div style="background:#e2f8f1;border-left:3px solid #137c67;padding:7px 11px;'
                    f'margin:4px 0;border-radius:4px;font-size:12.5px;">✓ <b>{name}</b> — {message}</div>')
                for w in line.get("parse_warnings") or []:
                    render_html(f'<div style="background:#fff4d9;border-left:3px solid #96650b;padding:6px 11px;'
                        f'margin:2px 0 4px 14px;border-radius:4px;font-size:12px;">⚠️ {html.escape(str(w))}</div>')
            else:
                render_html(f'<div style="background:#fdecee;border-left:3px solid #d1343f;padding:7px 11px;'
                    f'margin:4px 0;border-radius:4px;font-size:12.5px;">✕ <b>{name}</b> — {message}</div>')
        if st.button("Clear upload results", key=f"clear_up_{pid}"):
            st.session_state.pop(f"upload_results_{pid}", None)
            st.rerun()

    # Existing Documents List
    if docs:
        st.markdown(f"#### Stored Project Documents ({len(docs)})")
        for d in docs:
            d_pill = render_status_pill(d.get("parse_status", "pending"))
            p_warnings = d.get("parse_warnings", [])
            has_image_warning = any("Read from images" in w for w in p_warnings)

            render_html(f"""
            <div class="pf-project-row" style="margin-bottom:6px;">
                <div class="pf-project-icon">📄</div>
                <div class="pf-project-info">
                    <b>{html.escape(d['filename'])}</b>
                    <small>Size: {d.get('size_bytes', 0) // 1024} KB · {d.get('sections_count', 0)} sections detected · Checksum: {html.escape(d['checksum'][:12])}...</small>
                </div>
                <div>{d_pill}</div>
            </div>
            """)

            if has_image_warning:
                render_html("""
                <div style="background:#fffbeb;border:1px solid #fef3c7;padding:8px 12px;border-radius:6px;color:#b45309;font-size:12.5px;font-weight:600;margin:-2px 0 10px 0;">
                    ⚠️ Read from images, check the wording.
                </div>
                """)

            if d.get("parse_status") == "failed":
                st.error(f"Parsing failed for '{d['filename']}': Document produced zero usable text sections or could not be parsed.")

            elif d.get("parse_status") == "parsed":
                with st.expander(f"🔍 What I understood from {d['filename']}", expanded=False):
                    try:
                        u = fetch_document_understanding(token, d['id'], d.get('checksum', ''))
                        if u.get("model_is_mock"):
                            st.warning(
                                "This summary was generated offline and is not read from your "
                                "document. Configure a Gemini API key for real analysis."
                            )
                        if u.get("partially_read"):
                            st.error(
                                "Some pages of this document could not be read, so this summary "
                                "is incomplete. See the parsing warnings above."
                            )
                        if u.get("unverified_quotes_dropped"):
                            st.info(
                                f"{u['unverified_quotes_dropped']} quotation(s) the model offered "
                                "could not be found in the document and were discarded."
                            )
                        if u.get("read_from_image"):
                            st.warning("⚠️ Read from images, check the wording.")

                        # Document Type
                        dt = u.get("document_type", {})
                        st.markdown(f"**Document Type:** {dt.get('statement', 'Unknown')}")
                        if dt.get("exact_quote"):
                            st.caption(f"Quotation (Page {dt.get('page_number', 1)}): *\"{dt.get('exact_quote')}\"*")

                        # Summary
                        sm = u.get("summary", {})
                        st.markdown(f"**Summary:** {sm.get('statement', '')}")
                        if sm.get("exact_quote"):
                            st.caption(f"Quotation (Page {sm.get('page_number', 1)}): *\"{sm.get('exact_quote')}\"*")

                        # Required documents
                        req_docs = u.get("required_documents", [])
                        if req_docs:
                            st.markdown("##### 📑 Required Documents")
                            for rd in req_docs:
                                badge = "✅ [FACT]" if rd.get("is_extracted_fact") else "💡 [INTERPRETATION]"
                                st.markdown(f"- {badge} **{rd.get('statement')}**")
                                if rd.get("exact_quote"):
                                    st.caption(f"  *Quote (Page {rd.get('page_number', 1)}):* \"{rd.get('exact_quote')}\"")

                        # Process Steps
                        p_steps = u.get("process_steps", [])
                        if p_steps:
                            st.markdown("##### 👣 Process Steps")
                            for ps in p_steps:
                                badge = "✅ [FACT]" if ps.get("is_extracted_fact") else "💡 [INTERPRETATION]"
                                st.markdown(f"- {badge} **{ps.get('statement')}**")
                                if ps.get("exact_quote"):
                                    st.caption(f"  *Quote (Page {ps.get('page_number', 1)}):* \"{ps.get('exact_quote')}\"")

                        # Fees
                        fees = u.get("fees", [])
                        if fees:
                            st.markdown("##### 💰 Fees & Waivers")
                            for fe in fees:
                                badge = "✅ [FACT]" if fe.get("is_extracted_fact") else "💡 [INTERPRETATION]"
                                st.markdown(f"- {badge} **{fe.get('statement')}**")
                                if fe.get("exact_quote"):
                                    st.caption(f"  *Quote (Page {fe.get('page_number', 1)}):* \"{fe.get('exact_quote')}\"")

                        # Dates and Deadlines
                        dates = u.get("dates_and_deadlines", [])
                        if dates:
                            st.markdown("##### 📅 Dates & Deadlines")
                            for dt_item in dates:
                                badge = "✅ [FACT]" if dt_item.get("is_extracted_fact") else "💡 [INTERPRETATION]"
                                st.markdown(f"- {badge} **{dt_item.get('statement')}**")
                                if dt_item.get("exact_quote"):
                                    st.caption(f"  *Quote (Page {dt_item.get('page_number', 1)}):* \"{dt_item.get('exact_quote')}\"")

                        # People & Roles
                        roles = u.get("people_roles_responsibilities", [])
                        if roles:
                            st.markdown("##### 👥 People, Roles & Responsibilities")
                            for ro in roles:
                                badge = "✅ [FACT]" if ro.get("is_extracted_fact") else "💡 [INTERPRETATION]"
                                st.markdown(f"- {badge} **{ro.get('statement')}**")
                                if ro.get("exact_quote"):
                                    st.caption(f"  *Quote (Page {ro.get('page_number', 1)}):* \"{ro.get('exact_quote')}\"")

                        # Missing or uncertain information
                        missing = u.get("missing_or_uncertain_information", [])
                        if missing:
                            st.markdown("##### ❓ Missing or Uncertain Information")
                            for mis in missing:
                                st.markdown(f"- ⚠️ *{mis}*")

                    except Exception as e:
                        st.info(f"Detailed understanding extraction: {e}")
    else:
        render_html("""
        <div style="text-align:center;padding:32px 20px;background:#f8fafd;border:2px dashed #cbd5e1;border-radius:12px;margin:16px 0;">
            <div style="font-size:36px;margin-bottom:8px;">📁</div>
            <b style="font-size:15px;color:#1e293b;">No source documents uploaded yet</b>
            <p style="font-size:13px;color:#64748b;margin:6px 0 0 0;">Upload college SOPs, circulars, handbooks or guidelines above to provide ground-truth evidence for AI process discovery.</p>
        </div>
        """)
    render_html('</div>')

# -------------------------------------------------------------------------
# Page 4: Waiting for Me
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Waiting for me":
    render_html("<div style='font-size:11px;font-weight:800;letter-spacing:1.5px;color:var(--blue);text-transform:uppercase;'>YOUR QUEUE</div>")
    render_html("<h1 style='font-size:28px;letter-spacing:-0.8px;margin:3px 0 6px 0;'>Waiting for me</h1>")
    render_html("<p style='color:var(--muted);font-size:13.5px;margin:0 0 20px 0;'>Questions and approvals assigned to your current role across all projects.</p>")

    waiting = fetch_waiting_for_me(token)
    if not waiting:
        render_html("""
        <div class="pf-card" style="text-align:center;padding:50px;">
            <div style="font-size:32px;color:var(--teal);margin-bottom:8px;">✓</div>
            <b style="font-size:16px;">All caught up!</b>
            <p style="color:var(--muted);font-size:13px;">No open questions or approvals currently require your action.</p>
        </div>
        """)
    else:
        for q in waiting:
            with st.container():
                render_html('<div class="pf-card">')
                badge = render_status_pill(q["kind"])
                render_html(f"<div style='text-align:right;'>{badge}</div>")
                # Everything brief 7.12 requires, from stored records only.
                render_html(question_context_html(q, show_project=True))

                if q.get("ai_suggestion"):
                    render_html(ai_suggestion_html(q["ai_suggestion"]))

                ans_col1, ans_col2, ans_col3 = st.columns([3, 1, 1])
                with ans_col1:
                    answer_text = st.text_input("Your Response / Decision", key=f"ans_txt_{q['id']}", placeholder="Confirm value (e.g. 31 March) or specify official policy")
                with ans_col2:
                    render_html("<div style='height:28px;'></div>")
                    if st.button("Confirm Answer", key=f"btn_ans_{q['id']}", type="primary", use_container_width=True):
                        if not answer_text.strip():
                            st.error("Please enter a response.")
                        else:
                            try:
                                api_client.answer_question(token, q["id"], "answer", answer_text.strip())
                                st.cache_data.clear()
                                st.success("Answer recorded and verified fact minted!")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                with ans_col3:
                    render_html("<div style='height:28px;'></div>")
                    if st.button("Mark Unknown", key=f"btn_unk_{q['id']}", use_container_width=True):
                        try:
                            api_client.answer_question(token, q["id"], "unknown")
                            st.cache_data.clear()
                            st.info("Marked as unknown. Dependent items flagged as 'Needs clarification'.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                render_html('</div>')

# -------------------------------------------------------------------------
# Page 5: Sources & Evidence
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Sources & Evidence":
    if not active_project:
        st.warning("Please select a project first.")
        st.stop()
    pid = active_project["id"]

    st.markdown("### Verbatim Source Evidence Items (A2)")
    render_html("<p style='color:var(--muted);font-size:13.5px;'>All claims extracted by AI are verified in code against exact section substrings before being stored as project evidence.</p>")

    evidence = fetch_evidence(token, pid)
    if not evidence:
        st.info("No evidence extracted yet. Run the analysis on the Project Overview page.")
    else:
        st.markdown(f"**Total Verified Evidence Items:** {len(evidence)}")
        for e in evidence:
            render_html(f"""
            <div class="pf-card" style="padding:16px;">
                <div style="display:flex;justify-content:space-between;">
                    <b>{html.escape(e['evidence_key'])}</b>
                    <span class="pf-pill pf-pill-blue">{html.escape(e['claim_type'].upper())}</span>
                </div>
                <div style="margin:8px 0;font-size:13.5px;color:var(--ink);">{html.escape(e['claim'])}</div>
                <div style="background:#fffbe6;border-left:3px solid #ffcc00;padding:8px 12px;border-radius:4px;font-size:12.5px;font-style:italic;">
                    "{html.escape(e['quote'])}"
                </div>
                <small style="color:var(--muted);display:block;margin-top:6px;">
                    Source: {html.escape(e.get('document_filename') or 'Document')} — Section: {html.escape(e.get('section_title') or 'General')} (Confidence: {e.get('confidence')})
                </small>
            </div>
            """)

# -------------------------------------------------------------------------
# Page 6: As-Is Discovery (A3)
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "As-Is Discovery":
    if not active_project:
        st.warning("Please select a project first.")
        st.stop()
    pid = active_project["id"]

    st.markdown("### Discovered Current Process (As-Is Model)")
    render_html("<p style='color:var(--muted);font-size:13.5px;'>Grounded in verified evidence. Unnamed actors are explicitly preserved as NULL and flagged.</p>")

    disc = fetch_discovery(token, pid)
    steps = disc.get("steps", [])
    if not steps:
        st.info("As-Is process discovery has not run yet. Start the analysis from the Project Overview page.")
    else:
        render_html(f'<div class="pf-card"><div class="pf-card-head"><h3>Discovered Process Steps ({len(steps)})</h3></div>')
        for s in steps:
            actor = s.get("actor")
            actor_display = f"<b>{html.escape(actor)}</b>" if actor else "<span class='pf-pill pf-pill-red'>⚠️ UNNAMED ACTOR</span>"
            unknown_note = f"<span style='color:var(--red);font-size:11.5px;'>Unknowns: {', '.join(s.get('unknowns', []))}</span>" if s.get("unknowns") else ""

            render_html(f"""
            <div class="pf-project-row">
                <div class="pf-project-icon">{s.get('sequence', 1)}</div>
                <div class="pf-project-info">
                    <b>{html.escape(s['step_key'])}: {html.escape(s['name'])}</b>
                    <small>Type: {html.escape(s.get('step_type', 'task'))} · {unknown_note}</small>
                </div>
                <div>{actor_display}</div>
            </div>
            """)
        render_html('</div>')

# -------------------------------------------------------------------------
# Page 7: Questions & Rules
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Questions & Rules":
    if not active_project:
        st.warning("Please select a project first.")
        st.stop()
    pid = active_project["id"]

    tab_q, tab_r = st.tabs(["Clarification Questions (HITL)", "Candidate Business Rules"])

    with tab_q:
        st.markdown("#### Project Clarification Items")
        questions = fetch_questions(token, pid)
        if not questions:
            st.info("No clarification questions on file.")
        else:
            for q in questions:
                answer_block = (
                    f'<div style="background:#eef2fd;border-left:3px solid #1f4fd8;padding:8px 12px;'
                    f'border-radius:4px;font-size:12.5px;margin-top:10px;"><b>Answered:</b> '
                    f'{html.escape(q["answer"])} — by {html.escape(q.get("answered_by_name") or "a reviewer")}'
                    f'{" on " + html.escape(str(q.get("answered_at"))[:19]) if q.get("answered_at") else ""}</div>'
                ) if q.get("answer") else ""
                render_html('<div class="pf-card" style="padding:16px;">'
                    + f'<div style="text-align:right;">{render_status_pill(q["status"])}</div>'
                    + question_context_html(q, show_project=False)
                    + answer_block
                    + '</div>')
                if q.get("ai_suggestion"):
                    render_html(ai_suggestion_html(q["ai_suggestion"]))

    with tab_r:
        st.markdown("#### Candidate Business Rules")
        rules = fetch_rules(token, pid)
        if not rules:
            st.info("No business rules extracted yet.")
        else:
            for r in rules:
                render_html(f"""
                <div class="pf-card" style="padding:16px;">
                    <div style="display:flex;justify-content:space-between;">
                        <b>{html.escape(r['rule_key'])}</b>
                        {render_status_pill(r['status'])}
                    </div>
                    <div style="margin:6px 0;font-size:13.5px;color:var(--ink);">{html.escape(r['description'])}</div>
                    <small style="color:var(--muted);">Condition: {html.escape(str(r.get('condition_json', {}).get('condition', '')))}</small>
                </div>
                """)

# -------------------------------------------------------------------------
# Page 8: Process Redesign (To-Be) & Human Approval
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Process Redesign":
    if not active_project:
        st.warning("Please select a project first.")
        st.stop()
    pid = active_project["id"]

    st.markdown("### Redesigned Process (To-Be) & Automation Classification (A7, A8)")
    render_html("<p style='color:var(--muted);font-size:13.5px;'>Classifies activities as deterministic, AI-assisted, human decision, or hybrid. Process Owner approval is required before final engineering artifacts are approved.</p>")

    disc = fetch_discovery(token, pid)
    to_be = disc.get("to_be_json")
    if not to_be:
        st.info("To-Be process model has not been generated yet. Complete critical clarifications and run the analysis.")
    else:
        render_html(f'<div class="pf-card"><div class="pf-card-head"><h3>To-Be Modernized Steps: {html.escape(to_be.get("process_name", ""))}</h3></div>')
        render_html(f"<p style='color:var(--muted);font-size:13px;'>{html.escape(to_be.get('summary_of_changes', ''))}</p>")

        for s in to_be.get("steps", []):
            auto_badge = render_status_pill(s.get("automation") or "deterministic")
            approval_badge = "<span class='pf-pill pf-pill-amber'>Human Approval Required</span>" if s.get("human_approval_required") else ""

            render_html(f"""
            <div class="pf-project-row">
                <div class="pf-project-icon">{s.get('sequence', 1)}</div>
                <div class="pf-project-info">
                    <b>{html.escape(s['name'])}</b>
                    <small>Actor: {html.escape(s.get('actor') or 'System')} · Inputs: {', '.join(s.get('inputs', []))}</small>
                </div>
                <div>{auto_badge} {approval_badge}</div>
            </div>
            """)

        render_html('</div>')

        # Human Approval Panel (Process Owner only)
        render_html('<div class="pf-card">')
        st.markdown("### Process Owner Sign-Off")
        my_role = active_project.get("my_role")

        @st.dialog("Confirm Process Rejection")
        def confirm_reject_dialog(ver_id: str, rev_comment: str):
            st.error("⚠️ **Are you sure you want to reject this proposed To-Be process?**")
            st.markdown(
                "Rejecting this process archives the redesign and records your decision in the cryptographic audit log. "
                "The project will not proceed to requirements synthesis until an amended process is submitted."
            )
            if rev_comment and rev_comment.strip():
                st.markdown(f"**Your Review Feedback:** *\"{html.escape(rev_comment.strip())}\"*")
            else:
                st.caption("No written comment provided. It is recommended to explain why the process is rejected.")

            c_yes, c_no = st.columns(2)
            with c_yes:
                if st.button("Yes, Reject Process", type="primary", use_container_width=True):
                    try:
                        api_client.decide_process_version(token, ver_id, "reject", rev_comment)
                        st.cache_data.clear()
                        st.error("Process rejected.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with c_no:
                if st.button("Cancel", use_container_width=True):
                    st.rerun()

        @st.dialog("Confirm Request Changes")
        def confirm_request_changes_dialog(ver_id: str, rev_comment: str):
            st.warning("⚠️ **Request changes for this proposed To-Be process?**")
            st.markdown(
                "This will set the process status to 'Changes Requested' and notify the analyst to address your feedback."
            )
            if rev_comment and rev_comment.strip():
                st.markdown(f"**Requested Revisions:** *\"{html.escape(rev_comment.strip())}\"*")
            else:
                st.caption("Tip: Add specific feedback in the review comments box to clarify requested changes.")

            c_yes, c_no = st.columns(2)
            with c_yes:
                if st.button("Confirm Request Changes", type="primary", use_container_width=True):
                    try:
                        api_client.decide_process_version(token, ver_id, "request_changes", rev_comment)
                        st.cache_data.clear()
                        st.warning("Changes requested.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with c_no:
                if st.button("Cancel", use_container_width=True):
                    st.rerun()

        if my_role != "process_owner":
            st.info(f"You are currently viewing as **{my_role.replace('_',' ').title()}**. Only the **Process Owner** can approve or reject the proposed To-Be process.")
        else:
            comment = st.text_area("Review Comments (required if requesting changes or rejecting)", placeholder="Enter review feedback...")
            dec_col1, dec_col2, dec_col3 = st.columns([1, 1, 1])
            with dec_col1:
                if st.button("✓ Approve To-Be Process", type="primary", use_container_width=True):
                    try:
                        api_client.decide_process_version(token, disc["id"], "approve", comment)
                        st.cache_data.clear()
                        st.success("To-Be process officially approved by Process Owner!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with dec_col2:
                if st.button("Request Changes", use_container_width=True):
                    confirm_request_changes_dialog(disc["id"], comment)
            with dec_col3:
                if st.button("Reject Process", use_container_width=True):
                    confirm_reject_dialog(disc["id"], comment)
        render_html('</div>')

# -------------------------------------------------------------------------
# Page 9: Requirements & Specs (BRD, FRD, PRD, SRS)
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Requirements & Specs":
    if not active_project:
        st.warning("Please select a project first.")
        st.stop()
    pid = active_project["id"]

    artifacts = fetch_artifacts(token, pid)
    if not artifacts:
        st.info("No specification artifacts generated yet. Run the analysis on the Project Overview page.")
    else:
        art_map = {a["artifact_type"]: a for a in artifacts}
        tabs = st.tabs(["BRD", "PRD", "FRD", "SRS", "Rules Catalogue", "Roles Matrix", "Workflow JSON"])

        def render_art_tab(art_key: str):
            art = art_map.get(art_key)
            if not art:
                st.info(f"The {art_key.upper()} has not been compiled yet.")
            else:
                render_html(f"**Version:** {art['version']} · Status: {render_status_pill(art['status'])}")
                st.markdown(art.get("markdown") or "No content.")
                st.download_button(
                    label=f"Download {art_key.upper()} (.md)",
                    data=art.get("markdown") or "",
                    file_name=f"{art_key}_v{art['version']}.md",
                    mime="text/markdown"
                )

        with tabs[0]: render_art_tab("brd")
        with tabs[1]: render_art_tab("prd")
        with tabs[2]: render_art_tab("frd")
        with tabs[3]: render_art_tab("srs")
        with tabs[4]: render_art_tab("rules_catalogue")
        with tabs[5]: render_art_tab("roles_matrix")
        with tabs[6]: render_art_tab("workflow_json")

# -------------------------------------------------------------------------
# Page 10: Workflow & Traceability
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Workflow & Traceability":
    if not active_project:
        st.warning("Please select a project first.")
        st.stop()
    pid = active_project["id"]

    st.markdown("### End-to-End Traceability Matrix (A13)")
    render_html("<p style='color:var(--muted);font-size:13.5px;'>Full relational lineage from source evidence to rules, requirements, steps, and test cases.</p>")

    trace_data = fetch_traceability(token, pid)
    chains = trace_data.get("chains", [])
    report = trace_data.get("validation_report", {})

    render_html(f"""
    <div class="pf-stat-grid" style="grid-template-columns:repeat(4,1fr);">
        <div class="pf-stat-card"><div class="pf-stat-label">Total Requirements</div><div class="pf-stat-num">{report.get('total_requirements', len(chains))}</div></div>
        <div class="pf-stat-card"><div class="pf-stat-label">Verbatim Quote Mismatches</div><div class="pf-stat-num" style="color:var(--teal);">{report.get('quote_mismatches', 0)}</div><div class="pf-stat-note">Audit requirement (must be 0)</div></div>
        <div class="pf-stat-card"><div class="pf-stat-label">Orphan Requirements</div><div class="pf-stat-num">{len(report.get('orphan_requirements', []))}</div></div>
        <div class="pf-stat-card"><div class="pf-stat-label">Integrity Status</div><div class="pf-stat-num" style="color:{'var(--teal)' if report.get('is_valid') else 'var(--orange)'};">{'PASSED' if report.get('is_valid') else 'NEEDS REVIEW'}</div></div>
    </div>
    """)

    if chains:
        render_html('<div class="pf-card">')
        st.markdown("#### Traceability Chains")
        for ch in chains:
            render_html(f"""
            <div style="border:1px solid #edf0f5;border-radius:10px;padding:14px;margin-bottom:12px;background:#ffffff;">
                <div style="display:flex;justify-content:space-between;">
                    <b>{html.escape(ch['requirement_key'])}</b>
                    <span class="pf-pill pf-pill-blue">{html.escape(ch['type'].upper())}</span>
                </div>
                <div style="font-size:13.5px;margin:6px 0;">{html.escape(ch['requirement_statement'])}</div>
                <div style="font-size:12px;color:var(--muted);">
                    <b>Rules:</b> {', '.join(ch.get('rule_keys', [])) or 'None'} |
                    <b>Evidence:</b> {', '.join(ch.get('evidence_keys', [])) or 'None'} |
                    <b>Tests:</b> {', '.join(ch.get('test_keys', [])) or 'None'}
                </div>
            </div>
            """)
        render_html('</div>')

    # ---------------------------------------------------------------------
    # Workflow preview and clickable prototype (design doc A11 / Page 7)
    # Built from the project's own workflow JSON; nothing is saved or sent.
    # ---------------------------------------------------------------------
    st.markdown("### Workflow Preview & Prototype (A11)")
    render_html("<p style='color:var(--muted);font-size:13.5px;'>Generated from the project's workflow JSON. The prototype is illustrative only: it stores nothing and is not a working system.</p>")
    try:
        wf_art = {a["artifact_type"]: a for a in fetch_artifacts(token, pid)}.get("workflow_json")
    except Exception:
        wf_art = None
    wf_data = (wf_art or {}).get("content_json")
    preview = workflow_preview.preview_html(wf_data)
    if not preview:
        st.info("No workflow yet. Run the analysis and approve the To-Be process to generate the workflow preview and prototype.")
    else:
        try:
            wf_rules = api_client.get_rules(token, pid)
        except Exception:
            wf_rules = []
        proto_html = workflow_preview.prototype_html(wf_data, wf_rules)
        tab_prev, tab_proto, tab_json = st.tabs(["Workflow diagram", "Clickable prototype", "Workflow JSON"])
        with tab_prev:
            components.html(preview[0], height=min(preview[1] + 40, 760), scrolling=True)
            st.download_button(
                "Download diagram (.html)", data=preview[0],
                file_name=f"workflow_preview_v{wf_art['version']}.html", mime="text/html",
                key="dl_wf_preview",
            )
        with tab_proto:
            components.html(proto_html, height=720, scrolling=True)
            st.download_button(
                "Download prototype (.html)", data=proto_html,
                file_name=f"prototype_v{wf_art['version']}.html", mime="text/html",
                key="dl_wf_prototype",
            )
        with tab_json:
            st.json(wf_data)

# -------------------------------------------------------------------------
# Page 11: Team & Invitations
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Team & invitations":
    if not active_project:
        st.info("Open a project to manage its team and invite collaborators.")
    else:
        pid = active_project["id"]
        team = fetch_team(token, pid)

        render_html("<div style='font-size:11px;font-weight:800;letter-spacing:1.5px;color:var(--blue);text-transform:uppercase;'>COLLABORATION</div>")
        render_html("<h1 style='font-size:28px;letter-spacing:-0.8px;margin:3px 0 6px 0;'>Team & invitations</h1>")

        can_manage_team = (active_project.get("my_role") == "process_owner") or (active_project.get("created_by") == user["id"])

        @st.dialog("Confirm Member Removal")
        def confirm_remove_member_dialog(member_user_id: str, member_name: str):
            st.error(f"⚠️ **Are you sure you want to remove {member_name}?**")
            st.markdown(
                f"Removing **{html.escape(member_name)}** will immediately revoke their access to this project, "
                "its documents, evidence, and specification artifacts. This action is recorded in the audit trail."
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, Remove Member", type="primary", use_container_width=True):
                    try:
                        api_client.remove_member(token, pid, member_user_id)
                        st.cache_data.clear()
                        st.success(f"{member_name} has been removed.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with c2:
                if st.button("Cancel", use_container_width=True):
                    st.rerun()

        @st.dialog("Confirm Revoke Invitation")
        def confirm_revoke_invitation_dialog(inv_id: str, invitee_email: str):
            st.warning(f"⚠️ **Revoke invitation for {invitee_email}?**")
            st.markdown(
                f"This will immediately invalidate the pending invitation sent to **{html.escape(invitee_email)}**."
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, Revoke Invitation", type="primary", use_container_width=True):
                    try:
                        api_client.revoke_invitation(token, inv_id)
                        st.cache_data.clear()
                        st.success(f"Invitation to {invitee_email} revoked.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with c2:
                if st.button("Cancel", use_container_width=True):
                    st.rerun()

        inv_col1, inv_col2 = st.columns([1, 1], gap="large")

        with inv_col1:
            render_html('<div class="pf-card"><div class="pf-card-head"><h3>Active Project Members</h3></div>')
            for m in team.get("members", []):
                mem_c1, mem_c2 = st.columns([4, 1.2])
                with mem_c1:
                    render_html(f"""
                    <div class="pf-project-row" style="margin-bottom:0;">
                        <div class="pf-avatar" style="width:34px;height:34px;font-size:12px;">{m['display_name'][:2].upper()}</div>
                        <div class="pf-project-info">
                            <b>{html.escape(m['display_name'])}</b>
                            <small>{html.escape(m['email'])}</small>
                        </div>
                        <div>{render_status_pill(m['role'])}</div>
                    </div>
                    """)
                with mem_c2:
                    if can_manage_team and m["user_id"] != user["id"] and m["user_id"] != active_project.get("created_by"):
                        if st.button("Remove", key=f"rem_{m['user_id']}", use_container_width=True):
                            confirm_remove_member_dialog(m["user_id"], m["display_name"])
            render_html('</div>')

        with inv_col2:
            render_html('<div class="pf-card"><div class="pf-card-head"><h3>Invite Teammate</h3></div>')
            if not can_manage_team:
                st.info("Only the Process Owner or project creator can invite new teammates.")
            else:
                with st.form("invite_form"):
                    inv_email = st.text_input("Teammate Email Address", placeholder="colleague@college.edu")
                    inv_role = st.selectbox("Assigned Role", ["process_owner", "analyst", "technical_reviewer"], format_func=lambda r: {
                        "process_owner": "Process Owner (Domain authority & approvals)",
                        "analyst": "Analyst (Discovery & document preparation)",
                        "technical_reviewer": "Technical Reviewer (Architecture & test review)"
                    }[r])
                    inv_submit = st.form_submit_button("Send Invitation →", type="primary")
                    if inv_submit:
                        if not inv_email.strip():
                            st.error("Please enter a valid email address.")
                        else:
                            try:
                                api_client.invite_teammate(token, pid, inv_email.strip(), inv_role)
                                st.cache_data.clear()
                                st.success("Invitation created and recorded!")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

            st.markdown("#### Pending Invitations")
            inv_list = team.get("invitations", [])
            if not inv_list:
                st.caption("No pending invitations.")
            for inv in inv_list:
                p_c1, p_c2 = st.columns([4, 1.2])
                with p_c1:
                    render_html(f"""
                    <div style="border-top:1px solid #edf0f5;padding:10px 0;display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <b>{html.escape(inv['email'])}</b><br>
                            <small style="color:var(--muted);">Invited as {html.escape(inv['role'])} ·
                            {'E-mail sent' if inv['email_status'] == 'sent' else 'E-mail not sent'}
                            {f" · resent {inv['resend_count']} of 5" if inv.get('resend_count') else ''}</small>
                        </div>
                        {render_status_pill('pending')}
                    </div>
                    """)
                    if inv["email_status"] != "sent":
                        st.caption(
                            f"Invitation saved. The e-mail could not be sent, so ask "
                            f"{inv['email']} to register with this address."
                        )
                with p_c2:
                    if can_manage_team:
                        # Brief 7.4: a Resend button, limited to 5 per invitation.
                        resends_left = 5 - int(inv.get("resend_count") or 0)
                        if st.button(
                            "Resend e-mail",
                            key=f"resend_{inv['id']}",
                            use_container_width=True,
                            disabled=resends_left <= 0,
                            help=(
                                f"{resends_left} resend(s) left" if resends_left > 0
                                else "The limit of 5 resends has been reached."
                            ),
                        ):
                            try:
                                updated = api_client.resend_invitation(token, inv["id"])
                                st.cache_data.clear()
                                if updated.get("email_status") == "sent":
                                    st.success(f"Invitation e-mail resent to {inv['email']}.")
                                else:
                                    st.warning(
                                        "Resend recorded, but the e-mail could not be sent. "
                                        f"Ask {inv['email']} to register with this address."
                                    )
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                        if st.button("Revoke", key=f"rev_{inv['id']}", use_container_width=True):
                            confirm_revoke_invitation_dialog(inv["id"], inv["email"])
            render_html('</div>')

# -------------------------------------------------------------------------
# Page 12: Audit Log
# -------------------------------------------------------------------------
elif st.session_state["active_page"] == "Audit log":
    render_html("<div style='font-size:11px;font-weight:800;letter-spacing:1.5px;color:var(--blue);text-transform:uppercase;'>TRACEABILITY</div>")
    render_html("<h1 style='font-size:28px;letter-spacing:-0.8px;margin:3px 0 6px 0;'>Audit log</h1>")
    render_html("<p style='color:var(--muted);font-size:13.5px;margin:0 0 20px 0;'>Append-only cryptographic SHA-256 hash-chained history of project actions and decisions.</p>")

    if not active_project:
        st.info("Select a project to inspect its audit chain.")
    else:
        pid = active_project["id"]
        logs = fetch_audit_log(token, pid)
        render_html(f'<div class="pf-card"><div class="pf-card-head"><h3>Audit Events ({len(logs)})</h3></div>')
        if not logs:
            st.info("No audit events recorded yet.")
        else:
            for l in logs:
                render_html(f"""
                <div style="border-bottom:1px solid #edf0f5;padding:12px 0;">
                    <div style="display:flex;justify-content:space-between;">
                        <b>{html.escape(l['event_type'])}</b>
                        <small style="color:var(--muted);">{html.escape(l['created_at'][:19].replace('T', ' '))}</small>
                    </div>
                    <div style="font-size:13px;color:var(--ink);margin:4px 0;">Subject: {html.escape(str(l.get('subject') or 'General'))} · Actor: {html.escape(l['actor'])}</div>
                    <div style="font-family:monospace;font-size:11px;color:var(--muted);">SHA-256 Hash: {html.escape(l['hash'])}</div>
                </div>
                """)
        render_html('</div>')
