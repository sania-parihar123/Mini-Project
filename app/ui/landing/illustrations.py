"""SVG Visuals, Diagrams, and Illustrations for ProcessFoundry AI Phase 1 Landing Page.

All illustrations follow the navy-blue and royal-blue theme (#10213B, #142943, #3563F6, #48C7B5).
"""

HERO_PIPELINE_SVG = """
<svg viewBox="0 0 760 500" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block;">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#10213B" />
      <stop offset="60%" stop-color="#142943" />
      <stop offset="100%" stop-color="#0E1C30" />
    </linearGradient>
    <linearGradient id="blueGlow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#3563F6" />
      <stop offset="100%" stop-color="#48C7B5" />
    </linearGradient>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#1E3557" />
      <stop offset="100%" stop-color="#172A45" />
    </linearGradient>
    <linearGradient id="cardHighlight" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#3563F6" stop-opacity="0.8" />
      <stop offset="100%" stop-color="#48C7B5" stop-opacity="0.8" />
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <!-- Background Base -->
  <rect width="760" height="500" rx="16" fill="url(#bgGrad)" />
  <rect x="0.5" y="0.5" width="759" height="499" rx="15.5" stroke="#223B5E" stroke-opacity="0.7" />

  <!-- Grid Pattern -->
  <g opacity="0.12">
    <path d="M0 50 H760 M0 100 H760 M0 150 H760 M0 200 H760 M0 250 H760 M0 300 H760 M0 350 H760 M0 400 H760 M0 450 H760" stroke="#79A8E2" stroke-width="1" stroke-dasharray="3 3"/>
    <path d="M50 0 V500 M100 0 V500 M150 0 V500 M200 0 V500 M250 0 V500 M300 0 V500 M350 0 V500 M400 0 V500 M450 0 V500 M500 0 V500 M550 0 V500 M600 0 V500 M650 0 V500 M700 0 V500" stroke="#79A8E2" stroke-width="1" stroke-dasharray="3 3"/>
  </g>

  <!-- Top App Frame Header -->
  <rect x="0" y="0" width="760" height="42" fill="#0C182A" rx="16" />
  <circle cx="24" cy="21" r="5" fill="#FF5F56" />
  <circle cx="40" cy="21" r="5" fill="#FFBD2E" />
  <circle cx="56" cy="21" r="5" fill="#27C93F" />
  <rect x="80" y="12" width="220" height="18" rx="5" fill="#172944" />
  <text x="92" y="25" fill="#889EBA" font-size="10.5" font-family="'Inter', sans-serif" font-weight="600">processfoundry.ai / discovery-engine</text>
  <rect x="630" y="11" width="105" height="20" rx="10" fill="rgba(72,199,181,0.15)" stroke="rgba(72,199,181,0.3)" />
  <text x="643" y="24" fill="#48C7B5" font-size="10" font-family="'Inter', sans-serif" font-weight="700">● PHASE 1 ACTIVE</text>

  <!-- Pipeline Connector Lines -->
  <path d="M 145 130 C 205 130, 205 210, 265 210" stroke="#3563F6" stroke-width="2.5" stroke-dasharray="5 3" opacity="0.8"/>
  <path d="M 395 210 C 445 210, 445 130, 495 130" stroke="#48C7B5" stroke-width="2.5" opacity="0.9"/>
  <path d="M 395 210 C 445 210, 445 290, 495 290" stroke="#3563F6" stroke-width="2.5" opacity="0.8"/>
  <path d="M 625 130 C 665 130, 665 210, 695 210" stroke="#48C7B5" stroke-width="2.5" stroke-dasharray="5 3" opacity="0.8"/>
  <path d="M 625 290 C 665 290, 665 210, 695 210" stroke="#3563F6" stroke-width="2.5" stroke-dasharray="5 3" opacity="0.8"/>

  <!-- Flow Arrows / Pulses -->
  <circle cx="205" cy="170" r="4" fill="#3563F6" filter="url(#glow)"/>
  <circle cx="445" cy="170" r="4" fill="#48C7B5" filter="url(#glow)"/>
  <circle cx="445" cy="250" r="4" fill="#3563F6" filter="url(#glow)"/>

  <!-- NODE 1: Sources & Records (Left) -->
  <g transform="translate(30, 75)">
    <rect width="130" height="110" rx="12" fill="url(#cardGrad)" stroke="#2B466D" stroke-width="1.5" />
    <rect x="0" y="0" width="130" height="4" rx="2" fill="#3563F6" />
    <rect x="14" y="14" width="28" height="28" rx="6" fill="rgba(53,99,246,0.2)" stroke="#3563F6" stroke-width="1" />
    <text x="21" y="32" fill="#8BB2FE" font-size="14" font-weight="900">📄</text>
    <text x="48" y="24" fill="#FFFFFF" font-size="11.5" font-family="'Inter', sans-serif" font-weight="700">Documents</text>
    <text x="48" y="36" fill="#8FA2BD" font-size="9" font-family="'Inter', sans-serif">SOPs & Records</text>
    <rect x="14" y="52" width="102" height="18" rx="4" fill="#14243A" />
    <text x="22" y="64" fill="#78D8C9" font-size="9" font-family="'Inter', sans-serif" font-weight="600">✓ PDFs, Forms, Sheets</text>
    <rect x="14" y="76" width="102" height="18" rx="4" fill="#14243A" />
    <text x="22" y="88" fill="#B3C4DB" font-size="9" font-family="'Inter', sans-serif">Verbatim Grounding</text>
  </g>

  <!-- NODE 1b: Staff Knowledge (Below) -->
  <g transform="translate(30, 230)">
    <rect width="130" height="90" rx="12" fill="url(#cardGrad)" stroke="#2B466D" stroke-width="1.5" />
    <rect x="0" y="0" width="130" height="4" rx="2" fill="#48C7B5" />
    <rect x="14" y="14" width="28" height="28" rx="6" fill="rgba(72,199,181,0.2)" stroke="#48C7B5" stroke-width="1" />
    <text x="20" y="33" fill="#48C7B5" font-size="14" font-weight="900">👥</text>
    <text x="48" y="24" fill="#FFFFFF" font-size="11.5" font-family="'Inter', sans-serif" font-weight="700">Staff Insights</text>
    <text x="48" y="36" fill="#8FA2BD" font-size="9" font-family="'Inter', sans-serif">Subject Experts</text>
    <rect x="14" y="52" width="102" height="24" rx="4" fill="#14243A" />
    <text x="22" y="67" fill="#8FA2BD" font-size="9" font-family="'Inter', sans-serif">Tacit Practice Capture</text>
  </g>
  <path d="M 160 275 C 210 275, 210 210, 265 210" stroke="#48C7B5" stroke-width="2.5" stroke-dasharray="5 3" opacity="0.8"/>

  <!-- NODE 2: AI Process Discovery (Center Stage) -->
  <g transform="translate(265, 135)">
    <rect width="135" height="150" rx="14" fill="#142B49" stroke="#3563F6" stroke-width="2" filter="url(#glow)" opacity="0.3"/>
    <rect width="135" height="150" rx="14" fill="#142B49" stroke="#3563F6" stroke-width="1.8" />
    <rect x="0" y="0" width="135" height="5" rx="2.5" fill="url(#cardHighlight)" />
    <circle cx="67" cy="40" r="22" fill="rgba(53,99,246,0.25)" stroke="#3563F6" stroke-width="1.5" />
    <text x="56" y="47" fill="#82DED0" font-size="20">⚡</text>
    <text x="67" y="78" fill="#FFFFFF" font-size="12" font-family="'Inter', sans-serif" font-weight="800" text-anchor="middle">AI Discovery</text>
    <text x="67" y="92" fill="#8FA2BD" font-size="9" font-family="'Inter', sans-serif" text-anchor="middle">Step & Actor Mining</text>
    
    <rect x="12" y="104" width="111" height="16" rx="4" fill="#0E1D33" />
    <text x="18" y="115" fill="#48C7B5" font-size="8.5" font-family="'Inter', sans-serif" font-weight="700">● 14 Steps Extracted</text>
    <rect x="12" y="124" width="111" height="16" rx="4" fill="#0E1D33" />
    <text x="18" y="135" fill="#93C5FD" font-size="8.5" font-family="'Inter', sans-serif" font-weight="700">● 5 Roles Identified</text>
  </g>

  <!-- NODE 3a: Rules & Gap Analysis (Top Right Branch) -->
  <g transform="translate(495, 70)">
    <rect width="135" height="120" rx="12" fill="url(#cardGrad)" stroke="#2B466D" stroke-width="1.5" />
    <rect x="0" y="0" width="135" height="4" rx="2" fill="#F59E0B" />
    <text x="16" y="26" fill="#FBBF24" font-size="12" font-weight="800">🔍 Rule & Gap Engine</text>
    <text x="16" y="40" fill="#8FA2BD" font-size="9" font-family="'Inter', sans-serif">Conflict & Policy Analysis</text>
    <rect x="12" y="52" width="111" height="18" rx="4" fill="#14243A" />
    <text x="20" y="64" fill="#F87171" font-size="8.5" font-family="'Inter', sans-serif" font-weight="700">⚠ 3 Missing Exceptions</text>
    <rect x="12" y="74" width="111" height="18" rx="4" fill="#14243A" />
    <text x="20" y="86" fill="#FBBF24" font-size="8.5" font-family="'Inter', sans-serif" font-weight="700">⚡ 2 Policy Clashes</text>
    <rect x="12" y="96" width="111" height="16" rx="4" fill="#14243A" />
    <text x="20" y="108" fill="#48C7B5" font-size="8.5" font-family="'Inter', sans-serif">Zero Hallucinations</text>
  </g>

  <!-- NODE 3b: Human-in-the-Loop Validation (Bottom Right Branch) -->
  <g transform="translate(495, 230)">
    <rect width="135" height="120" rx="12" fill="url(#cardGrad)" stroke="#48C7B5" stroke-width="1.5" />
    <rect x="0" y="0" width="135" height="4" rx="2" fill="#48C7B5" />
    <text x="16" y="26" fill="#48C7B5" font-size="12" font-weight="800">🛡 Human Validation</text>
    <text x="16" y="40" fill="#8FA2BD" font-size="9" font-family="'Inter', sans-serif">Targeted Stakeholder Qs</text>
    <rect x="12" y="52" width="111" height="24" rx="4" fill="#14243A" />
    <text x="18" y="64" fill="#FFFFFF" font-size="8.5" font-family="'Inter', sans-serif" font-weight="600">Dean / Owner Input</text>
    <text x="18" y="73" fill="#8FA2BD" font-size="7.5" font-family="'Inter', sans-serif">Mandatory Sign-off</text>
    <rect x="12" y="82" width="111" height="28" rx="4" fill="rgba(72,199,181,0.15)" stroke="rgba(72,199,181,0.4)" stroke-width="0.8"/>
    <text x="20" y="96" fill="#48C7B5" font-size="8.5" font-family="'Inter', sans-serif" font-weight="800">✓ VERIFIED BY HUMAN</text>
    <text x="20" y="106" fill="#B2DFDB" font-size="7.5" font-family="'Inter', sans-serif">Audit Chained SHA-256</text>
  </g>

  <!-- NODE 4: Final Phase 1 Deliverables Blueprint (Right Outcome) -->
  <g transform="translate(640, 140)">
    <rect width="105" height="140" rx="12" fill="#102540" stroke="#3563F6" stroke-width="1.8" />
    <rect x="0" y="0" width="105" height="4" rx="2" fill="url(#cardHighlight)" />
    <text x="12" y="24" fill="#FFFFFF" font-size="11" font-weight="800">Deliverables</text>
    <text x="12" y="36" fill="#8FA2BD" font-size="8" font-family="'Inter', sans-serif">Phase 1 Blueprint</text>

    <rect x="8" y="46" width="89" height="16" rx="3" fill="#172D4D" />
    <text x="13" y="57" fill="#82DED0" font-size="8" font-family="'Inter', sans-serif" font-weight="700">✓ To-Be Workflow</text>

    <rect x="8" y="66" width="89" height="16" rx="3" fill="#172D4D" />
    <text x="13" y="77" fill="#93C5FD" font-size="8" font-family="'Inter', sans-serif" font-weight="700">✓ BRD / FRD / PRD</text>

    <rect x="8" y="86" width="89" height="16" rx="3" fill="#172D4D" />
    <text x="13" y="97" fill="#82DED0" font-size="8" font-family="'Inter', sans-serif" font-weight="700">✓ Prototype Spec</text>

    <rect x="8" y="106" width="89" height="16" rx="3" fill="#172D4D" />
    <text x="13" y="117" fill="#93C5FD" font-size="8" font-family="'Inter', sans-serif" font-weight="700">✓ Test/UAT Suite</text>
  </g>

  <!-- Bottom Interactive Status Rail -->
  <g transform="translate(30, 400)">
    <rect width="700" height="74" rx="12" fill="#0D1A2E" stroke="#1D3352" stroke-width="1" />
    
    <g transform="translate(24, 16)">
      <circle cx="14" cy="18" r="14" fill="rgba(53,99,246,0.2)" stroke="#3563F6" />
      <text x="9" y="23" fill="#3563F6" font-size="13" font-weight="900">1</text>
      <text x="36" y="16" fill="#FFFFFF" font-size="11" font-weight="700">Ingest & Evidence</text>
      <text x="36" y="28" fill="#8FA2BD" font-size="9">Verbatim Quotations</text>
    </g>

    <path d="M 175 34 H 200" stroke="#304C72" stroke-width="1.5" stroke-dasharray="3 3"/>

    <g transform="translate(208, 16)">
      <circle cx="14" cy="18" r="14" fill="rgba(72,199,181,0.2)" stroke="#48C7B5" />
      <text x="9" y="23" fill="#48C7B5" font-size="13" font-weight="900">2</text>
      <text x="36" y="16" fill="#FFFFFF" font-size="11" font-weight="700">Rules & Gaps</text>
      <text x="36" y="28" fill="#8FA2BD" font-size="9">Zero-assumption</text>
    </g>

    <path d="M 345 34 H 370" stroke="#304C72" stroke-width="1.5" stroke-dasharray="3 3"/>

    <g transform="translate(378, 16)">
      <circle cx="14" cy="18" r="14" fill="rgba(245,158,11,0.2)" stroke="#F59E0B" />
      <text x="9" y="23" fill="#F59E0B" font-size="13" font-weight="900">3</text>
      <text x="36" y="16" fill="#FFFFFF" font-size="11" font-weight="700">Stakeholder Gate</text>
      <text x="36" y="28" fill="#8FA2BD" font-size="9">Human Approval</text>
    </g>

    <path d="M 520 34 H 545" stroke="#304C72" stroke-width="1.5" stroke-dasharray="3 3"/>

    <g transform="translate(555, 16)">
      <circle cx="14" cy="18" r="14" fill="rgba(72,199,181,0.2)" stroke="#48C7B5" />
      <text x="9" y="23" fill="#48C7B5" font-size="13" font-weight="900">4</text>
      <text x="36" y="16" fill="#FFFFFF" font-size="11" font-weight="700">Verified Blueprint</text>
      <text x="36" y="28" fill="#8FA2BD" font-size="9">100% Traceable Pack</text>
    </g>
  </g>
</svg>
"""

PROCESS_GUIDE_MOCKUP_SVG = """
<svg viewBox="0 0 620 440" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block;">
  <defs>
    <linearGradient id="guideBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#10213B" />
      <stop offset="100%" stop-color="#142943" />
    </linearGradient>
    <linearGradient id="tealGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#3563F6" />
      <stop offset="100%" stop-color="#48C7B5" />
    </linearGradient>
  </defs>

  <!-- Frame -->
  <rect width="620" height="440" rx="16" fill="url(#guideBg)" stroke="#233C5F" stroke-width="1.5"/>

  <!-- Top bar -->
  <rect width="620" height="44" rx="16" fill="#0C182A" />
  <circle cx="22" cy="22" r="5" fill="#FF5F56" />
  <circle cx="38" cy="22" r="5" fill="#FFBD2E" />
  <circle cx="54" cy="22" r="5" fill="#27C93F" />
  <text x="75" y="26" fill="#FFFFFF" font-size="12" font-family="'Inter', sans-serif" font-weight="700">Verified Process Guide</text>
  <rect x="440" y="12" width="160" height="22" rx="11" fill="rgba(72,199,181,0.15)" stroke="rgba(72,199,181,0.3)"/>
  <text x="452" y="26" fill="#48C7B5" font-size="10" font-family="'Inter', sans-serif" font-weight="700">🔒 CONCEPT CAPABILITY</text>

  <!-- Search / Query bar -->
  <g transform="translate(26, 62)">
    <rect width="568" height="46" rx="10" fill="#172B47" stroke="#2B466D" stroke-width="1.2"/>
    <text x="18" y="28" fill="#48C7B5" font-size="16">🔍</text>
    <text x="46" y="28" fill="#E2EAF5" font-size="12.5" font-family="'Inter', sans-serif" font-weight="500">"What documents are needed when family income exceeds threshold for scholarship?"</text>
    <rect x="495" y="10" width="60" height="26" rx="6" fill="#3563F6"/>
    <text x="512" y="27" fill="#FFFFFF" font-size="11" font-family="'Inter', sans-serif" font-weight="700">Ask</text>
  </g>

  <!-- Role Selector Filter -->
  <g transform="translate(26, 122)">
    <text x="0" y="16" fill="#8FA2BD" font-size="11" font-family="'Inter', sans-serif" font-weight="600">Active Role Context:</text>
    <rect x="110" y="2" width="130" height="22" rx="11" fill="#3563F6" />
    <text x="122" y="16" fill="#FFFFFF" font-size="10.5" font-family="'Inter', sans-serif" font-weight="700">✓ Verification Officer</text>
    <rect x="250" y="2" width="115" height="22" rx="11" fill="#172B47" stroke="#2B466D" />
    <text x="262" y="16" fill="#8FA2BD" font-size="10.5" font-family="'Inter', sans-serif">Dean of Academics</text>
    <rect x="375" y="2" width="95" height="22" rx="11" fill="#172B47" stroke="#2B466D" />
    <text x="388" y="16" fill="#8FA2BD" font-size="10.5" font-family="'Inter', sans-serif">Student Applicant</text>
  </g>

  <!-- Answer Card Grounded in Evidence -->
  <g transform="translate(26, 160)">
    <rect width="568" height="150" rx="12" fill="#152843" stroke="#2E4D76" stroke-width="1.2"/>
    <rect x="0" y="0" width="568" height="4" rx="2" fill="url(#tealGrad)" />

    <!-- Status pill -->
    <rect x="18" y="16" width="170" height="20" rx="6" fill="rgba(72,199,181,0.15)" stroke="rgba(72,199,181,0.3)"/>
    <text x="26" y="29" fill="#48C7B5" font-size="10" font-family="'Inter', sans-serif" font-weight="700">✓ APPROVED PROCESS RULE</text>

    <text x="18" y="58" fill="#FFFFFF" font-size="13" font-family="'Inter', sans-serif" font-weight="600">Rule BR-04: Income Certificate &amp; Tehsildar Attestation</text>
    <text x="18" y="78" fill="#B3C4DB" font-size="11.5" font-family="'Inter', sans-serif" font-weight="400">If annual household income is reported between ₹2.5L and ₹5.0L, the applicant must submit Form 16 or an attested affidavit signed by a Class-I Gazetted Magistrate.</text>

    <!-- Verbatim citation pill -->
    <rect x="18" y="104" width="532" height="32" rx="6" fill="#0D1A2E" stroke="#1F3656"/>
    <text x="28" y="122" fill="#82DED0" font-size="10" font-family="'Inter', sans-serif" font-weight="600">Source Quote:</text>
    <text x="105" y="122" fill="#93C5FD" font-size="10" font-family="'Inter', sans-serif" font-style="italic">"Clause 4.2: Affidavits older than 6 months shall not be entertained..." [Scholarship_SOP.pdf §4]</text>
  </g>

  <!-- Interactive Checklist Section -->
  <g transform="translate(26, 326)">
    <rect width="568" height="96" rx="10" fill="#112239" stroke="#213B5E"/>
    <text x="18" y="24" fill="#FFFFFF" font-size="12" font-family="'Inter', sans-serif" font-weight="700">Step-by-Step Operator Checklist</text>
    
    <g transform="translate(18, 38)">
      <rect width="16" height="16" rx="4" fill="#48C7B5"/>
      <text x="4" y="12" fill="#10213B" font-size="11" font-weight="900">✓</text>
      <text x="26" y="12" fill="#E2EAF5" font-size="11" font-family="'Inter', sans-serif">1. Verify Income Certificate authenticity via QR seal</text>
    </g>

    <g transform="translate(18, 64)">
      <rect width="16" height="16" rx="4" fill="#172B47" stroke="#3563F6"/>
      <text x="26" y="12" fill="#E2EAF5" font-size="11" font-family="'Inter', sans-serif">2. Cross-reference attendance records (> 75% requirement)</text>
    </g>
  </g>
</svg>
"""

# Reusable SVG Icons for the 15 Core Features
FEATURE_ICONS = {
    "multi_doc": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>""",
    "ai_discovery": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>""",
    "actor_id": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>""",
    "rule_extract": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path><line x1="9" y1="7" x2="15" y2="7"></line><line x1="9" y1="11" x2="13" y2="11"></line></svg>""",
    "gap_analysis": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>""",
    "human_in_loop": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 11 12 14 22 4"></polyline></svg>""",
    "as_is_model": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>""",
    "to_be_redesign": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>""",
    "req_eng": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>""",
    "data_arch": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>""",
    "prototype_gen": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>""",
    "test_cases": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="9 14 11 16 15 12"></polyline></svg>""",
    "traceability": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>""",
    "process_guide": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>""",
    "doc_export": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>"""
}
