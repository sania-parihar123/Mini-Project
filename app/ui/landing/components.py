"""Reusable Visual Components for the ProcessFoundry AI Landing Page."""
from app.ui.landing.illustrations import (
    HERO_PIPELINE_SVG,
    PROCESS_GUIDE_MOCKUP_SVG,
    FEATURE_ICONS
)


def get_nav_html() -> str:
    """Render the sticky, responsive Navigation Bar."""
    return """
    <div class="pf-nav-wrapper">
        <div class="pf-nav-inner">
            <a href="#hero" class="pf-logo-group">
                <div class="pf-logo-icon">P</div>
                <div class="pf-logo-text">
                    ProcessFoundry AI
                    <small>PROCESS INTELLIGENCE</small>
                </div>
            </a>
            <ul class="pf-nav-links">
                <li><a href="#hero">Home</a></li>
                <li><a href="#how-it-works">How It Works</a></li>
                <li><a href="#features">Features</a></li>
                <li><a href="#why-different">Why Us</a></li>
                <li><a href="#use-cases">Use Cases</a></li>
                <li><a href="#process-guide">Process Guide</a></li>
            </ul>
            <div class="pf-nav-actions">
                <a href="/?page=login" target="_self" class="pf-btn pf-btn-ghost">Sign In</a>
                <a href="/?page=signup" target="_self" class="pf-btn pf-btn-primary">Get Started →</a>
            </div>
        </div>
    </div>
    """


def get_hero_html() -> str:
    """Render Hero Section with Heading, CTAs, and Visual Pipeline."""
    return f"""
    <section id="hero" class="pf-hero-section">
        <div class="pf-container">
            <div class="pf-hero-grid">
                <div class="pf-hero-content">
                    <div class="pf-badge pf-badge-teal">
                        <span style="font-size:14px;">⚡</span> PHASE 1: DISCOVERY, BLUEPRINT &amp; PROCESS GUIDE
                    </div>
                    <h1 class="pf-hero-title">
                        Understand Your Processes. <span class="pf-accent-text">Build the Right Blueprint.</span>
                    </h1>
                    <p class="pf-hero-desc">
                        Discover how your processes actually work, uncover hidden rules and gaps, validate decisions with stakeholders and transform scattered knowledge into a structured process blueprint.
                    </p>
                    <div class="pf-hero-actions">
                        <a href="/?page=signup" target="_self" class="pf-btn pf-btn-primary pf-btn-lg">
                            Get Started Free →
                        </a>
                        <a href="#how-it-works" class="pf-btn pf-btn-secondary pf-btn-lg">
                            Explore How It Works
                        </a>
                    </div>
                    <div class="pf-hero-meta">
                        <div class="pf-hero-meta-item">
                            <span class="pf-check-icon">✓</span> 100% Verbatim Grounding
                        </div>
                        <div class="pf-hero-meta-item">
                            <span class="pf-check-icon">✓</span> Human Stakeholder Sign-Off
                        </div>
                        <div class="pf-hero-meta-item">
                            <span class="pf-check-icon">✓</span> Zero Hallucinations
                        </div>
                    </div>
                </div>
                <div class="pf-hero-visual-card">
                    <div class="pf-visual-header">
                        <div class="pf-visual-dots">
                            <div class="pf-dot pf-dot-red"></div>
                            <div class="pf-dot pf-dot-yellow"></div>
                            <div class="pf-dot pf-dot-green"></div>
                        </div>
                        <div class="pf-visual-title">Autonomous Process Intelligence Engine</div>
                    </div>
                    <div class="pf-float-anim">
                        {HERO_PIPELINE_SVG}
                    </div>
                </div>
            </div>
        </div>
    </section>
    """


def get_problem_html() -> str:
    """Render Section C: Problem We Solve."""
    problems = [
        ("📁", "Scattered Documents & Sheets", "Process rules and steps are fragmented across outdated SOPs, email threads, forms, spreadsheets, and informal memory."),
        ("❓", "Hidden Rules & Exceptions", "Critical boundary conditions, financial cut-offs, and approval exceptions are undocumented or applied inconsistently across desks."),
        ("⚡", "Policy vs Practice Mismatches", "What is written in official guidelines often completely diverges from actual day-to-day administrative practices."),
        ("🚨", "Late Requirement Surprises", "Missing prerequisites, conflicting mandates, and edge cases are uncovered late during digitisation or software building."),
        ("🔄", "Recreated Process Wheel", "Every time an audit occurs, staff changes, or software is procured, teams start from scratch re-documenting the same workflows.")
    ]
    cards_html = "".join([
        f"""
        <div class="pf-problem-card">
            <div class="pf-card-icon-wrap" style="font-size:22px;">{icon}</div>
            <h3>{title}</h3>
            <p>{desc}</p>
        </div>
        """
        for icon, title, desc in problems
    ])

    return f"""
    <section class="pf-problem-section">
        <div class="pf-container">
            <div style="text-align:center;">
                <div class="pf-badge pf-badge-navy">THE FOUNDATIONAL CHALLENGE</div>
                <h2 class="pf-section-title">Process Digitisation Should Start with Understanding</h2>
                <p class="pf-section-subtitle">
                    Automating a broken or misunderstood process only accelerates confusion. ProcessFoundry AI creates total visibility before you spend engineering effort.
                </p>
            </div>
            <div class="pf-problem-grid">
                {cards_html}
            </div>
        </div>
    </section>
    """


def get_how_it_works_html() -> str:
    """Render Section D: How ProcessFoundry AI Works (6 Stages)."""
    stages = [
        ("1", "📁", "Collect Sources", "Upload supported process documents, SOPs, forms, policies, spreadsheets, and operational records.", "Multi-Format Ingestion"),
        ("2", "🔍", "Discover Processes", "Identify sequential steps, participating actors, decision branches, and operational responsibilities.", "AI Discovery Engine"),
        ("3", "⚖️", "Analyse Rules", "Discover business rules, logic gaps, policy conflicts, and unhandled exception paths with verbatim citations.", "Gap & Conflict Mining"),
        ("4", "🛡️", "Human Validation", "Engage stakeholders with targeted, role-gated clarification questions to confirm decisions before formalisation.", "Stakeholder-in-the-Loop"),
        ("5", "✨", "Redesign Processes", "Synthesise an improved, optimised To-Be process model eliminating bottlenecks and redundancies.", "To-Be Synthesis"),
        ("6", "📦", "Generate Deliverables", "Produce verified requirements packs (BRD, FRD, PRD), architecture diagrams, prototype specs, and test/UAT suites.", "Traceable Artifacts")
    ]
    stages_html = "".join([
        f"""
        <div class="pf-stage-card">
            <div class="pf-stage-num-badge">0{num}</div>
            <div class="pf-stage-icon-wrap" style="font-size:24px;">{icon}</div>
            <h3>{title}</h3>
            <p>{desc}</p>
            <div class="pf-stage-tag">{tag}</div>
        </div>
        """
        for num, icon, title, desc, tag in stages
    ])

    return f"""
    <section id="how-it-works" class="pf-workflow-section">
        <div class="pf-container">
            <div style="text-align:center;">
                <div class="pf-badge pf-badge-navy">SYSTEMATIC 6-STAGE PIPELINE</div>
                <h2 class="pf-section-title">From Existing Knowledge to a Verified Process Blueprint</h2>
                <p class="pf-section-subtitle">
                    A deterministic pipeline that never hallucinates: every step is anchored in documented evidence and approved by authorized humans.
                </p>
            </div>
            <div class="pf-stages-grid">
                {stages_html}
            </div>
        </div>
    </section>
    """


def get_features_html() -> str:
    """Render Section E: 15 Core Features."""
    features = [
        ("multi_doc", "Multi-Document Ingestion", "Ingest multi-format files (PDF, DOCX, TXT, MD) and extract verbatim text sections with verified content checksums."),
        ("ai_discovery", "AI-Assisted Process Discovery", "Extract clear operational steps, trigger events, execution pathways, and handoffs directly from evidence."),
        ("actor_id", "Actor Identification", "Map stakeholder roles, departmental ownership, and individual responsibilities across the entire workflow lifecycle."),
        ("rule_extract", "Business Rule Extraction", "Mine operational constraints, calculation formulas, eligibility conditions, and statutory mandates with citation links."),
        ("gap_analysis", "Gap and Conflict Analysis", "Identify contradictions between different policy documents, missing decision paths, and undocumented edge cases."),
        ("human_in_loop", "Human-in-the-Loop Clarification", "Generate role-gated clarification questions so only the designated process owner or technical reviewer can confirm rules."),
        ("as_is_model", "As-Is Process Modelling", "Structure the current operational reality into standard stage-by-stage event models without artificial assumptions."),
        ("to_be_redesign", "To-Be Process Redesign", "Draft streamlined target workflows that remove paper bottlenecks, simplify handoffs, and accelerate turnaround."),
        ("req_eng", "Requirements Engineering", "Generate complete, structured Business (BRD), Functional (FRD), and Product (PRD) requirements packs ready for engineering."),
        ("data_arch", "Data & Architecture Design", "Map proposed entity models, state transition diagrams, field dictionaries, and system integration points."),
        ("prototype_gen", "Clickable Prototype Generation", "Produce interactive, clickable HTML/JS prototype specifications for stakeholder walk-throughs and visual sign-off."),
        ("test_cases", "Test Case & UAT Generation", "Derive end-to-end user acceptance scenarios, positive/negative tests, and edge-case validations directly from rules."),
        ("traceability", "Evidence-Based Traceability", "Link every single requirement and rule back to its verbatim source paragraph with zero-gap traceability matrix."),
        ("process_guide", "Verified Process Guide", "Provide staff with a role-filtered, approved reference manual and step-by-step checklists for daily execution."),
        ("doc_export", "Document and Artifact Export", "Download all generated blueprints, markdown specifications, Mermaid diagrams, and audit reports instantly.")
    ]

    cards_html = "".join([
        f"""
        <div class="pf-feature-card">
            <div class="pf-feat-icon-box">{FEATURE_ICONS.get(k, '')}</div>
            <div class="pf-feat-body">
                <h4>{title}</h4>
                <p>{desc}</p>
            </div>
        </div>
        """
        for k, title, desc in features
    ])

    return f"""
    <section id="features" class="pf-features-section">
        <div class="pf-container">
            <div style="text-align:center;">
                <div class="pf-badge pf-badge-teal">PHASE 1 CAPABILITIES</div>
                <h2 class="pf-section-title">Enterprise Intelligence for Every Process Dimension</h2>
                <p class="pf-section-subtitle">
                    Purpose-built analytical agents working in concert to turn raw organisational documents into audit-ready blueprints.
                </p>
            </div>
            <div class="pf-features-grid">
                {cards_html}
            </div>
        </div>
    </section>
    """


def get_why_different_html() -> str:
    """Render Section F: Why ProcessFoundry AI Is Different."""
    return """
    <section id="why-different" class="pf-different-section">
        <div class="pf-container">
            <div style="text-align:center;">
                <div class="pf-badge pf-badge-navy">ARCHITECTURAL DISTINCTION</div>
                <h2 class="pf-section-title">More Than a Generic AI Chatbot or Coding Agent</h2>
                <p class="pf-section-subtitle">
                    Chatbots chat and code generators invent assumptions. ProcessFoundry AI is an evidence-first system designed to resolve business complexity before writing code.
                </p>
            </div>
            <div class="pf-compare-grid">
                <div class="pf-compare-col-generic">
                    <h3 style="margin:0 0 16px 0;font-size:22px;color:#1E293B;">Generic AI Chatbot / Coding Agent</h3>
                    <p style="color:#64748B;font-size:14px;margin-bottom:24px;">Focuses on rushing into code or generating plausible-sounding conversational answers without verification.</p>
                    <div class="pf-compare-item">
                        <div class="pf-compare-status-bad">✕</div>
                        <div>
                            <h4 style="color:#1E293B;">Jumps Straight to Coding</h4>
                            <p style="color:#64748B;">Builds software before resolving conflicting policies or understanding true exception workflows.</p>
                        </div>
                    </div>
                    <div class="pf-compare-item">
                        <div class="pf-compare-status-bad">✕</div>
                        <div>
                            <h4 style="color:#1E293B;">Plausible Hallucinations</h4>
                            <p style="color:#64748B;">Invents rules, limits, and steps when documents are vague, introducing silent compliance errors.</p>
                        </div>
                    </div>
                    <div class="pf-compare-item">
                        <div class="pf-compare-status-bad">✕</div>
                        <div>
                            <h4 style="color:#1E293B;">Unchecked Auto-Approvals</h4>
                            <p style="color:#64748B;">Lacks human governance; AI assumes authority without asking authorized domain stakeholders.</p>
                        </div>
                    </div>
                    <div class="pf-compare-item">
                        <div class="pf-compare-status-bad">✕</div>
                        <div>
                            <h4 style="color:#1E293B;">Zero Traceability</h4>
                            <p style="color:#64748B;">Outputs black-box text where requirements cannot be traced back to authoritative policy clauses.</p>
                        </div>
                    </div>
                </div>

                <div class="pf-compare-col-pf">
                    <div class="pf-badge pf-badge-teal" style="margin-bottom:14px;">ENTERPRISE ASSURANCE</div>
                    <h3 style="margin:0 0 16px 0;font-size:22px;color:#FFFFFF;">ProcessFoundry AI Platform</h3>
                    <p style="color:#A0B2C6;font-size:14px;margin-bottom:24px;">Rigorous process intelligence engine engineered for institutional compliance and clarity.</p>
                    <div class="pf-compare-item">
                        <div class="pf-compare-status-good">✓</div>
                        <div>
                            <h4 style="color:#FFFFFF;">Starts Before Coding</h4>
                            <p style="color:#B3C4DB;">Discovers how work actually flows and settles business architecture before development starts.</p>
                        </div>
                    </div>
                    <div class="pf-compare-item">
                        <div class="pf-compare-status-good">✓</div>
                        <div>
                            <h4 style="color:#FFFFFF;">Evidence-Based Intelligence</h4>
                            <p style="color:#B3C4DB;">Every single claim is grounded in a verified verbatim quote extracted directly from source SOPs.</p>
                        </div>
                    </div>
                    <div class="pf-compare-item">
                        <div class="pf-compare-status-good">✓</div>
                        <div>
                            <h4 style="color:#FFFFFF;">Human-Approved Decisions</h4>
                            <p style="color:#B3C4DB;">AI never auto-approves; clarification questions are role-gated so authorized experts make the call.</p>
                        </div>
                    </div>
                    <div class="pf-compare-item">
                        <div class="pf-compare-status-good">✓</div>
                        <div>
                            <h4 style="color:#FFFFFF;">End-to-End Traceability</h4>
                            <p style="color:#B3C4DB;">Full bidirectional traceability from original document clause to BRD, prototype, and UAT test case.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    """


def get_use_cases_html() -> str:
    """Render Section G: Use Cases (Colleges & Diverse Organisations)."""
    return """
    <section id="use-cases" class="pf-usecases-section">
        <div class="pf-container">
            <div style="text-align:center;">
                <div class="pf-badge pf-badge-teal">VERSATILE APPLICABILITY</div>
                <h2 class="pf-section-title">One Platform for Different Types of Processes</h2>
                <p class="pf-section-subtitle">
                    From university academic registrar offices to enterprise shared services, ProcessFoundry AI accelerates understanding across diverse process ecosystems.
                </p>
            </div>
            <div class="pf-usecases-split">
                <!-- Academic / College Operations -->
                <div class="pf-usecase-category-card">
                    <div class="pf-usecase-category-header">
                        <div style="font-size:32px;">🎓</div>
                        <div>
                            <h3>Higher Education &amp; Colleges</h3>
                            <small style="color:#64748B;">Complex statutory policies with high student volume</small>
                        </div>
                    </div>
                    <ul class="pf-usecase-list">
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">1</div>
                            <div class="pf-usecase-text">
                                <b>Scholarship Application &amp; Verification</b>
                                <small>Multiple income criteria, caste quota verification, and multi-tier sanction approvals.</small>
                            </div>
                        </li>
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">2</div>
                            <div class="pf-usecase-text">
                                <b>Student Certificates &amp; Transcript Requests</b>
                                <small>No-dues clearance across library, labs, hostels, and registrar signature workflows.</small>
                            </div>
                        </li>
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">3</div>
                            <div class="pf-usecase-text">
                                <b>ID Correction &amp; Migration Requests</b>
                                <small>Document verification, university board approvals, and tamper-resistant record updates.</small>
                            </div>
                        </li>
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">4</div>
                            <div class="pf-usecase-text">
                                <b>Examination Corrections &amp; Revaluation</b>
                                <small>Anonymised paper dispatch, evaluator fee calculation, and marks re-tallying guidelines.</small>
                            </div>
                        </li>
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">5</div>
                            <div class="pf-usecase-text">
                                <b>Internship NOC &amp; Project Approvals</b>
                                <small>Industry alignment check, mentor assignment, and academic credit transfer validation.</small>
                            </div>
                        </li>
                    </ul>
                </div>

                <!-- Enterprise & Operations -->
                <div class="pf-usecase-category-card">
                    <div class="pf-usecase-category-header">
                        <div style="font-size:32px;">🏢</div>
                        <div>
                            <h3>Enterprise &amp; Shared Services</h3>
                            <small style="color:#64748B;">Multi-departmental operations and governance</small>
                        </div>
                    </div>
                    <ul class="pf-usecase-list">
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">1</div>
                            <div class="pf-usecase-text">
                                <b>Employee Onboarding &amp; Provisioning</b>
                                <small>Background checks, IT asset allocation, bank declarations, and compliance checklists.</small>
                            </div>
                        </li>
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">2</div>
                            <div class="pf-usecase-text">
                                <b>Vendor Registration &amp; Due Diligence</b>
                                <small>Tax registrations, statutory audit forms, risk categorisation, and procurement onboarding.</small>
                            </div>
                        </li>
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">3</div>
                            <div class="pf-usecase-text">
                                <b>Travel &amp; Expense Approvals</b>
                                <small>Per diem rules, advance clearances, receipt reconciliation, and policy exception audits.</small>
                            </div>
                        </li>
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">4</div>
                            <div class="pf-usecase-text">
                                <b>Customer Complaint &amp; Dispute Resolution</b>
                                <small>Escalation matrix, SLAs, refund authorization tiers, and compliance audit trail.</small>
                            </div>
                        </li>
                        <li class="pf-usecase-item">
                            <div class="pf-usecase-bullet">5</div>
                            <div class="pf-usecase-text">
                                <b>Internal Service Requests &amp; Case Handling</b>
                                <small>Facilities requests, legal contract reviews, and cross-departmental SLA handoffs.</small>
                            </div>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </section>
    """


def get_process_guide_html() -> str:
    """Render Section H: Verified Process Guide Concept."""
    return f"""
    <section id="process-guide" class="pf-guide-section">
        <div class="pf-container">
            <div style="text-align:center;">
                <div class="pf-badge pf-badge-teal">PHASE 1 CONCEPT CAPABILITY</div>
                <h2 class="pf-section-title">One Trusted Reference for Your Process Knowledge</h2>
                <p class="pf-section-subtitle">
                    Turn static documentation into an interactive, role-aware operational manual that answers staff queries strictly using human-approved rules.
                </p>
            </div>
            <div class="pf-guide-grid">
                <div class="pf-guide-mockup-card">
                    <div class="pf-guide-mockup-topbar">
                        <span style="font-size:12px;font-weight:700;letter-spacing:1px;color:#A0B2C6;">VERIFIED PROCESS GUIDE PREVIEW</span>
                        <span style="font-size:11px;background:#24426A;padding:3px 8px;border-radius:4px;color:#82DED0;">CONCEPT DEMO</span>
                    </div>
                    <div class="pf-guide-mockup-body">
                        {PROCESS_GUIDE_MOCKUP_SVG}
                    </div>
                </div>
                <div class="pf-guide-points-list">
                    <div class="pf-guide-point">
                        <div class="pf-guide-point-icon">✓</div>
                        <div>
                            <h4>Role-Based Answers from Approved Knowledge</h4>
                            <p>Staff members receive clear, accurate answers filtered by their specific role authority, completely eliminating speculative water-cooler interpretations.</p>
                        </div>
                    </div>
                    <div class="pf-guide-point">
                        <div class="pf-guide-point-icon">📋</div>
                        <div>
                            <h4>Actionable Operational Checklists</h4>
                            <p>Transform dense policy manuals into structured, step-by-step checklists that front-line operators can follow during case handling.</p>
                        </div>
                    </div>
                    <div class="pf-guide-point">
                        <div class="pf-guide-point-icon">👥</div>
                        <div>
                            <h4>Faster Staff Onboarding</h4>
                            <p>New employees master intricate operational SOPs in days instead of months by querying a system that cites verbatim clauses for every answer.</p>
                        </div>
                    </div>
                    <div class="pf-guide-point">
                        <div class="pf-guide-point-icon">🔄</div>
                        <div>
                            <h4>Drastic Drop in Repeated Clarifications</h4>
                            <p>Senior administrators spend significantly less time answering the same routine policy queries over phone calls and internal emails.</p>
                        </div>
                    </div>
                    <div class="pf-guide-point">
                        <div class="pf-guide-point-icon">🛡️</div>
                        <div>
                            <h4>Strict Hallucination Prevention</h4>
                            <p>The system refuses to answer when evidence is absent, triggering a structured question to the process owner instead of fabricating advice.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    """


def get_expected_value_html() -> str:
    """Render Section I: Expected Value & Pilot Targets."""
    metrics = [
        ("30%", "Faster Process Preparation", "Reduction in time required to prepare an approved process and complete requirements pack.", "PILOT TARGET"),
        ("≥90%", "Evidence Grounding Ratio", "Proportion of generated requirements linked directly to approved source document evidence.", "PILOT TARGET"),
        ("25%", "Fewer Rework Cycles", "Reduction in clarification queries and post-approval rework cycles during implementation.", "PILOT TARGET"),
        ("≥90%", "Critical Rule Coverage", "Coverage of critical business rules and exceptions by generated test and UAT cases.", "PILOT TARGET"),
        ("≥4/5", "Pilot Satisfaction", "Average user satisfaction and usefulness rating across pilot stakeholders and analysts.", "EVALUATION GOAL"),
        ("≥50%", "Faster Impact Reviews", "Faster review and identification of impacted workflow steps following an SOP change.", "PILOT TARGET")
    ]
    cards_html = "".join([
        f"""
        <div class="pf-value-card">
            <div class="pf-target-badge">{tag}</div>
            <div class="pf-value-metric">{metric}</div>
            <div class="pf-value-title">{title}</div>
            <p class="pf-value-desc">{desc}</p>
        </div>
        """
        for metric, title, desc, tag in metrics
    ])

    return f"""
    <section class="pf-value-section">
        <div class="pf-container">
            <div style="text-align:center;">
                <div class="pf-badge pf-badge-navy">PILOT EVALUATION TARGETS</div>
                <h2 class="pf-section-title">Measurable Value for Transformation Teams</h2>
                <p class="pf-section-subtitle">
                    Target evaluation metrics established for institutional pilots to objectively measure productivity, rigor, and compliance confidence.
                </p>
            </div>
            <div class="pf-value-grid">
                {cards_html}
            </div>
        </div>
    </section>
    """


def get_final_cta_html() -> str:
    """Render Section J: Final Call to Action."""
    return """
    <section class="pf-cta-section">
        <div class="pf-container">
            <div class="pf-cta-box">
                <div class="pf-badge pf-badge-teal">READY TO TRANSFORM YOUR WORKFLOWS</div>
                <h2>Start with Understanding.<br>Move Forward with Confidence.</h2>
                <p>
                    Bring your existing process documents and knowledge together. Discover what is happening today, validate what matters with stakeholders, and create an approved blueprint ready for digital transformation.
                </p>
                <div class="pf-cta-buttons">
                    <a href="/?page=signup" target="_self" class="pf-btn pf-btn-primary pf-btn-lg">
                        Get Started Free →
                    </a>
                    <a href="/?page=login" target="_self" class="pf-btn pf-btn-secondary pf-btn-lg">
                        Sign In to Workspace
                    </a>
                </div>
            </div>
        </div>
    </section>
    """


def get_footer_html() -> str:
    """Render Section K: Footer."""
    return """
    <footer class="pf-footer">
        <div class="pf-container">
            <div class="pf-footer-grid">
                <div class="pf-footer-brand">
                    <div class="pf-logo-group">
                        <div class="pf-logo-icon">P</div>
                        <div class="pf-logo-text" style="color:#ffffff;">
                            ProcessFoundry AI
                            <small style="color:#8E9DB2;">PROCESS INTELLIGENCE</small>
                        </div>
                    </div>
                    <p>
                        From scattered process knowledge to a verified digital workflow. Designed for institutions and enterprises that require audit-grade rigor.
                    </p>
                </div>
                <div class="pf-footer-col">
                    <h5>Platform</h5>
                    <ul>
                        <li><a href="#hero">Overview</a></li>
                        <li><a href="#how-it-works">How It Works</a></li>
                        <li><a href="#features">Core Features</a></li>
                        <li><a href="#process-guide">Process Guide</a></li>
                    </ul>
                </div>
                <div class="pf-footer-col">
                    <h5>Use Cases</h5>
                    <ul>
                        <li><a href="#use-cases">Higher Education</a></li>
                        <li><a href="#use-cases">Shared Services</a></li>
                        <li><a href="#use-cases">Student Services</a></li>
                        <li><a href="#use-cases">Policy Compliance</a></li>
                    </ul>
                </div>
                <div class="pf-footer-col">
                    <h5>Access</h5>
                    <ul>
                        <li><a href="/?page=login" target="_self">Sign In</a></li>
                        <li><a href="/?page=signup" target="_self">Create Account</a></li>
                        <li><a href="#why-different">Why Us</a></li>
                    </ul>
                </div>
            </div>
            <div class="pf-footer-bottom">
                <div>&copy; 2026 ProcessFoundry AI. All rights reserved. Phase 1 Platform.</div>
                <div style="color:#64748B;">Enterprise Process Discovery, Redesign &amp; Specification Platform</div>
            </div>
        </div>
    </footer>
    """
