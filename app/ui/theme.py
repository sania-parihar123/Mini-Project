"""ProcessFoundry AI: Professional SaaS UI Theme & Design Tokens."""
import streamlit as st

from app.ui.components import render_html

def apply_theme():
    """Inject CSS tokens matching processfoundry_ai_professional_clickable_prototype.html."""
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --ink: #15243a;
        --muted: #64748b;
        --line: #e5eaf1;
        --bg: #f5f7fb;
        --navy: #101f36;
        --blue: #3568f5;
        --blue-hover: #2455df;
        --blue2: #eaf0ff;
        --teal: #0d9b8a;
        --orange: #f59e0b;
        --red: #d9485f;
        --white: #ffffff;
        --shadow: 0 16px 45px rgba(23,42,77,.08);
    }

    /* Reset & Typography */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif !important;
        background-color: var(--bg) !important;
        color: var(--ink) !important;
    }

    /* Hide standard Streamlit header and footer */
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0px !important;
        /* The collapsed header still sat above the page and caught the pointer,
           so its contents overlapped the app's own top bar. */
        pointer-events: none !important;
        z-index: 0 !important;
    }
    footer { display: none !important; }
    /* Streamlit's built-in toolbar (the Deploy button, the hamburger menu, the
       "Running" status and the thin decoration bar) is absolutely positioned
       over the top-right of the page, which is exactly where .pf-topbar shows
       the signed-in user's name and role: the Deploy label printed on top of it.
       This app supplies its own top bar, so the built-in one is removed rather
       than only made transparent. */
    [data-testid="stToolbar"],
    [data-testid="stToolbarActions"],
    [data-testid="stDeployButton"],
    [data-testid="stStatusWidget"],
    [data-testid="stDecoration"],
    .stDeployButton,
    #MainMenu {
        display: none !important;
        visibility: hidden !important;
    }
    /* Keep the app's own top bar above anything Streamlit still paints there. */
    .pf-topbar {
        position: relative;
        z-index: 5;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 24px !important;
        padding-bottom: 48px !important;
        max-width: 1440px !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: var(--navy) !important;
        border-right: 1px solid #1c2e4a !important;
    }
    section[data-testid="stSidebar"] * {
        color: #d6deec !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #2a3a52 !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        background-color: transparent !important;
        color: #aebbd0 !important;
        border: none !important;
        text-align: left !important;
        width: 100% !important;
        border-radius: 9px !important;
        padding: 9px 12px !important;
        font-weight: 500 !important;
        font-size: 13.5px !important;
        display: flex !important;
        justify-content: flex-start !important;
        transition: background 0.15s ease !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #223550 !important;
        color: #ffffff !important;
    }

    /* Topbar Header Container */
    .pf-topbar {
        background: #ffffff;
        border-bottom: 1px solid var(--line);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 28px;
        border-radius: 12px;
        margin-bottom: 22px;
        box-shadow: 0 1px 4px rgba(16,32,57,0.03);
    }
    .pf-crumb {
        color: #8090a6;
        font-size: 12px;
    }
    .pf-crumb b {
        color: #1e2c40;
    }
    .pf-userline {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .pf-avatar {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: #dce7ff;
        color: #3158be;
        display: grid;
        place-items: center;
        font-weight: 750;
        font-size: 14px;
    }
    .pf-user-info b {
        display: block;
        font-size: 13px;
        color: var(--ink);
    }
    .pf-user-info small {
        display: block;
        color: var(--muted);
        font-size: 11px;
    }

    /* Cards */
    .pf-card {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 22px;
        box-shadow: 0 2px 7px rgba(16,32,57,0.03);
        margin-bottom: 18px;
    }
    .pf-card-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
    }
    .pf-card-head h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 700;
        color: var(--ink);
    }

    /* Stat Cards */
    .pf-stat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 16px;
        margin-bottom: 22px;
    }
    .pf-stat-card {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 2px 6px rgba(16,32,57,0.02);
    }
    .pf-stat-label {
        color: var(--muted);
        font-size: 12px;
        font-weight: 600;
    }
    .pf-stat-num {
        font-size: 28px;
        font-weight: 750;
        letter-spacing: -0.7px;
        margin: 6px 0 3px;
        color: var(--ink);
    }
    .pf-stat-note {
        font-size: 11px;
        color: #718096;
    }
    .pf-stat-icon {
        float: right;
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: #edf2ff;
        display: grid;
        place-items: center;
        font-size: 16px;
        color: var(--blue);
    }

    /* Pills & Badges */
    .pf-pill {
        font-size: 11px;
        padding: 4px 10px;
        border-radius: 99px;
        font-weight: 700;
        display: inline-block;
        white-space: nowrap;
    }
    .pf-pill-blue { background: #edf2ff; color: #355ed6; }
    .pf-pill-green { background: #e2f8f1; color: #137c67; }
    .pf-pill-amber { background: #fff4d9; color: #96650b; }
    .pf-pill-gray { background: #eef1f5; color: #637188; }
    .pf-pill-red { background: #fee8eb; color: #d9485f; }

    /* Project Row */
    .pf-project-row {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 14px 0;
        border-top: 1px solid #edf0f5;
    }
    .pf-project-row:first-of-type { border-top: 0; }
    .pf-project-icon {
        width: 42px;
        height: 42px;
        border-radius: 11px;
        display: grid;
        place-items: center;
        background: #edf2ff;
        color: #3568f5;
        font-weight: 800;
        font-size: 14px;
    }
    .pf-project-info {
        flex: 1;
        min-width: 0;
    }
    .pf-project-info b {
        display: block;
        font-size: 14px;
        color: var(--ink);
    }
    .pf-project-info small {
        display: block;
        color: var(--muted);
        margin-top: 3px;
        font-size: 12px;
    }

    /* Button Styling Overrides */
    .stButton > button {
        border-radius: 9px !important;
        font-weight: 600 !important;
        font-size: 13.5px !important;
        padding: 8px 16px !important;
        transition: transform 0.1s ease, box-shadow 0.15s ease !important;
    }
    .stButton > button[kind="primary"] {
        background-color: var(--blue) !important;
        color: #ffffff !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(53,104,245,0.22) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--blue-hover) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #34445b !important;
        border: 1px solid var(--line) !important;
    }

    /* Drag-and-Drop File Uploader Styling (Section 10.9) */
    [data-testid="stFileUploaderDropzone"] {
        border: 2px dashed #b9cbe6 !important;
        border-radius: 12px !important;
        background-color: #f7faff !important;
        padding: 24px 20px !important;
        transition: border-color 0.2s ease, background-color 0.2s ease !important;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--blue) !important;
        background-color: #f0f5ff !important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] {
        color: var(--ink) !important;
        font-weight: 500 !important;
    }

    /* Notice Banners */
    .pf-banner {
        border-left: 4px solid var(--blue);
        background: #edf4ff;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 13.5px;
    }
    .pf-banner-warning {
        border-left: 4px solid var(--orange);
        background: #fff9ea;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 13.5px;
    }
    .pf-banner-critical {
        border-left: 4px solid var(--red);
        background: #fdf0f2;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 20px;
        font-size: 13.5px;
    }

    /* Tables */
    .pf-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }
    .pf-table th {
        text-align: left;
        color: #7b8a9e;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-weight: 700;
        padding: 10px 8px;
        border-bottom: 1px solid var(--line);
    }
    .pf-table td {
        padding: 12px 8px;
        border-bottom: 1px solid #f0f3f7;
        color: var(--ink);
    }

    /* Code Block Formatting */
    pre, code {
        font-family: 'Consolas', 'Menlo', 'Monaco', monospace !important;
    }
    </style>
    """
    render_html(css)
