# Experiment Dashboard ― "Analyst's Funnel" Redesign

_Last updated: 2025-06-26_

This document captures the agreed-upon roadmap for evolving the Streamlit dashboard into a three-tier workflow that guides a user from batch-level results to individual trade analysis.

---
## 0  Rationale
The current dashboard shows high-level KPIs and a basic per-run preview, but it lacks context (batch summary), easy comparison (sortable leaderboard) and deep drill-down (trade-level narrative).  The redesign solves this by presenting information in an **analyst's funnel**:  
  **Batch → Leaderboard → Trade Inspector**.

---
## 1  Batch Performance Header
| Metric | Description |
|--------|-------------|
| **Total Net PNL** | Sum of `net_pnl_quote` across all runs |
| **Total Volume Traded** | Sum of `total_volume` |
| **Overall Win Rate** | % of trades with positive PNL across batch |
| **Aggregate Profit Factor** | Total gross profit / total gross loss |

Rendered as four KPI cards at top of Page 1.

---
## 2  Interactive Leaderboard (Page 1)
* Uses **Ag-Grid** (sortable, filterable).
* Columns: `label`, `algo`, `net_pnl_quote`, `total_volume`, `total_trades`, `win_rate`, `profit_factor`, `sharpe_ratio`.
* Row click → stores selected label in `st.session_state["run_profile"]` and navigates to Page 3.

---
## 3  Trade Inspector (Page 3)
1. **KPI Blocks** – reuse `hb_components.backtesting_metrics`.
2. **3-row Plotly figure** (price / signals ribbon / cumulative PNL).
   * Candles from `processed_data`.
   * Signals markers sized by `filled_amount_quote`.
3. **Trade Log Table** (Ag-Grid).
   Columns : `timestamp`, `side`, `size`, `price`, `pnl` – colour code PNL.

---
## 4  Implementation Milestones
| ID | Deliverable |
|----|-------------|
| M5-a | KPI header + Leaderboard replaces old bar/scatter on Page 1 |
| M5-b | Variable-size markers in `hb_components.signals` |
| M5-c | New Page 3 with full Trade Inspector & routing |
| M5-d | Add `st_aggrid` + docs, polish visuals |

---
## 5  HTML vs Streamlit
• **Keep Streamlit** for now ‑ existing backend & hot-reload works; moving to raw HTML/Tailwind would require a Flask/FastAPI template layer or iframe embed.  
• We can still adopt the **visual style** from the Tailwind mock by:
  1. Using Streamlit 1.30's `theme` overrides (set primary/background colours).
  2. Styling KPI cards / tables with custom CSS via `st.markdown("<style>…</style>", unsafe_allow_html=True)`.
  3. Ag-Grid dark theme matches Tailwind dark palette.
• Decision: **implement design in Streamlit** first; revisit full HTML migration only if Streamlit becomes limiting.

---
## 6  Open Todos / Nice-to-haves
* Performance-over-time subplot (`performance_time_evolution.py`).
* DCA analysis Tab (only for DCA controllers).
* Global theme consolidation.
* Unit tests for packet → DataFrame loaders.

---
## 7  Visual Style Reference (Tailwind Mock-up)
The final dashboard should visually match the dark Tailwind design shown in `docs/assets/mock_dashboard_tailwind.html` (see snippet below for quick reference).  Key style cues to replicate in Streamlit:

* **Colour palette** – Gray-900 background, Gray-800 card bodies, Gray-700 borders, with Blue-400 highlight accents.  These hexes will be mirrored in `.streamlit/config.toml`.
* **Typography** – `Inter` font family loaded from Google Fonts.
* **KPI cards** – rounded (12 px) dark panels with subtle border; primary values coloured (green-400 for positive PNL).
* **Leaderboard table** – dark header row (Gray-700), hover row shading, ability to highlight the selected run (`highlighted-row`).
* **Charts container** – same card style as KPI but larger padding; Plotly traces must follow palette.
* **Badges** – BUY/SELL pills (green/red 50 % opacity background).

An HTML mock-up is stored at `docs/assets/mock_dashboard_tailwind.html` for pixel-perfect comparison.  During implementation the style rules will be injected via `dashboard/theme_overrides.py` so **no additional frontend stack (React, Tailwind CLI, etc.) is required**.

_Added 2025-06-26 per user discussion._

---
_This file is autogenerated by ChatGPT to ensure the roadmap is tracked in-repo._ 