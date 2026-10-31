"""CSS Stylesheet and Animation Tokens for ProcessFoundry AI Phase 1 Landing Page."""

LANDING_CSS = """
<style>
/* ProcessFoundry AI Landing Page Tokens & Rules */
:root {
    --pf-dark-navy: #10213B;
    --pf-sec-navy: #142943;
    --pf-blue: #3563F6;
    --pf-blue-hover: #2251dc;
    --pf-light-blue: #EAF0FF;
    --pf-bg: #F4F7FC;
    --pf-white: #FFFFFF;
    --pf-text-primary: #17243A;
    --pf-text-muted: #64748B;
    --pf-accent-teal: #48C7B5;
    --pf-border: #E2E8F0;
    --pf-card-border: #E8EEF8;
    --pf-card-bg: #FFFFFF;
    --pf-radius-sm: 8px;
    --pf-radius-md: 14px;
    --pf-radius-lg: 20px;
    --pf-shadow-subtle: 0 4px 20px rgba(16, 33, 59, 0.04);
    --pf-shadow-hover: 0 16px 36px rgba(16, 33, 59, 0.09);
    --pf-shadow-glow: 0 0 28px rgba(53, 99, 246, 0.15);
}

/* Ensure landing page takes full container width */
.pf-landing-root {
    width: 100%;
    margin: 0;
    padding: 0;
    font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
    color: var(--pf-text-primary);
    background-color: var(--pf-bg);
    overflow-x: hidden;
    line-height: 1.6;
}

/* Hide Streamlit sidebar during landing view */
body:has(.pf-landing-root) section[data-testid="stSidebar"],
.pf-landing-active section[data-testid="stSidebar"] {
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
}

body:has(.pf-landing-root) .block-container {
    max-width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Smooth Scrolling */
html {
    scroll-behavior: smooth;
}

/* Typography Helpers */
.pf-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    background: var(--pf-light-blue);
    color: var(--pf-blue);
    border: 1px solid rgba(53, 99, 246, 0.2);
}

.pf-badge-teal {
    background: #e6faf7;
    color: #0b8a7c;
    border: 1px solid rgba(72, 199, 181, 0.35);
}

.pf-badge-navy {
    background: #142943;
    color: #82ded0;
    border: 1px solid rgba(130, 222, 208, 0.3);
}

.pf-section-title {
    font-size: 36px;
    font-weight: 800;
    line-height: 1.2;
    letter-spacing: -0.03em;
    color: var(--pf-text-primary);
    margin: 12px 0 16px 0;
}

.pf-section-subtitle {
    font-size: 16.5px;
    color: var(--pf-text-muted);
    max-width: 720px;
    margin: 0 auto;
    line-height: 1.65;
}

.pf-container {
    max-width: 1220px;
    margin: 0 auto;
    padding: 0 28px;
}

/* Navigation Bar */
.pf-nav-wrapper {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--pf-border);
    transition: all 0.25s ease;
}

.pf-nav-inner {
    max-width: 1220px;
    margin: 0 auto;
    padding: 14px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.pf-logo-group {
    display: flex;
    align-items: center;
    gap: 12px;
    text-decoration: none;
    color: var(--pf-text-primary);
}

.pf-logo-icon {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, #3563F6, #48C7B5);
    display: grid;
    place-items: center;
    color: #ffffff;
    font-weight: 900;
    font-size: 20px;
    box-shadow: 0 4px 12px rgba(53, 99, 246, 0.28);
}

.pf-logo-text {
    font-size: 19px;
    font-weight: 800;
    letter-spacing: -0.4px;
    color: var(--pf-text-primary);
    display: flex;
    flex-direction: column;
}

.pf-logo-text small {
    font-size: 9px;
    letter-spacing: 1.6px;
    color: var(--pf-text-muted);
    font-weight: 700;
    margin-top: -2px;
}

.pf-nav-links {
    display: flex;
    align-items: center;
    gap: 26px;
    list-style: none;
    margin: 0;
    padding: 0;
}

.pf-nav-links a {
    text-decoration: none;
    color: var(--pf-text-muted);
    font-size: 14px;
    font-weight: 600;
    transition: color 0.18s ease;
}

.pf-nav-links a:hover {
    color: var(--pf-blue);
}

.pf-nav-actions {
    display: flex;
    align-items: center;
    gap: 12px;
}

/* Button Styles */
.pf-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 11px 22px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    white-space: nowrap;
}

.pf-btn-primary {
    background: var(--pf-blue);
    color: #ffffff !important;
    border: 1px solid var(--pf-blue);
    box-shadow: 0 4px 14px rgba(53, 99, 246, 0.25);
}

.pf-btn-primary:hover {
    background: var(--pf-blue-hover);
    border-color: var(--pf-blue-hover);
    transform: translateY(-2px);
    box-shadow: 0 8px 22px rgba(53, 99, 246, 0.35);
}

.pf-btn-secondary {
    background: var(--pf-white);
    color: var(--pf-text-primary) !important;
    border: 1px solid var(--pf-border);
}

.pf-btn-secondary:hover {
    border-color: var(--pf-blue);
    color: var(--pf-blue) !important;
    transform: translateY(-2px);
    box-shadow: var(--pf-shadow-subtle);
}

.pf-btn-ghost {
    background: transparent;
    color: var(--pf-text-primary) !important;
    border: 1px solid transparent;
}

.pf-btn-ghost:hover {
    color: var(--pf-blue) !important;
    background: var(--pf-light-blue);
}

.pf-btn-lg {
    padding: 14px 30px;
    font-size: 15.5px;
    border-radius: 12px;
}

/* Hero Section */
.pf-hero-section {
    padding: 72px 0 64px 0;
    background: radial-gradient(circle at 80% 12%, rgba(53, 99, 246, 0.07) 0%, transparent 50%),
                radial-gradient(circle at 10% 40%, rgba(72, 199, 181, 0.08) 0%, transparent 45%),
                var(--pf-bg);
    position: relative;
    border-bottom: 1px solid var(--pf-border);
}

.pf-hero-grid {
    display: grid;
    grid-template-columns: 1.05fr 1.15fr;
    gap: 48px;
    align-items: center;
}

.pf-hero-content {
    animation: pf-fade-up 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.pf-hero-title {
    font-size: 48px;
    font-weight: 900;
    line-height: 1.12;
    letter-spacing: -0.04em;
    color: var(--pf-dark-navy);
    margin: 18px 0 20px 0;
}

.pf-hero-title .pf-accent-text {
    background: linear-gradient(135deg, #3563F6 30%, #48C7B5 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.pf-hero-desc {
    font-size: 17.5px;
    color: var(--pf-text-muted);
    line-height: 1.7;
    margin-bottom: 32px;
}

.pf-hero-actions {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 34px;
    flex-wrap: wrap;
}

.pf-hero-meta {
    display: flex;
    align-items: center;
    gap: 22px;
    padding-top: 24px;
    border-top: 1px solid var(--pf-border);
    font-size: 13px;
    color: var(--pf-text-muted);
}

.pf-hero-meta-item {
    display: flex;
    align-items: center;
    gap: 7px;
}

.pf-check-icon {
    color: #0b8a7c;
    font-weight: 800;
}

/* Hero Visual Box */
.pf-hero-visual-card {
    background: #ffffff;
    border-radius: var(--pf-radius-lg);
    border: 1px solid var(--pf-card-border);
    box-shadow: 0 24px 60px rgba(16, 33, 59, 0.09);
    padding: 22px;
    position: relative;
    overflow: hidden;
    animation: pf-fade-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.pf-visual-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 16px;
    margin-bottom: 16px;
    border-bottom: 1px solid #EEF2F6;
}

.pf-visual-dots {
    display: flex;
    gap: 6px;
}

.pf-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
}
.pf-dot-red { background: #FF5F56; }
.pf-dot-yellow { background: #FFBD2E; }
.pf-dot-green { background: #27C93F; }

.pf-visual-title {
    font-size: 12px;
    font-weight: 700;
    color: #64748B;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* Animations */
@keyframes pf-fade-up {
    0% {
        opacity: 0;
        transform: translateY(24px);
    }
    100% {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes pf-float-slow {
    0%, 100% {
        transform: translateY(0);
    }
    50% {
        transform: translateY(-6px);
    }
}

@keyframes pf-pulse-glow {
    0%, 100% {
        opacity: 0.8;
        transform: scale(1);
    }
    50% {
        opacity: 1;
        transform: scale(1.03);
    }
}

.pf-float-anim {
    animation: pf-float-slow 5s ease-in-out infinite;
}

.pf-pulse-anim {
    animation: pf-pulse-glow 3s ease-in-out infinite;
}

/* Problem Section */
.pf-problem-section {
    padding: 88px 0;
    background: #ffffff;
    border-bottom: 1px solid var(--pf-border);
}

.pf-problem-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 24px;
    margin-top: 52px;
}

.pf-problem-card {
    background: var(--pf-bg);
    border: 1px solid var(--pf-card-border);
    border-radius: var(--pf-radius-md);
    padding: 30px 26px;
    transition: all 0.25s ease;
    display: flex;
    flex-direction: column;
}

.pf-problem-card:hover {
    transform: translateY(-5px);
    background: #ffffff;
    border-color: #CBD5E1;
    box-shadow: var(--pf-shadow-hover);
}

.pf-card-icon-wrap {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    background: var(--pf-light-blue);
    display: grid;
    place-items: center;
    color: var(--pf-blue);
    margin-bottom: 20px;
}

.pf-problem-card h3 {
    font-size: 19px;
    font-weight: 700;
    color: var(--pf-text-primary);
    margin: 0 0 10px 0;
}

.pf-problem-card p {
    font-size: 14.5px;
    color: var(--pf-text-muted);
    margin: 0;
    line-height: 1.6;
}

/* How It Works Section */
.pf-workflow-section {
    padding: 96px 0;
    background: var(--pf-dark-navy);
    color: #ffffff;
    position: relative;
    overflow: hidden;
}

.pf-workflow-section .pf-section-title {
    color: #ffffff;
}

.pf-workflow-section .pf-section-subtitle {
    color: #A0B2C6;
}

.pf-stages-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 28px;
    margin-top: 60px;
    position: relative;
}

.pf-stage-card {
    background: #142943;
    border: 1px solid #223c5e;
    border-radius: var(--pf-radius-md);
    padding: 32px 26px;
    transition: all 0.25s ease;
    position: relative;
}

.pf-stage-card:hover {
    transform: translateY(-6px);
    border-color: #48C7B5;
    background: #183354;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.35);
}

.pf-stage-num-badge {
    position: absolute;
    top: 22px;
    right: 22px;
    font-size: 28px;
    font-weight: 900;
    color: rgba(255, 255, 255, 0.1);
    letter-spacing: -1px;
}

.pf-stage-icon-wrap {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    background: rgba(53, 99, 246, 0.18);
    border: 1px solid rgba(53, 99, 246, 0.4);
    display: grid;
    place-items: center;
    color: #82ded0;
    margin-bottom: 22px;
}

.pf-stage-card h3 {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    margin: 0 0 10px 0;
}

.pf-stage-card p {
    font-size: 14px;
    color: #b5c7db;
    margin: 0;
    line-height: 1.6;
}

.pf-stage-tag {
    display: inline-block;
    margin-top: 18px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: #48C7B5;
    background: rgba(72, 199, 181, 0.12);
    padding: 4px 10px;
    border-radius: 6px;
}

/* Core Features Section */
.pf-features-section {
    padding: 96px 0;
    background: var(--pf-bg);
    border-bottom: 1px solid var(--pf-border);
}

.pf-features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 22px;
    margin-top: 56px;
}

.pf-feature-card {
    background: #ffffff;
    border: 1px solid var(--pf-card-border);
    border-radius: var(--pf-radius-md);
    padding: 26px;
    transition: all 0.22s ease;
    display: flex;
    gap: 18px;
    align-items: flex-start;
}

.pf-feature-card:hover {
    transform: translateY(-4px);
    border-color: var(--pf-blue);
    box-shadow: var(--pf-shadow-hover);
}

.pf-feat-icon-box {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    background: var(--pf-light-blue);
    color: var(--pf-blue);
    display: grid;
    place-items: center;
    flex-shrink: 0;
}

.pf-feat-body h4 {
    font-size: 17px;
    font-weight: 700;
    color: var(--pf-text-primary);
    margin: 0 0 6px 0;
}

.pf-feat-body p {
    font-size: 13.5px;
    color: var(--pf-text-muted);
    margin: 0;
    line-height: 1.55;
}

/* Why Different Section */
.pf-different-section {
    padding: 96px 0;
    background: #ffffff;
    border-bottom: 1px solid var(--pf-border);
}

.pf-compare-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 32px;
    margin-top: 54px;
}

.pf-compare-col-generic {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: var(--pf-radius-lg);
    padding: 38px 32px;
}

.pf-compare-col-pf {
    background: linear-gradient(145deg, #10213B, #142943);
    border: 1px solid #2b456b;
    border-radius: var(--pf-radius-lg);
    padding: 38px 32px;
    color: #ffffff;
    box-shadow: 0 20px 48px rgba(16, 33, 59, 0.16);
    position: relative;
}

.pf-compare-item {
    display: flex;
    gap: 16px;
    margin-top: 24px;
    align-items: flex-start;
}

.pf-compare-status-bad {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #FEE2E2;
    color: #DC2626;
    display: grid;
    place-items: center;
    font-weight: 800;
    font-size: 13px;
    flex-shrink: 0;
}

.pf-compare-status-good {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: rgba(72, 199, 181, 0.2);
    color: #48C7B5;
    border: 1px solid rgba(72, 199, 181, 0.4);
    display: grid;
    place-items: center;
    font-weight: 800;
    font-size: 13px;
    flex-shrink: 0;
}

.pf-compare-item h4 {
    margin: 0 0 4px 0;
    font-size: 16px;
    font-weight: 700;
}

.pf-compare-item p {
    margin: 0;
    font-size: 14px;
    line-height: 1.55;
}

/* Use Cases Section */
.pf-usecases-section {
    padding: 96px 0;
    background: var(--pf-bg);
    border-bottom: 1px solid var(--pf-border);
}

.pf-usecases-split {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 32px;
    margin-top: 54px;
}

.pf-usecase-category-card {
    background: #ffffff;
    border: 1px solid var(--pf-card-border);
    border-radius: var(--pf-radius-lg);
    padding: 36px 30px;
    box-shadow: var(--pf-shadow-subtle);
}

.pf-usecase-category-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 24px;
    padding-bottom: 18px;
    border-bottom: 1px solid var(--pf-border);
}

.pf-usecase-category-header h3 {
    margin: 0;
    font-size: 22px;
    font-weight: 800;
    color: var(--pf-dark-navy);
}

.pf-usecase-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.pf-usecase-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
}

.pf-usecase-bullet {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    background: var(--pf-light-blue);
    color: var(--pf-blue);
    display: grid;
    place-items: center;
    font-size: 11px;
    font-weight: 800;
    flex-shrink: 0;
    margin-top: 2px;
}

.pf-usecase-text {
    font-size: 14.5px;
    color: var(--pf-text-primary);
    font-weight: 500;
}

.pf-usecase-text small {
    display: block;
    color: var(--pf-text-muted);
    font-size: 12.5px;
    margin-top: 2px;
}

/* Process Guide Section */
.pf-guide-section {
    padding: 96px 0;
    background: #ffffff;
    border-bottom: 1px solid var(--pf-border);
}

.pf-guide-grid {
    display: grid;
    grid-template-columns: 1.05fr 1.15fr;
    gap: 48px;
    align-items: center;
    margin-top: 54px;
}

.pf-guide-mockup-card {
    background: #10213B;
    border: 1px solid #233a59;
    border-radius: var(--pf-radius-lg);
    box-shadow: 0 24px 60px rgba(16, 33, 59, 0.18);
    overflow: hidden;
    color: #ffffff;
}

.pf-guide-mockup-topbar {
    background: #142943;
    padding: 14px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #223c5e;
}

.pf-guide-mockup-body {
    padding: 24px;
}

.pf-guide-points-list {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.pf-guide-point {
    display: flex;
    gap: 16px;
    align-items: flex-start;
}

.pf-guide-point-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: #e6faf7;
    color: #0b8a7c;
    display: grid;
    place-items: center;
    font-weight: 800;
    font-size: 15px;
    flex-shrink: 0;
}

.pf-guide-point h4 {
    margin: 0 0 4px 0;
    font-size: 17px;
    font-weight: 700;
    color: var(--pf-text-primary);
}

.pf-guide-point p {
    margin: 0;
    font-size: 14px;
    color: var(--pf-text-muted);
    line-height: 1.55;
}

/* Expected Value Section */
.pf-value-section {
    padding: 96px 0;
    background: var(--pf-dark-navy);
    color: #ffffff;
    border-bottom: 1px solid #1c3352;
}

.pf-value-section .pf-section-title {
    color: #ffffff;
}

.pf-value-section .pf-section-subtitle {
    color: #A0B2C6;
}

.pf-value-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 26px;
    margin-top: 54px;
}

.pf-value-card {
    background: #142943;
    border: 1px solid #243f63;
    border-radius: var(--pf-radius-md);
    padding: 32px 26px;
    transition: all 0.25s ease;
    text-align: left;
}

.pf-value-card:hover {
    transform: translateY(-5px);
    border-color: #3563F6;
    background: #183354;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.25);
}

.pf-value-metric {
    font-size: 42px;
    font-weight: 900;
    letter-spacing: -1.5px;
    color: #82ded0;
    line-height: 1;
    margin-bottom: 12px;
}

.pf-value-title {
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 8px;
}

.pf-value-desc {
    font-size: 13.5px;
    color: #b5c7db;
    line-height: 1.55;
    margin: 0;
}

.pf-target-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #93c5fd;
    background: rgba(53, 99, 246, 0.2);
    border: 1px solid rgba(53, 99, 246, 0.35);
    padding: 3px 8px;
    border-radius: 4px;
    margin-bottom: 14px;
}

/* Final CTA Section */
.pf-cta-section {
    padding: 96px 0;
    background: radial-gradient(circle at 50% 30%, #1f4270 0%, #10213B 70%);
    color: #ffffff;
    text-align: center;
    position: relative;
}

.pf-cta-box {
    max-width: 820px;
    margin: 0 auto;
}

.pf-cta-box h2 {
    font-size: 44px;
    font-weight: 900;
    letter-spacing: -0.04em;
    line-height: 1.15;
    margin: 16px 0 20px 0;
    color: #ffffff;
}

.pf-cta-box p {
    font-size: 17.5px;
    color: #c4d7ec;
    line-height: 1.7;
    margin-bottom: 36px;
}

.pf-cta-buttons {
    display: flex;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
}

/* Footer */
.pf-footer {
    background: #0B1626;
    color: #8E9DB2;
    padding: 68px 0 36px 0;
    border-top: 1px solid #192d47;
    font-size: 13.5px;
}

.pf-footer-grid {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 1fr;
    gap: 48px;
    margin-bottom: 48px;
}

.pf-footer-brand p {
    margin: 14px 0 0 0;
    line-height: 1.65;
    color: #8E9DB2;
    max-width: 320px;
}

.pf-footer-col h5 {
    color: #ffffff;
    font-size: 13.5px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin: 0 0 18px 0;
}

.pf-footer-col ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 11px;
}

.pf-footer-col a {
    color: #8E9DB2;
    text-decoration: none;
    transition: color 0.18s ease;
}

.pf-footer-col a:hover {
    color: #48C7B5;
}

.pf-footer-bottom {
    padding-top: 28px;
    border-top: 1px solid #16263b;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12.5px;
}

/* Reduced Motion Preference Accessibility */
@media (prefers-reduced-motion: reduce) {
    *, ::before, ::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
}

/* Responsive Breakpoints */
@media (max-width: 1024px) {
    .pf-hero-grid {
        grid-template-columns: 1fr;
        gap: 40px;
    }
    .pf-stages-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .pf-compare-grid {
        grid-template-columns: 1fr;
    }
    .pf-usecases-split {
        grid-template-columns: 1fr;
    }
    .pf-guide-grid {
        grid-template-columns: 1fr;
    }
    .pf-value-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .pf-footer-grid {
        grid-template-columns: 1fr 1fr;
    }
}

@media (max-width: 768px) {
    .pf-nav-links {
        display: none;
    }
    .pf-hero-title {
        font-size: 34px;
    }
    .pf-section-title {
        font-size: 28px;
    }
    .pf-stages-grid {
        grid-template-columns: 1fr;
    }
    .pf-value-grid {
        grid-template-columns: 1fr;
    }
    .pf-footer-grid {
        grid-template-columns: 1fr;
        gap: 32px;
    }
    .pf-footer-bottom {
        flex-direction: column;
        gap: 12px;
        text-align: center;
    }
}
</style>
"""
