# 💎 Premium Enterprise UI Redesign Prompt — PR Sage Dashboard

Copy-paste the entire block below into a senior frontend/product engineer (or any AI coding agent with file write access). The current `ui/dashboard.py` is a ~1590-line single-file Streamlit app with inline CSS strings, raw HTML interpolation, and regex-based logic — it works but LOOKS and FEELS "third class" / homemade. This prompt tells the engineer exactly how to rebuild it into a polished, professional, enterprise-grade product.

---

## ROLE
You are a **senior product-grade frontend engineer** specializing in polished enterprise SaaS UIs. Your job is to redesign the PR Sage Streamlit dashboard from a "hobby demo" look into a **premium, cohesive, professional product** — matching the visual quality of Linear, Vercel, GitHub Codespaces, or Raycast. You have full read/write access to the repo.

> Golden rule: Polish is a system, not decoration. Every visual decision must be deliberate, consistent, and purposeful. No more one-off random colors, no more inconsistent spacing, no more hacky inline CSS scattered in f-strings.

---

## CURRENT STATE (what's wrong — verify in `ui/dashboard.py`)
1. **One giant 1590-line file** mixing CSS, HTML, business logic, and Streamlit calls — impossible to maintain.
2. **~600 lines of CSS injected via one giant `ENTERPRISE_CSS` f-string** using `st.markdown(..., unsafe_allow_html=True)` — that's fragile, can't be cached, can't use real CSS features, and re-renders on every interaction.
3. **Everything is hardcoded random colors** (hex values scattered like `#8B5CF6`, `#10B981`, `#EF4444`) — no design tokens, no theme.
4. **Raw HTML f-string interpolation everywhere** — no structure, no typed components, high XSS/escaping risk.
5. Fonts, spacing, and radii are inconsistent. Cards, badges, and buttons don't share a design language.
6. No onboarding, no empty states, no loading/skeleton states, no error recovery UX.

## DELIVERABLES

### 1. SPLIT INTO A CLEAN, MODULAR STRUCTURE
Split the current monolith into a proper `ui/` package with clearly separated concerns. Suggested layout (adjust as you see fit, but it MUST be modular, not one file):

```
ui/
  dashboard.py            # main entrypoint: assembles pages, routing, session init
  theme.py                # single source of truth: design tokens (colors, spacing, radii, typography, shadows)
  styles.py               # ONE app-wide CSS string built from theme tokens, applied once
  components/
    __init__.py
    hud.py                # metric cards / score HUD
    pipeline.py           # live stage pipeline bar
    diff_card.py          # GitHub-style inline comment thread card
    badges.py             # severity / CWE / OWASP badges
    codeblock.py          # syntax-highlighted code + fix diff view
    export_panel.py       # patch / md / json export + auto-fix
    sidebar.py            # AI model hub + guardrail config
    onboarding.py         # first-run walkthrough / empty state
  views/
    __init__.py
    scenario_view.py
    editor_view.py
    github_view.py
    results_view.py
  state.py                # session_state management (typed helpers, no magic string keys)
  analytics.py            # static analysis / AST / LLM connectors (MOVED OUT of component code)
```

**Hard requirement:** Move ALL business logic (AST analyzer, LLM connectors, diff parsing) out of the view/component files into `ui/analytics.py` (and eventually reuse `src/`). Components must be pure rendering given props.

### 2. DESIGN SYSTEM (theme.py + styles.py)
Create ONE cohesive design system and apply it everywhere:
- **Design tokens**: `COLORS` (primary, success, warning, danger, info, surfaces, borders, text-muted), `SPACING` (4/8/12/16/24/32 scale), `RADII` (4/8/12), `SHADOWS`, `FONT` stack.
- **Professional dark + light mode** (at minimum dark; ideally add a light toggle). Pick a restrained, modern palette — think Linear/Notion, NOT neon-on-black "cyberpunk".
- **Typography**: one refined font (e.g. Inter for UI, JetBrains Mono for code), consistent sizes/weights, letter-spacing.
- **Real CSS file** (or a single well-crafted `<style>` built from tokens) applied ONCE via `st.markdown`, not restyled inline on every render.
- **Consistent component primitives**: one Button style, one Card, one Badge (with variant prop), one Input, one Tooltip. No hand-rolled HTML per feature.

### 3. REBUILD CORE COMPONENTS TO PRODUCTION QUALITY
- **Top nav**: a real header with product name/logo, environment indicator, global search-ish feel, current-engine badge. Clean, minimal, aligned.
- **Score HUD**: refined metric cards with subtle gradients, icon + label + value, tooltips explaining each metric. No jarring colors; use a proper severity scale.
- **Pipeline bar**: clear 4-step horizontal stepper with connected line, active/done/error states, animated transition on run.
- **Inline diff comment cards**: match GitHub's aesthetic — proper margin/padding, monospace line numbers column, real syntax highlighting for the added/removed lines, comment thread visually connected to the line.
- **Code + fix preview**: 2-column "before → after" diff view with syntax highlighting, not a plain `st.code`.
- **Badges**: severity (critical/warning/info), CWE, OWASP — consistent pill style, no glowing neon.
- **Empty/loading/error states**: skeleton loading while review runs, happy-path empty state ("Codebase approved"), and friendly error state with retry — not raw exception text.

### 4. INTERACTION & UX POLISH
- Give the "Run Review" a proper loading state (spinner/skeleton + disabled button) instead of auto-running on rerun.
- Debounce / session-state handling so the review does NOT re-trigger on every Streamlit rerun (side-effect separation from render).
- Add keyboard-accessible, clear focus states; consistent hover states; micro-interactions on cards/buttons.
- Add a lightweight onboarding hint / feature tour on first load (collapsible, dismissible).
- Responsive behavior so it doesn't break on smaller windows.

### 5. RESULT / REPORT VIEW
Make the findings review feel like a real report, not a dev console:
- Group findings by severity and/or file with counts.
- One-click "copy" + "download" for each finding and for the full report.
- A clean final summary panel (approve-as-is / needs-work verdict, key risks, next steps).
- Keep the exports (patch/md/json) but present them in an elegant export dropdown.

## QUALITY BAR
- No magic hex colors in component files — everything from `theme.py`.
- No raw HTML string interpolation without explicit escaping helper (add `escape_html()`).
- Every component self-contained and reusable; no copy-pasted markdown blocks.
- Consistent spacing and alignment on every screen.
- Runs without errors: `streamlit run ui/dashboard.py` should boot cleanly with no new dependencies (only use libs already in `requirements.txt`: streamlit, pandas, matplotlib, httpx — if you absolutely must add one, flag it and justify it).

## VERIFY YOUR WORK
1. Confirm `streamlit run ui/dashboard.py` (or the root entrypoints `app.py`/`streamlit_app.py`) starts without import errors.
2. Keep the app feature-complete: presets, custom editor, GitHub fetch, multi-model hub, inline diff findings, auto-fix + exports, stage trace, benchmark tab — all must still work after refactor.

## OUTPUT FORMAT
Report back:
1. What the new `ui/` structure looks like (tree).
2. The design tokens/theme you chose (colors, fonts, spacing).
3. `file:line` notes on the most impactful changes.
4. Anything you cut or moved, and why.
5. Screenshot/run instructions to verify the premium look.
