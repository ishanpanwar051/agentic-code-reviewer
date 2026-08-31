"""
ui/styles.py — Unified App-Wide CSS Stylesheet for PR Sage Dashboard.
Generated deterministically from theme tokens. Applied once at app root.
"""
from __future__ import annotations

from ui.theme import COLORS, TYPOGRAPHY, SPACING, RADII, SHADOWS


def get_application_styles() -> str:
    """Returns the complete production CSS string for the Streamlit dashboard."""
    return f"""
<style>
  /* ─────────────────────────────────────────────────────────────────────────────
     Global App Canvas & Reset
     ───────────────────────────────────────────────────────────────────────────── */
  .stApp {{
      background-color: {COLORS.bg_app};
      background-image: 
          radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.08) 0px, transparent 50%),
          radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.06) 0px, transparent 50%);
      color: {COLORS.text_primary};
      font-family: {TYPOGRAPHY.font_sans};
      -webkit-font-smoothing: antialiased;
  }}

  /* Streamlit default container padding adjustments */
  .block-container {{
      padding-top: 1.5rem;
      padding-bottom: 3rem;
      max-width: 1380px;
  }}

  /* Sidebar polish */
  section[data-testid="stSidebar"] {{
      background-color: {COLORS.bg_surface};
      border-right: 1px solid {COLORS.border_subtle};
  }}

  /* ─────────────────────────────────────────────────────────────────────────────
     Top Enterprise Navigation Bar
     ───────────────────────────────────────────────────────────────────────────── */
  .enterprise-nav {{
      background: {COLORS.bg_surface_glass};
      backdrop-filter: blur(12px);
      border: 1px solid {COLORS.border_default};
      border-radius: {RADII.lg};
      padding: 16px 22px;
      margin-bottom: 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      box-shadow: {SHADOWS.md};
      gap: 12px;
  }}
  .brand-container {{
      display: flex;
      align-items: center;
      gap: 14px;
  }}
  .brand-logo-icon {{
      font-size: 1.8rem;
      background: {COLORS.bg_surface_elevated};
      padding: 8px 10px;
      border-radius: {RADII.md};
      border: 1px solid {COLORS.border_accent};
  }}
  .brand-title {{
      font-size: {TYPOGRAPHY.size_lg};
      font-weight: 700;
      color: {COLORS.text_primary};
      letter-spacing: -0.3px;
      margin: 0;
  }}
  .brand-sub {{
      font-size: {TYPOGRAPHY.size_sm};
      color: {COLORS.text_muted};
      margin-top: 2px;
  }}
  .nav-badges {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
  }}
  .engine-pill {{
      font-size: {TYPOGRAPHY.size_xs};
      font-family: {TYPOGRAPHY.font_mono};
      color: {COLORS.accent_purple_light};
      background: rgba(139, 92, 246, 0.12);
      padding: 4px 12px;
      border-radius: {RADII.pill};
      border: 1px solid rgba(139, 92, 246, 0.3);
      font-weight: 600;
  }}
  .status-pill {{
      font-size: {TYPOGRAPHY.size_xs};
      color: {COLORS.success_text};
      background: {COLORS.success_bg};
      padding: 4px 12px;
      border-radius: {RADII.pill};
      border: 1px solid {COLORS.success_border};
      font-weight: 600;
  }}

  /* ─────────────────────────────────────────────────────────────────────────────
     Score HUD & Metric Cards
     ───────────────────────────────────────────────────────────────────────────── */
  .score-container {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
  }}
  .score-card {{
      background: {COLORS.bg_surface};
      border: 1px solid {COLORS.border_default};
      border-radius: {RADII.md};
      padding: 14px 16px;
      text-align: center;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      box-shadow: {SHADOWS.sm};
  }}
  .score-card:hover {{
      border-color: {COLORS.border_accent};
      transform: translateY(-2px);
      box-shadow: {SHADOWS.md};
  }}
  .score-val {{
      font-size: {TYPOGRAPHY.size_2xl};
      font-weight: 800;
      line-height: 1.1;
      margin-bottom: 4px;
      letter-spacing: -0.5px;
  }}
  .score-lbl {{
      font-size: {TYPOGRAPHY.size_xs};
      color: {COLORS.text_muted};
      text-transform: uppercase;
      letter-spacing: 0.6px;
      font-weight: 600;
  }}

  /* ─────────────────────────────────────────────────────────────────────────────
     Live 4-Stage State Pipeline Radar
     ───────────────────────────────────────────────────────────────────────────── */
  .pipeline-bar {{
      display: flex;
      background: {COLORS.bg_surface};
      border: 1px solid {COLORS.border_default};
      border-radius: {RADII.md};
      padding: 12px 18px;
      margin-bottom: 22px;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      box-shadow: {SHADOWS.sm};
  }}
  .pipeline-step {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: {TYPOGRAPHY.size_sm};
      font-weight: 600;
      color: {COLORS.text_secondary};
  }}
  .step-dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
  }}
  .step-dot-ok {{
      background: {COLORS.success};
      box-shadow: {SHADOWS.glow_success};
  }}
  .step-dot-warn {{
      background: {COLORS.warning};
      box-shadow: 0 0 8px {COLORS.warning};
  }}
  .step-dot-crit {{
      background: {COLORS.critical};
      box-shadow: {SHADOWS.glow_critical};
  }}
  .pipeline-arrow {{
      color: {COLORS.border_default};
      font-size: {TYPOGRAPHY.size_sm};
  }}

  /* ─────────────────────────────────────────────────────────────────────────────
     GitHub PR-Style Inline Comment Thread Cards
     ───────────────────────────────────────────────────────────────────────────── */
  .diff-card {{
      background: {COLORS.bg_surface};
      border: 1px solid {COLORS.border_default};
      border-radius: {RADII.md};
      margin-bottom: 16px;
      overflow: hidden;
      box-shadow: {SHADOWS.sm};
      transition: border-color 0.15s ease;
  }}
  .diff-card:hover {{
      border-color: {COLORS.border_accent};
  }}
  .diff-header {{
      background: {COLORS.bg_surface_elevated};
      padding: 10px 16px;
      border-bottom: 1px solid {COLORS.border_subtle};
      font-family: {TYPOGRAPHY.font_mono};
      font-size: {TYPOGRAPHY.size_sm};
      color: {COLORS.text_secondary};
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
  }}
  .diff-body {{
      padding: 14px 16px;
      font-family: {TYPOGRAPHY.font_mono};
      font-size: {TYPOGRAPHY.size_sm};
      line-height: 1.5;
  }}
  .diff-bad-line {{
      background: {COLORS.critical_bg};
      border-left: 3px solid {COLORS.critical};
      padding: 6px 10px;
      margin: 6px 0;
      color: {COLORS.critical_text};
      border-radius: 0 {RADII.xs} {RADII.xs} 0;
      white-space: pre-wrap;
      word-break: break-all;
  }}
  .diff-fix-line {{
      background: {COLORS.success_bg};
      border-left: 3px solid {COLORS.success};
      padding: 6px 10px;
      margin: 6px 0;
      color: {COLORS.success_text};
      border-radius: 0 {RADII.xs} {RADII.xs} 0;
      white-space: pre-wrap;
      word-break: break-all;
  }}
  .comment-thread {{
      background: {COLORS.bg_surface_elevated};
      border: 1px solid {COLORS.border_subtle};
      border-radius: {RADII.sm};
      padding: 12px 14px;
      margin: 12px 0 4px 0;
  }}
  .comment-author {{
      font-weight: 600;
      color: {COLORS.text_primary};
      margin-bottom: 4px;
      font-size: {TYPOGRAPHY.size_sm};
      display: flex;
      align-items: center;
      gap: 6px;
  }}
  .comment-text {{
      color: {COLORS.text_secondary};
      font-size: {TYPOGRAPHY.size_sm};
      margin-bottom: 8px;
      font-family: {TYPOGRAPHY.font_sans};
      line-height: 1.45;
  }}

  /* ─────────────────────────────────────────────────────────────────────────────
     Badges & Labels
     ───────────────────────────────────────────────────────────────────────────── */
  .badge-cwe {{
      background: rgba(139, 92, 246, 0.14);
      border: 1px solid rgba(139, 92, 246, 0.4);
      color: {COLORS.accent_purple_light};
      padding: 2px 8px;
      border-radius: {RADII.xs};
      font-size: {TYPOGRAPHY.size_xs};
      font-weight: 600;
      font-family: {TYPOGRAPHY.font_mono};
  }}
  .badge-crit {{
      background: {COLORS.critical_bg};
      border: 1px solid {COLORS.critical_border};
      color: {COLORS.critical_text};
      padding: 2px 8px;
      border-radius: {RADII.xs};
      font-size: {TYPOGRAPHY.size_xs};
      font-weight: 700;
      letter-spacing: 0.3px;
  }}
  .badge-warn {{
      background: {COLORS.warning_bg};
      border: 1px solid {COLORS.warning_border};
      color: {COLORS.warning_text};
      padding: 2px 8px;
      border-radius: {RADII.xs};
      font-size: {TYPOGRAPHY.size_xs};
      font-weight: 700;
      letter-spacing: 0.3px;
  }}
  .badge-info {{
      background: {COLORS.info_bg};
      border: 1px solid {COLORS.info_border};
      color: {COLORS.info_text};
      padding: 2px 8px;
      border-radius: {RADII.xs};
      font-size: {TYPOGRAPHY.size_xs};
      font-weight: 600;
  }}

  /* ─────────────────────────────────────────────────────────────────────────────
     Onboarding & Empty States
     ───────────────────────────────────────────────────────────────────────────── */
  .onboarding-banner {{
      background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%);
      border: 1px solid {COLORS.border_accent};
      border-radius: {RADII.md};
      padding: 16px 20px;
      margin-bottom: 20px;
  }}
  .empty-state {{
      background: {COLORS.bg_surface};
      border: 1px dashed {COLORS.border_default};
      border-radius: {RADII.md};
      padding: 40px 24px;
      text-align: center;
      margin: 20px 0;
  }}

  /* ─────────────────────────────────────────────────────────────────────────────
     Tabs & DataFrames Polish
     ───────────────────────────────────────────────────────────────────────────── */
  .stTabs [data-baseweb="tab-list"] {{
      gap: 8px;
      border-bottom: 1px solid {COLORS.border_subtle};
      padding-bottom: 4px;
  }}
  .stTabs [data-baseweb="tab"] {{
      background: transparent;
      border-radius: {RADII.sm};
      color: {COLORS.text_muted};
      font-weight: 600;
      padding: 6px 14px;
  }}
  .stTabs [aria-selected="true"] {{
      background: {COLORS.bg_surface_elevated} !important;
      color: {COLORS.text_primary} !important;
      border: 1px solid {COLORS.border_default} !important;
  }}
</style>
"""
