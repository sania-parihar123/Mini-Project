"""Test suite for Phase 1 Landing Page components, assets, and styling."""
import pytest
from app.ui.components import html_block
from app.ui.landing.styles import LANDING_CSS
from app.ui.landing.illustrations import (
    HERO_PIPELINE_SVG,
    PROCESS_GUIDE_MOCKUP_SVG,
    FEATURE_ICONS
)
from app.ui.landing.components import (
    get_nav_html,
    get_hero_html,
    get_problem_html,
    get_how_it_works_html,
    get_features_html,
    get_why_different_html,
    get_use_cases_html,
    get_process_guide_html,
    get_expected_value_html,
    get_final_cta_html,
    get_footer_html
)
from app.ui.landing.landing_page import render_landing_page


def test_landing_css_tokens():
    """Verify that design colors and theme tokens are defined."""
    assert "#10213B" in LANDING_CSS  # Primary dark navy
    assert "#142943" in LANDING_CSS  # Secondary navy
    assert "#3563F6" in LANDING_CSS  # Primary blue
    assert "#EAF0FF" in LANDING_CSS  # Light blue
    assert "#F4F7FC" in LANDING_CSS  # Background
    assert "#FFFFFF" in LANDING_CSS  # White
    assert "#17243A" in LANDING_CSS  # Primary text
    assert "#64748B" in LANDING_CSS  # Secondary text
    assert "#48C7B5" in LANDING_CSS  # Accent teal


def test_landing_reduced_motion_support():
    """Ensure accessibility preference for reduced motion is handled."""
    assert "@media (prefers-reduced-motion: reduce)" in LANDING_CSS
    assert "animation-duration: 0.01ms" in LANDING_CSS


def test_hero_pipeline_svg_validity():
    """Verify hero pipeline diagram contains required stages and visual cues."""
    assert "<svg" in HERO_PIPELINE_SVG
    assert "</svg>" in HERO_PIPELINE_SVG
    assert "Documents" in HERO_PIPELINE_SVG
    assert "AI Discovery" in HERO_PIPELINE_SVG
    assert "Rule & Gap Engine" in HERO_PIPELINE_SVG
    assert "Human Validation" in HERO_PIPELINE_SVG
    assert "Deliverables" in HERO_PIPELINE_SVG
    assert "PHASE 1 ACTIVE" in HERO_PIPELINE_SVG


def test_process_guide_mockup_svg():
    """Verify Process Guide mockup includes concept tag, role filtering, and quote grounding."""
    assert "<svg" in PROCESS_GUIDE_MOCKUP_SVG
    assert "Verified Process Guide" in PROCESS_GUIDE_MOCKUP_SVG
    assert "CONCEPT CAPABILITY" in PROCESS_GUIDE_MOCKUP_SVG
    assert "Source Quote:" in PROCESS_GUIDE_MOCKUP_SVG


def test_all_15_feature_icons_exist():
    """Verify that all 15 core features have dedicated SVG icons."""
    expected_keys = [
        "multi_doc", "ai_discovery", "actor_id", "rule_extract", "gap_analysis",
        "human_in_loop", "as_is_model", "to_be_redesign", "req_eng", "data_arch",
        "prototype_gen", "test_cases", "traceability", "process_guide", "doc_export"
    ]
    assert len(FEATURE_ICONS) == 15
    for key in expected_keys:
        assert key in FEATURE_ICONS
        assert "<svg" in FEATURE_ICONS[key]


def test_navigation_bar_links():
    """Verify navigation links and call-to-actions."""
    nav = get_nav_html()
    assert "ProcessFoundry AI" in nav
    assert 'href="#hero"' in nav
    assert 'href="#how-it-works"' in nav
    assert 'href="#features"' in nav
    assert 'href="#use-cases"' in nav
    assert 'href="/?page=login"' in nav
    assert 'href="/?page=signup"' in nav


def test_hero_section_content():
    """Verify exact hero copy as specified in requirements."""
    hero = get_hero_html()
    assert "Understand Your Processes." in hero
    assert "Build the Right Blueprint." in hero
    assert "Discover how your processes actually work" in hero
    assert "Get Started Free" in hero
    assert "Explore How It Works" in hero


def test_problem_section_cards():
    """Verify all 5 problems are articulated."""
    prob = get_problem_html()
    assert "Process Digitisation Should Start with Understanding" in prob
    assert "Scattered Documents" in prob
    assert "Hidden Rules & Exceptions" in prob
    assert "Policy vs Practice Mismatches" in prob
    assert "Late Requirement Surprises" in prob
    assert "Recreated Process Wheel" in prob


def test_how_it_works_6_stages():
    """Verify all 6 pipeline stages are present."""
    hiw = get_how_it_works_html()
    assert "From Existing Knowledge to a Verified Process Blueprint" in hiw
    assert "Collect Sources" in hiw
    assert "Discover Processes" in hiw
    assert "Analyse Rules" in hiw
    assert "Human Validation" in hiw
    assert "Redesign Processes" in hiw
    assert "Generate Deliverables" in hiw


def test_core_features_15_cards():
    """Verify all 15 core feature titles appear in features section."""
    feat = get_features_html()
    features = [
        "Multi-Document Ingestion",
        "AI-Assisted Process Discovery",
        "Actor Identification",
        "Business Rule Extraction",
        "Gap and Conflict Analysis",
        "Human-in-the-Loop Clarification",
        "As-Is Process Modelling",
        "To-Be Process Redesign",
        "Requirements Engineering",
        "Data & Architecture Design",
        "Clickable Prototype Generation",
        "Test Case & UAT Generation",
        "Evidence-Based Traceability",
        "Verified Process Guide",
        "Document and Artifact Export"
    ]
    for title in features:
        assert title in feat


def test_why_different_distinctions():
    """Verify the 4 architectural highlights vs generic AI chatbots."""
    diff = get_why_different_html()
    assert "More Than a Generic AI Chatbot or Coding Agent" in diff
    assert "Starts Before Coding" in diff
    assert "Evidence-Based Intelligence" in diff
    assert "Human-Approved Decisions" in diff
    assert "End-to-End Traceability" in diff


def test_use_cases_higher_ed_and_enterprise():
    """Verify both college and enterprise use cases are detailed."""
    uc = get_use_cases_html()
    assert "One Platform for Different Types of Processes" in uc
    assert "Scholarship Application" in uc
    assert "Student Certificates" in uc
    assert "ID Correction &amp; Migration" in uc
    assert "Examination Corrections" in uc
    assert "Internship NOC" in uc
    assert "Employee Onboarding" in uc
    assert "Vendor Registration" in uc
    assert "Travel &amp; Expense" in uc
    assert "Customer Complaint" in uc
    assert "Internal Service Requests" in uc


def test_expected_value_pilot_targets():
    """Verify pilot evaluation metrics are labeled as targets."""
    ev = get_expected_value_html()
    assert "PILOT EVALUATION TARGETS" in ev
    assert "30%" in ev
    assert "≥90%" in ev
    assert "25%" in ev
    assert "≥4/5" in ev
    assert "≥50%" in ev


def test_strict_phase_1_scope():
    """Ensure no prohibited Phase 2/3 operational workflow claims are made."""
    combined = (
        get_hero_html() + get_problem_html() + get_how_it_works_html() +
        get_features_html() + get_why_different_html() + get_use_cases_html() +
        get_process_guide_html() + get_expected_value_html()
    )
    # Must NOT claim deployable execution or live operational management
    assert "deployable workflow application generation" not in combined.lower()
    assert "automated workflow execution" not in combined.lower()
    assert "live operational workflow management" not in combined.lower()


def test_render_landing_page_execution(monkeypatch):
    """Test that render_landing_page invokes render_html with single-line collapsed markup."""
    rendered = []

    def mock_render_html(markup):
        collapsed = html_block(markup)
        rendered.append(collapsed)

    monkeypatch.setattr("app.ui.landing.landing_page.render_html", mock_render_html)
    render_landing_page()

    assert len(rendered) == 2  # CSS + Landing Root
    assert "pf-landing-root" in rendered[1]
    assert "\n" not in rendered[1]  # Confirms html_block was applied properly
