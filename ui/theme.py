"""
ui/theme.py — Enterprise Design System Tokens for PR Sage.
Single source of truth for all colors, typography, spacing, radii, and component metrics.
Inspired by Linear, Raycast, and GitHub Dark Premier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class ThemeColors:
    # Canvas & Surfaces
    bg_app: str = "#0B0D13"
    bg_surface: str = "#131620"
    bg_surface_elevated: str = "#1A1E2C"
    bg_surface_highlight: str = "#23283B"
    bg_surface_glass: str = "rgba(19, 22, 32, 0.85)"

    # Borders
    border_default: str = "#282E42"
    border_subtle: str = "#1E2333"
    border_accent: str = "rgba(99, 102, 241, 0.4)"
    border_focus: str = "#6366F1"

    # Brand & Primary Accents
    primary: str = "#6366F1"
    primary_hover: str = "#4F46E5"
    primary_light: str = "#818CF8"
    accent_purple: str = "#8B5CF6"
    accent_purple_light: str = "#A78BFA"
    accent_cyan: str = "#06B6D4"

    # Semantic Status Colors (AppSec & Reliability)
    critical: str = "#EF4444"
    critical_bg: str = "rgba(239, 68, 68, 0.12)"
    critical_border: str = "rgba(239, 68, 68, 0.35)"
    critical_text: str = "#FCA5A5"

    warning: str = "#F59E0B"
    warning_bg: str = "rgba(245, 158, 11, 0.12)"
    warning_border: str = "rgba(245, 158, 11, 0.35)"
    warning_text: str = "#FCD34D"

    success: str = "#10B981"
    success_bg: str = "rgba(16, 185, 129, 0.12)"
    success_border: str = "rgba(16, 185, 129, 0.35)"
    success_text: str = "#6EE7B7"

    info: str = "#38BDF8"
    info_bg: str = "rgba(56, 189, 248, 0.12)"
    info_border: str = "rgba(56, 189, 248, 0.35)"
    info_text: str = "#7DD3FC"

    # Typography
    text_primary: str = "#F8FAFC"
    text_secondary: str = "#CBD5E1"
    text_muted: str = "#64748B"
    text_inverse: str = "#0F172A"


@dataclass(frozen=True)
class ThemeTypography:
    font_sans: str = '-apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif'
    font_mono: str = '"JetBrains Mono", "Fira Code", Consolas, "Courier New", monospace'

    size_xs: str = "0.75rem"      # 12px
    size_sm: str = "0.84rem"      # 13.5px
    size_base: str = "0.92rem"    # 14.7px
    size_md: str = "1.05rem"      # 16.8px
    size_lg: str = "1.25rem"      # 20px
    size_xl: str = "1.55rem"      # 24.8px
    size_2xl: str = "1.95rem"     # 31.2px
    size_3xl: str = "2.4rem"      # 38.4px


@dataclass(frozen=True)
class ThemeSpacing:
    xs: str = "4px"
    sm: str = "8px"
    md: str = "12px"
    lg: str = "16px"
    xl: str = "24px"
    xxl: str = "32px"


@dataclass(frozen=True)
class ThemeRadii:
    xs: str = "4px"
    sm: str = "6px"
    md: str = "8px"
    lg: str = "12px"
    xl: str = "16px"
    pill: str = "9999px"


@dataclass(frozen=True)
class ThemeShadows:
    sm: str = "0 1px 2px 0 rgba(0, 0, 0, 0.35)"
    md: str = "0 4px 12px -1px rgba(0, 0, 0, 0.45)"
    lg: str = "0 10px 25px -3px rgba(0, 0, 0, 0.6)"
    glow_primary: str = "0 0 20px rgba(99, 102, 241, 0.25)"
    glow_critical: str = "0 0 16px rgba(239, 68, 68, 0.3)"
    glow_success: str = "0 0 16px rgba(16, 185, 129, 0.3)"


# Singleton Theme Instances
COLORS = ThemeColors()
TYPOGRAPHY = ThemeTypography()
SPACING = ThemeSpacing()
RADII = ThemeRadii()
SHADOWS = ThemeShadows()
