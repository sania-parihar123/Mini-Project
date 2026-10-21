# 16 Visual Design Specification
Status: agreed
Source: Section 10.9 (UI Visual Reference Override), Part 10.7 [TEAM DECISION: REQUIRED]

## Purpose
Specify the exact design tokens, typography, layout geometry, responsive behavior, and component patterns implementing the professional SaaS visual language from `reference_prototype.html`.

## Requirements
- SPEC-16-01 The design system shall employ the exact palette tokens:
  - Deep Navy Sidebar: `#101F36`
  - Page Background: `#F5F7FB`
  - Main Body Ink: `#15243A`
  - Subtle Line Border: `#E5EAF1`
  - Primary Action Blue: `#3568F5` (hover: `#2455DF`)
  - Secondary Light Blue: `#EAF0FF`
  - Supporting Accent Teal: `#0D9B8A`
  - Status Pills:
    - In Progress / Info: Blue pill (`background: #EDF2FF; color: #355ED6`)
    - Approved / Success: Green pill (`background: #E2F8F1; color: #137C67`)
    - Waiting / Critical: Amber pill (`background: #FFF4D9; color: #96650B`)
    - Neutral / Draft: Gray pill (`background: #EEF1F5; color: #637188`)
- SPEC-16-02 Layout Structure:
  - Persistent left sidebar (250px on desktop) with brand mark, navigation items with icons, active highlight (`#223550`), and system health indicator.
  - Sticky top header (76px) with breadcrumb path, user avatar initials, user name, project role, and sign-out control.
  - Responsive content container (max-width 1450px) with generous padding (32px 36px 48px).
- SPEC-16-03 Split-Screen Authentication:
  - Clean left authentication form with display name, email, password, inline validation, and toggle links.
  - Right branded visual panel (`#10203A` gradient with teal accents), displaying product mission, bulleted value points, and workflow progression.
- SPEC-16-04 Streamlit integration via `app/ui/theme.py` injecting custom CSS rules, font declarations, and `.streamlit/config.toml` ensuring native Streamlit inputs and custom cards render seamlessly together.

## Acceptance criteria
- AC-16-01 (covers SPEC-16-01/02) When any workspace page renders, the deep navy sidebar, sticky header, and light grey-blue background are applied.
- AC-16-02 (covers SPEC-16-03) When an unauthenticated visitor visits the root, the split-screen authentication view renders with correct brand colors and sans-serif typography.

## Design notes
- Files: `.streamlit/config.toml`, `app/ui/theme.py`, `app/ui/components.py`.
- Font: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-16-01
  - `test_the_visual_design_tokens_from_section_10_9_are_defined` (`tests/test_spec_coverage.py`)
- SPEC-16-02
  - `test_the_workspace_shell_is_present` (`tests/test_spec_coverage.py`)
- SPEC-16-03
  - `test_the_split_screen_auth_view_is_implemented` (`tests/test_spec_coverage.py`)
- SPEC-16-04
  - `test_the_streamlit_theme_config_matches_the_tokens` (`tests/test_spec_coverage.py`)
