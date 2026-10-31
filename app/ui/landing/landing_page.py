"""Master Landing Page Renderer for ProcessFoundry AI (Phase 1)."""
import streamlit as st
from app.ui.components import render_html
from app.ui.landing.styles import LANDING_CSS
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


def render_landing_page():
    """Render the complete, animated Phase 1 landing page."""
    # 1. Inject Stylesheet & Design Tokens
    render_html(LANDING_CSS)

    # 2. Render Full-Width Landing Root
    landing_markup = f"""
    <div class="pf-landing-root">
        {get_nav_html()}
        {get_hero_html()}
        {get_problem_html()}
        {get_how_it_works_html()}
        {get_features_html()}
        {get_why_different_html()}
        {get_use_cases_html()}
        {get_process_guide_html()}
        {get_expected_value_html()}
        {get_final_cta_html()}
        {get_footer_html()}
    </div>
    """
    render_html(landing_markup)
