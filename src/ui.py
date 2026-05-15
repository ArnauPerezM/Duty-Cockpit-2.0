from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pycountry
import streamlit as st


# -----------------------------------------------------------------------------
# Accenture palette (purple)
# -----------------------------------------------------------------------------
ACCENTURE_PURPLE_CORE = "#A100FF"
ACCENTURE_PURPLE_DARK = "#7500C0"
ACCENTURE_PURPLE_DARKEST = "#460073"
ACCENTURE_PURPLE_LIGHT = "#C2A3FF"
ACCENTURE_PURPLE_LIGHTEST = "#E6DCFF"


# -----------------------------------------------------------------------------
# Styling (Hero header + KPI cards)
# -----------------------------------------------------------------------------
_BASE_CSS = f"""
<style>

/* --- Hero header --- */
.hero-wrap {{
  border-radius: 16px;
  padding: 18px 18px 14px 18px;
  background: linear-gradient(135deg, rgba(70,0,115,0.55) 0%, rgba(161,0,255,0.20) 55%, rgba(255,255,255,0.02) 100%);
  border: 1px solid rgba(194,163,255,0.18);
  box-shadow: 0 10px 28px rgba(0,0,0,0.35);
  margin-bottom: 14px;
}}

.hero-top {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}}

.hero-title {{
  font-size: 40px;
  font-weight: 900;
  letter-spacing: 0.2px;
  line-height: 1.05;
  
}}

.hero-sub {{
  margin-top: 6px;
  font-size: 12px;
  color: rgba(255,255,255,0.70);
}}

/* Quita el padding superior del contenido principal */
div.block-container{{
  padding-top: 0.8rem !important;  /* pon 0rem si lo quieres pegado del todo */
}}
header[data-testid="stHeader"]{{
  height: 0rem !important;
}}

.status-chip {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.16);
  background: rgba(0,0,0,0.20);
  font-size: 12px;
  white-space: nowrap;
}}

.status-dot {{
  width: 8px;
  height: 8px;
  border-radius: 999px;
  box-shadow: 0 0 0 3px rgba(161,0,255,0.12);
}}

.status-bar {{
  margin-top: 12px;
  height: 8px;
  border-radius: 999px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.08);
}}

.status-bar-fill {{
  height: 100%;
  width: 100%;
  background: linear-gradient(90deg, {ACCENTURE_PURPLE_DARKEST} 0%, {ACCENTURE_PURPLE_CORE} 55%, {ACCENTURE_PURPLE_LIGHT} 100%);
  opacity: 0.95;
}}

/* --- KPI cards --- */
.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}}
@media (max-width: 1100px) {{
  .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
@media (max-width: 650px) {{
  .kpi-grid {{ grid-template-columns: repeat(1, minmax(0, 1fr)); }}
}}

.kpi-card {{
  border-radius: 16px;
  padding: 14px 16px 12px 16px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.10);
  box-shadow: 0 10px 26px rgba(0,0,0,0.30);
  position: relative;
  overflow: hidden;
  text-align: center;
}}

.kpi-card::before {{
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  height: 3px;
  width: 100%;
  background: linear-gradient(90deg, {ACCENTURE_PURPLE_DARKEST}, {ACCENTURE_PURPLE_CORE}, {ACCENTURE_PURPLE_LIGHT});
  opacity: 0.95;
}}

.kpi-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}}

.kpi-label {{
  font-size: 15px;
  font-weight: 600;
  color: rgba(255,255,255,0.80);
  margin: 0;
  text-align: center;
}}

.kpi-value {{
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 0.2px;
  line-height: 1.1;
  text-align: center;
}}

.kpi-sub {{
  margin-top: 6px;
  font-size: 12px;
  color: rgba(255,255,255,0.60);
  text-align: center;
}}

.kpi-delta {{
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border-radius: 999px;
  border: 1px solid rgba(194,163,255,0.22);
  background: rgba(161,0,255,0.10);
  color: rgba(230,220,255,0.95);
  font-size: 12px;
}}

.kpi-delta.bad {{
  border: 1px solid rgba(255,120,120,0.28);
  background: rgba(255,60,60,0.12);
}}

.kpi-delta.good {{
  border: 1px solid rgba(120,255,200,0.22);
  background: rgba(40,200,120,0.10);
}}

/* ── KPI entry animation ──────────────────────────────────────── */
@keyframes kpiIn {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to   {{ opacity: 1; transform: translateY(0);  }}
}}
.kpi-value {{
  animation: kpiIn 0.55s ease both;
}}
.kpi-card, .kpi-card-compact {{
  animation: kpiIn 0.45s ease both;
}}

/* ── Table styling ────────────────────────────────────────────── */
/* Even rows: visible gray stripe (Styler handles it via pandas) */
/* Header row accent */
[data-testid="stDataFrame"] thead tr th {{
  background-color: rgba(161,0,255,0.18) !important;
  color: rgba(255,255,255,0.95) !important;
  font-weight: 700 !important;
}}
/* Data editor container */
[data-testid="stDataEditorContainer"],
[data-testid="stDataFrame"] {{
  border-radius: 6px;
  background: rgba(255,255,255,0.03);
}}

</style>
"""


# -----------------------------------------------------------------------------
# Hero header renderer
# -----------------------------------------------------------------------------
def render_hero_header(
    title: str,
    subtitle: str,
    run_state: str,
    meta: Optional[Dict[str, str]] = None,
    account_label: str = "",
) -> None:
    """
    Visual hero header with a status chip + a gradient status bar.
    run_state: "ready" | "blocked" | "running" | "completed" | "failed" | "cancelled"
    account_label: if set, shown as a secondary chip below the status chip.
    """
    st.markdown(_BASE_CSS, unsafe_allow_html=True)

    state = (run_state or "ready").lower().strip()
    state_map = {
        "ready": ("Ready", ACCENTURE_PURPLE_LIGHT, "rgba(161,0,255,0.10)"),
        "blocked": ("Blocked", "rgba(255,165,0,0.85)", "rgba(255,165,0,0.10)"),
        "running": ("Running", ACCENTURE_PURPLE_CORE, "rgba(161,0,255,0.15)"),
        "completed": ("Completed", "rgba(120,255,200,0.90)", "rgba(40,200,120,0.12)"),
        "failed": ("Failed", "rgba(255,120,120,0.90)", "rgba(255,60,60,0.12)"),
        "cancelled": ("Cancelled", "rgba(255,120,120,0.90)", "rgba(255,60,60,0.12)"),
    }
    label, dot_color, chip_bg = state_map.get(state, state_map["ready"])

    meta_line = ""
    if meta:
        parts = [f"{k}: {v}" for k, v in meta.items() if v is not None and str(v).strip() != ""]
        if parts:
            meta_line = " | ".join(parts)

    account_chip = ""
    if account_label and account_label.strip():
        account_chip = (
            f'<div style="margin-top:6px; display:inline-flex; align-items:center; gap:6px; '
            f'padding:4px 10px; border-radius:999px; border:1px solid rgba(194,163,255,0.18); '
            f'background:rgba(161,0,255,0.08); font-size:11px; color:rgba(255,255,255,0.70);">'
            f'<span style="opacity:0.7;">&#128100;</span>'
            f'<span>{_esc(account_label.strip())}</span>'
            f'</div>'
        )

    html = (
        f'<div class="hero-wrap">'
        f'  <div class="hero-top">'
        f'    <div>'
        f'      <div class="hero-title">{_esc(title)}</div>'
        f'      <div class="hero-sub">{_esc(subtitle)}'
        f'        {(" • " + _esc(meta_line)) if meta_line else ""}'
        f'      </div>'
        f'    </div>'
        f'    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:4px;">'
        f'      <div class="status-chip" style="background:{chip_bg}">'
        f'        <span class="status-dot" style="background:{dot_color}"></span>'
        f'        <span><b>{_esc(label)}</b></span>'
        f'      </div>'
        f'      {account_chip}'
        f'    </div>'
        f'  </div>'
        f'  <div class="status-bar"><div class="status-bar-fill"></div></div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _esc(s: Any) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# -----------------------------------------------------------------------------
# Sidebar filter helpers
# -----------------------------------------------------------------------------
def _reset_sidebar_filters() -> None:
    for k in ["sf_date_from", "sf_date_to", "sf_coo", "sf_coi", "sf_hs", "sf_material"]:
        st.session_state.pop(k, None)


def _apply_sidebar_filters(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Apply global sidebar (sf_*) selectbox filters. Returns filtered copy."""
    if df is None or df.empty:
        return df
    df = df.copy()

    for col in ["coo", "coi", "hs code"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    sf_coo = st.session_state.get("sf_coo", "All")
    sf_coi = st.session_state.get("sf_coi", "All")
    sf_hs  = st.session_state.get("sf_hs",  "All")
    sf_mat = st.session_state.get("sf_material", "All")

    if sf_coo and sf_coo != "All" and "coo" in df.columns:
        df = df[df["coo"] == sf_coo]
    if sf_coi and sf_coi != "All" and "coi" in df.columns:
        df = df[df["coi"] == sf_coi]
    if sf_hs and sf_hs != "All":
        hs_col = next((c for c in ["hs code", "hs_code"] if c in df.columns), None)
        if hs_col:
            df = df[df[hs_col].astype(str).str.strip() == sf_hs]
    if sf_mat and sf_mat != "All":
        mat_col = next((c for c in ["material number", "material_number"] if c in df.columns), None)
        if mat_col:
            df = df[df[mat_col].astype(str).str.strip() == sf_mat]

    sf_from = st.session_state.get("sf_date_from")
    sf_to   = st.session_state.get("sf_date_to")
    if sf_from or sf_to:
        dcol = next((c for c in ["input_date", "ref_date", "date"] if c in df.columns), None)
        if dcol:
            dates = pd.to_datetime(df[dcol], errors="coerce")
            if sf_from:
                df = df[dates >= pd.Timestamp(sf_from)]
            if sf_to:
                df = df[dates <= pd.Timestamp(sf_to)]

    return df


# -----------------------------------------------------------------------------
# Sidebar controls (renders inline inside the Process tab, not in sidebar)
# -----------------------------------------------------------------------------
def render_sidebar_controls() -> Dict[str, Any]:
    """Renders file upload + run controls inline (horizontal); call inside the Process tab."""
    with st.container():
        c1, c2, c3, c4, c5 = st.columns([3, 1.4, 1.4, 1, 1])
        with c1:
            uploaded_file = st.file_uploader(
                "Upload input Excel", type=["xlsx", "xls"],
                accept_multiple_files=False, label_visibility="collapsed",
            )
        with c2:
            sheet_name = st.text_input(
                "Sheet", value="Transactions",
                help="Excel sheet name (default: Transactions)",
            )
        with c3:
            ref_date = st.date_input(
                "Reference date", value=date.today(),
                help="Reference date for the API query",
            )
        with c4:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            analyze_clicked = st.button("▶ Run", type="primary", width='stretch')
        with c5:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            cancel_clicked = st.button("✕ Cancel", width='stretch')
    return {
        "uploaded_file": uploaded_file,
        "sheet_name": sheet_name,
        "ref_date": ref_date.strftime("%Y-%m-%d"),
        "analyze_clicked": analyze_clicked,
        "cancel_clicked": cancel_clicked,
    }


# -----------------------------------------------------------------------------
# Sidebar filter panel (always visible on non-Process tabs)
# -----------------------------------------------------------------------------
def render_sidebar_filters(df_merged: Optional[pd.DataFrame] = None) -> None:
    """Renders logo + filter widgets in the sidebar. Writes to sf_* session state keys."""
    from datetime import date as _date_t

    st.image("src/logo.png", width='stretch')
    st.divider()
    st.markdown("**Filters**")

    if df_merged is None or df_merged.empty:
        st.caption("Run an analysis to enable filters.")
        st.divider()
        if st.button("Reset Filter", key="sf_reset", width='stretch'):
            _reset_sidebar_filters()
            st.rerun()
        return

    # ── Time ──────────────────────────────────────────────────────────────
    _date_col = None
    for _dc in ["input_date", "ref_date", "date"]:
        if _dc in df_merged.columns:
            _parsed = pd.to_datetime(df_merged[_dc], errors="coerce")
            if _parsed.notna().sum() > 0:
                _date_col = _dc
                break

    if _date_col:
        _all_d  = pd.to_datetime(df_merged[_date_col], errors="coerce").dropna()
        _min_d  = _all_d.min().date()
        _max_d  = _all_d.max().date()
        st.markdown("**Time**")
        if "sf_date_from" not in st.session_state:
            st.session_state.sf_date_from = _min_d
        if "sf_date_to" not in st.session_state:
            st.session_state.sf_date_to = _max_d
        st.date_input("From", min_value=_min_d, max_value=_max_d, key="sf_date_from")
        st.date_input("To",   min_value=_min_d, max_value=_max_d, key="sf_date_to")
        st.markdown("")

    # ── COO ───────────────────────────────────────────────────────────────
    if "coo" in df_merged.columns:
        _opts = ["All"] + sorted(df_merged["coo"].dropna().astype(str).str.strip().unique().tolist())
        st.markdown("**Origin Country (COO)**")
        st.selectbox("Origin Country (COO)", options=_opts, key="sf_coo", label_visibility="collapsed")

    # ── COI ───────────────────────────────────────────────────────────────
    if "coi" in df_merged.columns:
        _opts = ["All"] + sorted(df_merged["coi"].dropna().astype(str).str.strip().unique().tolist())
        st.markdown("**Import Country (COI)**")
        st.selectbox("Import Country (COI)", options=_opts, key="sf_coi", label_visibility="collapsed")

    # ── HS Code ───────────────────────────────────────────────────────────
    _hs_col = next((c for c in ["hs code", "hs_code"] if c in df_merged.columns), None)
    if _hs_col:
        _opts = ["All"] + sorted(df_merged[_hs_col].dropna().astype(str).str.strip().unique().tolist())
        st.markdown("**HS Code**")
        st.selectbox("HS Code", options=_opts, key="sf_hs", label_visibility="collapsed")

    # ── Material ──────────────────────────────────────────────────────────
    _mat_col = next((c for c in ["material number", "material_number"] if c in df_merged.columns), None)
    if _mat_col:
        _opts = ["All"] + sorted(df_merged[_mat_col].dropna().astype(str).str.strip().unique().tolist())
        st.markdown("**Material Number**")
        st.selectbox("Material Number", options=_opts, key="sf_material", label_visibility="collapsed")

    st.markdown("")
    st.divider()
    if st.button("Reset Filter", key="sf_reset", width='stretch'):
        _reset_sidebar_filters()
        st.rerun()


# -----------------------------------------------------------------------------
# Process tab: inline auth gate
# -----------------------------------------------------------------------------
def render_process_auth_gate(existing_label: str = "") -> None:
    """
    Inline credential form inside the Process tab.
    existing_label: pre-fill Account name if previously stored for these credentials.
    Self-contained: validates against E2Open, saves label to DB, updates session_state.
    """
    st.info("Connect to E2Open to enable API execution.", icon="🔒")

    with st.form("e2open_auth", clear_on_submit=False):
        st.markdown("**E2Open credentials**")
        environment = st.selectbox("Environment", ["UAT", "PRO"])
        username = st.text_input("User ID", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        password = st.text_input("Password", type="password", placeholder="••••••••••••••••••••")
        tenant = st.text_input("Tenant ID", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        account_name = st.text_input(
            "Account name",
            value=existing_label,
            placeholder="e.g. Accenture UAT",
            help="A short name shown in the header to identify this connection. Saved for future sessions.",
        )
        submitted = st.form_submit_button("Connect to E2Open", type="primary", width='stretch')

    if submitted:
        u = username.strip()
        p = password
        t = tenant.strip()
        env = environment
        name = account_name.strip()
        if not u or not p or not t:
            st.error("User ID, Password and Tenant ID are required.")
        else:
            try:
                from E2Open import E2OpenSession as _E2OpenSession
                _E2OpenSession(u, p, t, env)
                _ak = f"{env}:{u}:{t}"
                from src.db import save_account_label as _save_label, get_account_label as _get_label
                # Use stored label if user left the field blank (returning user)
                if not name:
                    name = _get_label(_ak) or ""
                if not name:
                    st.error("Account name is required for first-time connections.")
                else:
                    _save_label(_ak, name)
                    st.session_state.e2open_env = env
                    st.session_state.e2open_username = u
                    st.session_state.e2open_password = p
                    st.session_state.e2open_tenant = t
                    st.session_state.account_key = _ak
                    st.session_state.account_label = name
                    st.session_state.auth_ok = True
                    st.rerun()
            except Exception as _e:
                st.error(f"Authentication failed: {_e}")


def render_logout_control() -> bool:
    """
    Renders a Logout button in the sidebar. Returns True if clicked.
    Call this inside a `with st.sidebar:` block (or after sidebar context).
    """
    st.divider()
    return st.button("Logout", width='stretch')








# -----------------------------------------------------------------------------
# Arrow / PyArrow compatibility helpers (display-only)
# -----------------------------------------------------------------------------
def _make_arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    out = df.copy()

    for col in out.columns:
        if str(col).strip().lower() == "analyzed":
            out[col] = out[col].astype("string")

    for col in out.columns:
        if out[col].dtype == "object":
            sample = out[col].dropna().head(50)
            if not sample.empty and sample.apply(lambda x: isinstance(x, (dict, list, tuple, set))).any():
                out[col] = out[col].astype("string")

    return out


_STRIPE_BG = "background-color: rgba(255,255,255,0.09);"


def _stripe(df_or_sty):
    """Alternating row stripe for st.dataframe display."""
    sty = df_or_sty.style if isinstance(df_or_sty, pd.DataFrame) else df_or_sty
    return sty.apply(
        lambda row: [_STRIPE_BG if row.name % 2 == 0 else "" for _ in row],
        axis=1,
    )


def _auto_col_cfg(df: pd.DataFrame) -> dict:
    """Auto NumberColumn configs for all float columns: %.3f for rate columns, %.2f for others."""
    cfg = {}
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            fmt = "%.3f" if "rate" in str(col).lower() else "%.2f"
            cfg[col] = st.column_config.NumberColumn(format=fmt)
    return cfg


def _render_empty_state(message: str, icon: str = "📭", hint: str = "") -> None:
    hint_html = (
        f'<div style="font-size:12px;color:rgba(255,255,255,0.45);margin-top:8px;">{_esc(hint)}</div>'
        if hint else ""
    )
    st.markdown(
        f'<div style="text-align:center;padding:48px 24px;border-radius:12px;'
        f'background:rgba(255,255,255,0.03);border:1px dashed rgba(255,255,255,0.12);margin:16px 0;">'
        f'<div style="font-size:40px;margin-bottom:12px;">{icon}</div>'
        f'<div style="font-size:16px;font-weight:600;color:rgba(255,255,255,0.78);">{_esc(message)}</div>'
        f'{hint_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# KPI cards renderer (icons + delta + sublabels)
# -----------------------------------------------------------------------------
def _render_kpi_cards(kpis: List[Dict[str, Any]], compact: bool = False) -> None:
    """
    Each KPI dict supports:
      - label (str)
      - value (str)
      - sub (str) optional
      - icon (str) optional (emoji or short text)
      - delta (str) optional (badge text)
      - delta_kind: "good" | "bad" | "neutral" (optional)
    compact=True: 6-column single-row layout with reduced padding/font sizes.
    """
    # CSS already injected by render_hero_header(); safe to re-inject once too
    st.markdown(_BASE_CSS, unsafe_allow_html=True)

    if compact:
        n = len(kpis)
        st.markdown(
            f"""<style>
            .kpi-grid-compact {{
              display: grid;
              grid-template-columns: repeat({n}, minmax(0, 1fr));
              gap: 8px;
            }}
            .kpi-card-compact {{
              border-radius: 10px;
              padding: 8px 10px 6px 10px;
              background: rgba(255,255,255,0.04);
              border: 1px solid rgba(255,255,255,0.10);
              box-shadow: 0 4px 12px rgba(0,0,0,0.20);
              position: relative;
              overflow: hidden;
              text-align: center;
            }}
            .kpi-card-compact::before {{
              content: "";
              position: absolute;
              left: 0; top: 0;
              height: 2px; width: 100%;
              background: linear-gradient(90deg, {ACCENTURE_PURPLE_DARKEST}, {ACCENTURE_PURPLE_CORE}, {ACCENTURE_PURPLE_LIGHT});
            }}
            .kpi-card-compact .kpi-label {{ font-size: 15px; font-weight: 600; color: rgba(255,255,255,0.80); margin:0; text-align:center; }}
            .kpi-card-compact .kpi-value {{ font-size: 34px; font-weight: 800; line-height: 1.1; text-align:center; }}
            .kpi-card-compact .kpi-sub   {{ font-size: 10px; color: rgba(255,255,255,0.50); margin-top:2px; text-align:center; }}
            .kpi-card-compact .kpi-delta {{
              margin-top: 5px;
              display: inline-flex; align-items: center; gap: 4px;
              padding: 2px 7px; border-radius: 999px;
              border: 1px solid rgba(194,163,255,0.22);
              background: rgba(161,0,255,0.10);
              color: rgba(230,220,255,0.95); font-size: 10px;
            }}
            .kpi-card-compact .kpi-delta.bad {{
              border: 1px solid rgba(255,120,120,0.28);
              background: rgba(255,60,60,0.12);
            }}
            .kpi-card-compact .kpi-delta.good {{
              border: 1px solid rgba(120,255,200,0.22);
              background: rgba(40,200,120,0.10);
            }}
            </style>""",
            unsafe_allow_html=True,
        )
        parts = ['<div class="kpi-grid-compact">']
        card_class = "kpi-card-compact"
    else:
        parts = ['<div class="kpi-grid">']
        card_class = "kpi-card"
    for k in kpis:
        label = _esc(k.get("label") or "")
        value = _esc(k.get("value") or "")
        sub = _esc(k.get("sub") or "")
        delta = _esc(k.get("delta") or "")
        delta_kind = (k.get("delta_kind") or "neutral").strip().lower()

        delta_html = ""
        if delta:
            cls = "kpi-delta"
            if delta_kind in ("good", "bad"):
                cls = f"{cls} {delta_kind}"
            delta_html = f'<div class="{cls}">{delta}</div>'

        parts.append(
            f'<div class="{card_class}">'
            f'  <div class="kpi-label">{label}</div>'
            f'  <div class="kpi-value">{value}</div>'
            f'  <div class="kpi-sub">{sub}</div>'
            f'  {delta_html}'
            f'</div>'
        )
    parts.append("</div>")

    st.markdown("".join(parts), unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Formatting helpers (k / M / B)  ✅ (display-only)
# -----------------------------------------------------------------------------
def _fmt_human(x: Any, decimals: int = 1) -> str:
    """
    Format big numbers using k/M/B suffix.
    Keeps small numbers readable (no suffix).
    """
    try:
        if x is None:
            return "N/A"
        v = float(x)
    except Exception:
        return "N/A"

    sign = "-" if v < 0 else ""
    v = abs(v)

    if v >= 1_000_000_000:
        return f"{sign}{v/1_000_000_000:.{decimals}f}B"
    if v >= 1_000_000:
        return f"{sign}{v/1_000_000:.{decimals}f}M"
    if v >= 1_000:
        return f"{sign}{v/1_000:.{decimals}f}k"

    # Small numbers: keep standard formatting
    if float(v).is_integer():
        return f"{sign}{int(v):,}"
    return f"{sign}{v:,.2f}"


def _fmt_num(x: Any, decimals: int = 2) -> str:
    """
    Backward-compatible: now shows k/M/B for >= 1,000.
    """
    try:
        if x is None:
            return "N/A"
        v = float(x)
        if abs(v) >= 1_000:
            return _fmt_human(v, decimals=1)
        return f"{v:,.{decimals}f}"
    except Exception:
        return "N/A"


def _fmt_int(x: Any) -> str:
    try:
        if x is None:
            return "0"
        return f"{int(x):,}"
    except Exception:
        return "0"


def _fmt_pct(x: Any, decimals: int = 1) -> str:
    try:
        if x is None:
            return "N/A"
        return f"{float(x) * 100:.{decimals}f}%"
    except Exception:
        return "N/A"


# -----------------------------------------------------------------------------
# ISO helpers (ISO2 -> ISO3) for map only
# -----------------------------------------------------------------------------
def _iso2_to_iso3(iso2: str) -> Optional[str]:
    if not iso2 or not isinstance(iso2, str):
        return None

    code = iso2.strip().upper()
    if code == "":
        return None

    aliases = {"UK": "GB", "EL": "GR"}
    code = aliases.get(code, code)

    try:
        c = pycountry.countries.get(alpha_2=code)
        return c.alpha_3 if c else None
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Country-level metrics (COI) for map + top10
# IMPORTANT: Customs Value sum must use EUR-normalized values.
# This function always uses df_merged["customs value"] (the normalized column).
# -----------------------------------------------------------------------------
def _build_country_metrics(
    df_merged: Optional[pd.DataFrame],
    df_ok: Optional[pd.DataFrame],
    df_failed: Optional[pd.DataFrame],
    df_missing: Optional[pd.DataFrame],
) -> pd.DataFrame:
    ok_counts = pd.DataFrame(columns=["coi", "ok_count"])
    if df_ok is not None and not df_ok.empty and "coi" in df_ok.columns:
        ok_counts = df_ok.groupby("coi", dropna=False).size().reset_index(name="ok_count")

    failed_counts = pd.DataFrame(columns=["coi", "failed_count"])
    if df_failed is not None and not df_failed.empty and "coi" in df_failed.columns:
        failed_counts = df_failed.groupby("coi", dropna=False).size().reset_index(name="failed_count")

    missing_counts = pd.DataFrame(columns=["coi", "missing_count"])
    if df_missing is not None and not df_missing.empty and "coi" in df_missing.columns:
        missing_counts = df_missing.groupby("coi", dropna=False).size().reset_index(name="missing_count")

    customs_sum   = pd.DataFrame(columns=["coi", "customs_value_sum_eur"])
    duty_paid_sum = pd.DataFrame(columns=["coi", "duty_paid_sum"])
    savings_sum   = pd.DataFrame(columns=["coi", "savings_sum"])

    if df_merged is not None and not df_merged.empty and "coi" in df_merged.columns:
        if "customs value" in df_merged.columns:
            tmp = df_merged.copy()
            tmp["customs value"] = pd.to_numeric(tmp["customs value"], errors="coerce").fillna(0.0)
            customs_sum = tmp.groupby("coi", dropna=False)["customs value"].sum().reset_index(name="customs_value_sum_eur")

        if "duty paid" in df_merged.columns:
            tmp = df_merged.copy()
            tmp["duty paid"] = pd.to_numeric(tmp["duty paid"], errors="coerce").fillna(0.0)
            duty_paid_sum = tmp.groupby("coi", dropna=False)["duty paid"].sum().reset_index(name="duty_paid_sum")

        if "duty paid" in df_merged.columns and "Minimum Duties" in df_merged.columns:
            tmp = df_merged.copy()
            tmp["duty paid"]      = pd.to_numeric(tmp["duty paid"],      errors="coerce").fillna(0.0)
            tmp["Minimum Duties"] = pd.to_numeric(tmp["Minimum Duties"], errors="coerce").fillna(0.0)
            tmp["savings"] = tmp["duty paid"] - tmp["Minimum Duties"]
            savings_sum = tmp.groupby("coi", dropna=False)["savings"].sum().reset_index(name="savings_sum")

    df = ok_counts.merge(failed_counts, on="coi", how="outer")
    df = df.merge(missing_counts, on="coi", how="outer")
    df = df.merge(customs_sum,    on="coi", how="outer")
    df = df.merge(duty_paid_sum,  on="coi", how="outer")
    df = df.merge(savings_sum,    on="coi", how="outer")

    for col in ["ok_count", "failed_count", "missing_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    for col in ["customs_value_sum_eur", "duty_paid_sum", "savings_sum"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["total_count"] = df["ok_count"] + df["failed_count"] + df["missing_count"]
    df["failed_plus_missing"] = df["failed_count"] + df["missing_count"]
    df["failed_rate"] = df.apply(
        lambda r: (r["failed_plus_missing"] / r["total_count"]) if r["total_count"] > 0 else 0.0,
        axis=1,
    )

    df["coi_iso2"] = df["coi"].astype(str).str.upper().str.strip()
    df["iso3"] = df["coi_iso2"].apply(_iso2_to_iso3)

    return df


# -----------------------------------------------------------------------------
# Dark, large, detailed map + Top 10 table (Accenture palette)
# -----------------------------------------------------------------------------
def _render_country_map_and_top10(metrics_df: pd.DataFrame) -> None:
    st.markdown("### Country map (COI)")

    options = [
        "Customs value (EUR)",
        "Duties paid (EUR)",
        "Potential savings (EUR)",
        "% failed/missing rows by COI",
    ]
    choice = st.selectbox("Map view", options, index=0)

    if metrics_df is None or metrics_df.empty:
        st.info("Not enough data to render the map.")
        return

    df_map = metrics_df.dropna(subset=["iso3"]).copy()
    if df_map.empty:
        st.warning("No COI codes could be mapped to ISO-3 (check ISO-2 inputs).")
        return

    if choice == "Customs value (EUR)":
        value_col = "customs_value_sum_eur"
        title = "Customs Value (EUR) by COI"
        top_df = metrics_df.sort_values(value_col, ascending=False)[["coi_iso2", value_col]].head(10)
        top_df = top_df.rename(columns={"coi_iso2": "COI", value_col: "Customs value (EUR)"})
        top_money_cols = ["Customs value (EUR)"]
    elif choice == "Duties paid (EUR)":
        value_col = "duty_paid_sum"
        title = "Duties Paid (EUR) by COI"
        top_df = metrics_df.sort_values(value_col, ascending=False)[["coi_iso2", value_col]].head(10)
        top_df = top_df.rename(columns={"coi_iso2": "COI", value_col: "Duties paid (EUR)"})
        top_money_cols = ["Duties paid (EUR)"]
    elif choice == "Potential savings (EUR)":
        value_col = "savings_sum"
        title = "Potential savings (EUR) by COI"
        top_df = metrics_df.sort_values(value_col, ascending=False)[["coi_iso2", value_col]].head(10)
        top_df = top_df.rename(columns={"coi_iso2": "COI", value_col: "Potential savings (EUR)"})
        top_money_cols = ["Potential savings (EUR)"]
    else:
        value_col = "failed_rate"
        title = "% failed/missing rows by COI"
        top_df = metrics_df.sort_values(value_col, ascending=False)[
            ["coi_iso2", "failed_plus_missing", "total_count", value_col]
        ].head(10)
        top_df = top_df.rename(
            columns={
                "coi_iso2": "COI",
                "failed_plus_missing": "Failed+Missing",
                "total_count": "Total",
                value_col: "Failed rate (%)",
            }
        )
        top_df["Failed rate (%)"] = (top_df["Failed rate (%)"] * 100).round(2)
        top_money_cols = []

    accenture_scale = [
        (0.00, ACCENTURE_PURPLE_LIGHTEST),  # lightest
        (0.25, ACCENTURE_PURPLE_LIGHT),     # light
        (0.50, ACCENTURE_PURPLE_CORE),      # core
        (0.75, ACCENTURE_PURPLE_DARK),      # dark
        (1.00, ACCENTURE_PURPLE_DARKEST),   # darkest
    ]

    fig = px.choropleth(
        df_map,
        locations="iso3",
        color=value_col,
        hover_name="coi_iso2",
        hover_data={
            "ok_count": True,
            "failed_count": True,
            "missing_count": True,
            # ✅ k/M in hover using d3-format SI (e.g., 1.2M)
            "customs_value_sum_eur": ":.2s",
            "savings_sum": ":.2s",
            "failed_rate": ":.2%",
            "iso3": False,
        },
        title=title,
        template="plotly_dark",
        color_continuous_scale=accenture_scale,
    )

    fig.update_traces(
        marker_line_width=0.8,
        marker_line_color="rgba(194,163,255,0.35)",
    )
    fig.update_layout(
        height=700,
        margin=dict(l=0, r=0, t=45, b=0),
        paper_bgcolor="rgba(255,255,255,0.06)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(
            outlinewidth=0,
            tickcolor="rgba(255,255,255,0.45)",
            tickfont=dict(size=12, color="rgba(255,255,255,0.65)"),
            title=dict(font=dict(color="rgba(255,255,255,0.75)")),
        ),
        title_font=dict(size=14, color="rgba(255,255,255,0.88)"),
    )

    fig.update_geos(
        showframe=False,
        showcountries=True,
        countrycolor="rgba(194,163,255,0.28)",
        showcoastlines=True,
        coastlinecolor="rgba(230,220,255,0.18)",
        showocean=True,
        oceancolor="rgb(10, 14, 24)",
        showland=True,
        landcolor="rgb(20, 24, 36)",
        bgcolor="rgba(0,0,0,0)",
        projection_type="natural earth",
    )

    st.plotly_chart(fig, width='stretch')

    st.markdown("### Top 10 countries (selected metric)")
    if top_money_cols:
        sty = top_df.style.format({c: (lambda v: _fmt_human(v, decimals=1)) for c in top_money_cols})
        st.dataframe(_stripe(sty), width="stretch", column_config=_auto_col_cfg(top_df))
    else:
        st.dataframe(_stripe(_make_arrow_safe(top_df)), width="stretch", column_config=_auto_col_cfg(top_df))


# -----------------------------------------------------------------------------
# Process tab rendering (split into pre-run and post-run)
# -----------------------------------------------------------------------------
def render_process_pre(
    uploaded_file,
    sheet_name: str,
    load_error: Optional[str],
    df_clean: Optional[pd.DataFrame],
    df_missing: Optional[pd.DataFrame],
    warnings_info: Optional[Dict[str, Any]],
) -> None:
    st.subheader("Input validation")

    if uploaded_file is None:
        st.info("Upload an Excel file to get started.")
        return

    st.write(f"**Selected sheet:** `{sheet_name}`")

    if load_error:
        st.error(load_error)
        return

    if warnings_info is not None and warnings_info.get("warnings"):
        st.warning("\n\n".join(warnings_info["warnings"]))

    st.markdown("### Row summary")

    candidates = int(len(df_clean)) if df_clean is not None else 0
    missing = int(len(df_missing)) if df_missing is not None else 0
    hs_ok = warnings_info.get("hs_ratio_ok", True) if warnings_info else True
    iso_ok = warnings_info.get("iso_ratio_ok", True) if warnings_info else True
    data_quality = "⚠️ Check warnings" if (not hs_ok or not iso_ok) else "✔ OK"
    quality_kind = "bad" if (not hs_ok or not iso_ok) else "good"

    kpis = [
        {
            "label": "Candidate rows",
            "value": _fmt_int(candidates),
            "sub": "Eligible rows for E2Open calls",
            "icon": "🧾",
            "delta": f"{_fmt_int(missing)} missing (skipped)",
            "delta_kind": "neutral",
        },
        {
            "label": "Data quality",
            "value": data_quality,
            "sub": "HS codes & COO/COI format",
            "icon": "🛡️",
            "delta": "Review warnings above" if (not hs_ok or not iso_ok) else "Ready to run",
            "delta_kind": quality_kind,
        },
    ]
    _render_kpi_cards(kpis)

    st.markdown("### Candidate rows")
    if df_clean is not None and not df_clean.empty:
        st.dataframe(_stripe(_make_arrow_safe(df_clean)), width="stretch", column_config=_auto_col_cfg(df_clean))
    else:
        st.info("No candidate rows found (or all rows are already marked as analyzed).")

    if df_missing is not None and not df_missing.empty:
        with st.expander("Missing rows (skipped)"):
            st.dataframe(_stripe(_make_arrow_safe(df_missing)), width="stretch", column_config=_auto_col_cfg(df_missing))


def render_process_post(
    df_clean: Optional[pd.DataFrame],
    df_missing: Optional[pd.DataFrame],
    df_failed: Optional[pd.DataFrame],
    df_ok: Optional[pd.DataFrame],
    df_merged: Optional[pd.DataFrame],
    run_summary: Optional[Dict[str, Any]],
) -> None:
    if run_summary is None:
        return

    st.divider()
    st.subheader("Post-run overview")

    processed = int(run_summary.get("processed", 0))
    ok_n = int(run_summary.get("ok", 0))
    failed_n = int(run_summary.get("failed", 0))
    missing_n = int(run_summary.get("missing", 0))
    total_candidates = int(run_summary.get("total_candidates", max(processed, 1)))

    ok_rate = (ok_n / total_candidates) if total_candidates > 0 else None
    fail_rate = (failed_n / total_candidates) if total_candidates > 0 else None

    kpis = [
        {
            "label": "Processed rows",
            "value": _fmt_int(processed),
            "sub": "OK + Failed (attempted API calls)",
            "icon": "⚙️",
            "delta": f"OK rate: {_fmt_pct(ok_rate)}" if ok_rate is not None else "",
            "delta_kind": "good" if (ok_rate is not None and ok_rate >= 0.85) else "neutral",
        },
        {
            "label": "OK",
            "value": _fmt_int(ok_n),
            "sub": "Successfully analyzed",
            "icon": "✅",
            "delta": f"Failure rate: {_fmt_pct(fail_rate)}" if fail_rate is not None else "",
            "delta_kind": "bad" if (fail_rate is not None and fail_rate >= 0.10) else "neutral",
        },
        {
            "label": "Failed",
            "value": _fmt_int(failed_n),
            "sub": "API failures after retries",
            "icon": "❌",
            "delta": "Check Logs tab for details",
            "delta_kind": "bad" if failed_n > 0 else "good",
        },
        {
            "label": "Missing",
            "value": _fmt_int(missing_n),
            "sub": "Skipped before API (missing required fields)",
            "icon": "⛔",
            "delta": "Fix input data to reduce skips",
            "delta_kind": "neutral",
        },
    ]
    _render_kpi_cards(kpis)

    if run_summary.get("cancelled"):
        st.warning("Run was cancelled. The map may be incomplete.")

    metrics_df = _build_country_metrics(
        df_merged=df_merged,
        df_ok=df_ok if df_ok is not None else df_clean,
        df_failed=df_failed,
        df_missing=df_missing,
    )
    _render_country_map_and_top10(metrics_df)


# -----------------------------------------------------------------------------
# Results tab (filters + KPI cards)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
div[data-testid="stMultiSelect"] label p {
  font-size: 24px !important;  /* <-- cambia aquí el tamaño*/
  font-weight: 600 !important; /* opcional */
}
</style>
""", unsafe_allow_html=True)

def render_tab_resultados(
    df_merged: Optional[pd.DataFrame],
    run_summary: Optional[Dict[str, Any]],
    df_current_run: Optional[pd.DataFrame] = None,
    df_failed: Optional[pd.DataFrame] = None,
    df_missing: Optional[pd.DataFrame] = None,
    ref_date: str = "",
    account_label: str = "",
    environment: str = "",
) -> None:
    _hdr_col, _btn_col = st.columns([5, 1])
    with _hdr_col:
        pass
    _btn_ph = _btn_col.empty()

    if df_merged is None or df_merged.empty:
        _render_empty_state("No results yet", "📊", "Run the analysis to populate this tab.")
        return

    df = df_merged.copy()
    for col in ["coo", "coi", "hs code"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ── Drill-down from Opportunities (multi-value override) ─────────────────
    coo_opts = sorted(df["coo"].dropna().unique().tolist()) if "coo" in df.columns else []
    coi_opts = sorted(df["coi"].dropna().unique().tolist()) if "coi" in df.columns else []
    hs_opts  = sorted(df["hs code"].dropna().unique().tolist()) if "hs code" in df.columns else []

    if "opp_drill_results" in st.session_state:
        _dr = st.session_state.pop("opp_drill_results")
        st.session_state["res_coo"] = [v for v in _dr.get("coo", []) if v in coo_opts]
        st.session_state["res_coi"] = [v for v in _dr.get("coi", []) if v in coi_opts]
        st.session_state["res_hs"]  = [v for v in _dr.get("hs",  []) if v in hs_opts]

    _drill_coo = st.session_state.get("res_coo", [])
    _drill_coi = st.session_state.get("res_coi", [])
    _drill_hs  = st.session_state.get("res_hs",  [])
    _drill_active = bool(_drill_coo or _drill_coi or _drill_hs)

    if _drill_active:
        _dc1, _dc2 = st.columns([9, 1])
        with _dc1:
            st.info(
                f"Drill-down from **Opportunities** active — "
                f"{len(_drill_coo)} COO · {len(_drill_coi)} COI · {len(_drill_hs)} HS Code",
                icon="🔍",
            )
        with _dc2:
            if st.button("Clear", key="res_clear_drill", width='stretch'):
                for _k in ["res_coo", "res_coi", "res_hs"]:
                    st.session_state.pop(_k, None)
                st.rerun()
        if _drill_coo:
            df = df[df["coo"].isin(_drill_coo)]
        if _drill_coi:
            df = df[df["coi"].isin(_drill_coi)]
        if _drill_hs:
            df = df[df["hs code"].isin(_drill_hs)]
    else:
        # Apply global sidebar filters
        df = _apply_sidebar_filters(df)

    # ── Numerics ──────────────────────────────────────────────────────────────
    def _n(col):
        return pd.to_numeric(df[col], errors="coerce").fillna(0.0) if col in df.columns else pd.Series([0.0]*len(df), index=df.index)

    customs_s = float(_n("customs value").sum())
    paid_s    = float(_n("duty paid").sum())
    def_s     = float(_n("Default Duties").sum())
    min_s     = float(_n("Minimum Duties").sum())
    n_coi     = int(df["coi"].nunique()) if "coi" in df.columns else 0
    n_coo     = int(df["coo"].nunique()) if "coo" in df.columns else 0

    # ── 6 KPI cards ──────────────────────────────────────────────────────────
    _kpi_cols = st.columns(6)
    _kpis = [
        ("# Transactions", _fmt_int(len(df)),           False),
        ("# COI",          _fmt_int(n_coi),             False),
        ("# COO",          _fmt_int(n_coo),             False),
        ("Customs Value",  _fmt_num(customs_s) + " €",  False),
        ("Duty Exposure",  _fmt_num(def_s)     + " €",  False),
        ("Duty Paid",      _fmt_num(paid_s)    + " €",  True),
    ]
    for _col, (_lbl, _val, _hi) in zip(_kpi_cols, _kpis):
        with _col:
            _style = (
                "background:rgba(0,178,178,0.18);border-color:rgba(0,178,178,0.40);"
                if _hi else ""
            )
            st.markdown(
                f"""<div class="kpi-card" style="{_style}">
                  <div class="kpi-label">{_lbl}</div>
                  <div class="kpi-value">{_val}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("")

    # ── Shared chart layout ────────────────────────────────────────────────
    _CL = dict(
        paper_bgcolor="rgba(255,255,255,0.06)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=8, t=32, b=0),
        font=dict(color="rgba(255,255,255,0.82)", size=13),
    )
    _AXIS = dict(
        gridcolor="rgba(255,255,255,0.07)", tickfont=dict(size=12),
        showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1,
    )
    _PURPLES = [
        ACCENTURE_PURPLE_CORE, ACCENTURE_PURPLE_LIGHT, ACCENTURE_PURPLE_DARK,
        ACCENTURE_PURPLE_LIGHTEST, ACCENTURE_PURPLE_DARKEST,
        "#C2A3FF", "#7500C0", "#E6DCFF",
    ]

    # ── Row 2: Pie · Gauge · Pie ───────────────────────────────────────────
    _ch1, _ch2, _ch3 = st.columns(3)

    with _ch1:
        st.markdown("**Customs Value by COO**")
        if "coo" in df.columns and customs_s > 0:
            _grp = (
                df.groupby("coo")["customs value"]
                .apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())
                .reset_index()
                .rename(columns={"customs value": "val"})
            )
            _grp = _grp[_grp["val"] > 0].nlargest(8, "val")
            _fig = px.pie(_grp, values="val", names="coo",
                          color_discrete_sequence=_PURPLES, template="plotly_dark")
            _fig.update_layout(height=240, **_CL, showlegend=True,
                               legend=dict(font=dict(size=12), bgcolor="rgba(0,0,0,0)"))
            _fig.update_traces(
                textinfo="percent", textfont_size=13,
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent:.1%}<extra></extra>",
            )
            st.plotly_chart(_fig, width='stretch')
        else:
            st.info("No customs value data.")

    with _ch2:
        st.markdown("**Duty Exposure**")
        _gauge_max = max(def_s, paid_s * 1.1, 1.0)
        _fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=paid_s,
            gauge={
                "axis": {
                    "range": [0, _gauge_max],
                    "tickformat": ".2s", "ticksuffix": " €",
                    "tickfont": {"size": 12, "color": "rgba(255,255,255,0.65)"},
                },
                "bar": {"color": "#40E0D0", "thickness": 0.55},
                "bgcolor": "rgba(255,255,255,0.07)",
                "borderwidth": 0,
                "steps": [{"range": [0, _gauge_max], "color": "rgba(255,255,255,0.07)"}],
                "threshold": {
                    "line": {"color": ACCENTURE_PURPLE_LIGHT, "width": 2},
                    "thickness": 0.75,
                    "value": def_s,
                },
            },
            number={"suffix": " €", "valueformat": ".3s",
                    "font": {"size": 26, "color": "white"}},
        ))
        _fig.update_layout(
            height=240, paper_bgcolor="rgba(255,255,255,0.06)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "white"}, margin=dict(l=20, r=20, t=20, b=10),
        )
        st.plotly_chart(_fig, width='stretch')
        st.caption(f"Paid: {_fmt_num(paid_s)} € / Exposure: {_fmt_num(def_s)} €")

    with _ch3:
        st.markdown("**Duties Paid by COI**")
        if "coi" in df.columns and paid_s > 0:
            _grp = (
                df.groupby("coi")["duty paid"]
                .apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())
                .reset_index()
                .rename(columns={"duty paid": "val"})
            )
            _grp = _grp[_grp["val"] > 0].nlargest(8, "val")
            _fig = px.pie(_grp, values="val", names="coi",
                          color_discrete_sequence=_PURPLES, template="plotly_dark")
            _fig.update_layout(height=240, **_CL, showlegend=True,
                               legend=dict(font=dict(size=12), bgcolor="rgba(0,0,0,0)"))
            _fig.update_traces(
                textinfo="percent", textfont_size=13,
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent:.1%}<extra></extra>",
            )
            st.plotly_chart(_fig, width='stretch')
        else:
            st.info("No duty paid data.")

    # ── Date column detection ─────────────────────────────────────────────
    _date_col = None
    for _dc in ["input_date", "ref_date", "date"]:
        if _dc in df.columns:
            _dp = pd.to_datetime(df[_dc], errors="coerce")
            if _dp.notna().sum() > 0:
                _date_col = _dc
                df = df.copy()
                df["__mdt"]   = _dp
                df["__msort"] = _dp.dt.to_period("M").dt.to_timestamp()
                df["__mlbl"]  = _dp.dt.strftime("%b %Y")
                break

    # ── Row 3: monthly charts (left, tall) + product/COI bars (right) ────
    _col_main, _col_side = st.columns([3, 2])
    _prod_col = next((c for c in ["product", "material number", "material"] if c in df.columns), None)

    with _col_main:
        # ── Customs Value by Month ─────────────────────────────────────────
        st.markdown("**Customs Value of Imported Products**")
        if _date_col and "coi" in df.columns:
            _grp = (
                df.groupby(["__msort", "__mlbl", "coi"])
                .agg({"customs value": lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()})
                .reset_index()
                .sort_values("__msort")
            )
            _grp.columns = ["_ms", "Month", "COI", "Customs Value"]
            if not _grp.empty:
                _mo = _grp.sort_values("_ms")["Month"].unique().tolist()
                _fig = px.bar(_grp, x="Month", y="Customs Value", color="COI",
                              template="plotly_dark", color_discrete_sequence=_PURPLES,
                              barmode="group", text_auto=".2s",
                              category_orders={"Month": _mo})
                _fig.update_layout(
                    height=280, yaxis_ticksuffix=" €", yaxis_tickformat=".2s",
                    **{**_CL, "margin": dict(l=0, r=8, t=32, b=50)},
                    showlegend=True,
                    legend=dict(font=dict(size=12), bgcolor="rgba(0,0,0,0)",
                                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    xaxis=dict(tickfont=dict(size=12), tickangle=-30,
                               gridcolor="rgba(255,255,255,0.07)",
                               showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.07)", tickfont=dict(size=12),
                               tickformat=".2s",
                               showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1),
                )
                _fig.update_traces(
                    textfont_size=11,
                    hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:,.0f} €<extra></extra>",
                )
                st.plotly_chart(_fig, width='stretch')
            else:
                st.info("No monthly customs value data.")
        else:
            st.info("No date / COI data for monthly breakdown.")

        # ── Duties Paid by Month ───────────────────────────────────────────
        st.markdown("**Duties Paid on Imported Products**")
        if _date_col and "coi" in df.columns:
            _grp = (
                df.groupby(["__msort", "__mlbl", "coi"])
                .agg({"duty paid": lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()})
                .reset_index()
                .sort_values("__msort")
            )
            _grp.columns = ["_ms", "Month", "COI", "Duty Paid"]
            if not _grp.empty:
                _mo = _grp.sort_values("_ms")["Month"].unique().tolist()
                _fig = px.bar(_grp, x="Month", y="Duty Paid", color="COI",
                              template="plotly_dark", color_discrete_sequence=_PURPLES,
                              barmode="group", text_auto=".2s",
                              category_orders={"Month": _mo})
                _fig.update_layout(
                    height=280, yaxis_ticksuffix=" €",
                    **{**_CL, "margin": dict(l=0, r=8, t=32, b=50)},
                    showlegend=True,
                    legend=dict(font=dict(size=12), bgcolor="rgba(0,0,0,0)",
                                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    xaxis=dict(tickfont=dict(size=12), tickangle=-30,
                               gridcolor="rgba(255,255,255,0.07)",
                               showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.07)", tickfont=dict(size=12),
                               tickformat=".2s",
                               showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1),
                )
                _fig.update_traces(
                    textfont_size=11,
                    hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:,.0f} €<extra></extra>",
                )
                st.plotly_chart(_fig, width='stretch')
            else:
                st.info("No monthly duty paid data.")
        else:
            st.info("No date / COI data for monthly breakdown.")

    with _col_side:
        # ── Duties Paid by Product ─────────────────────────────────────────
        st.markdown("**Duties Paid by Product**")
        if _prod_col:
            _grp = (
                df.groupby(_prod_col)["duty paid"]
                .apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())
                .reset_index()
                .rename(columns={"duty paid": "val"})
            )
            _grp = _grp[_grp["val"] > 0].sort_values("val", ascending=True).tail(15)
            if not _grp.empty:
                _fig = px.bar(_grp, x="val", y=_prod_col, orientation="h",
                              template="plotly_dark",
                              color_discrete_sequence=[ACCENTURE_PURPLE_CORE],
                              text_auto=".2s")
                _fig.update_layout(
                    height=280, xaxis_ticksuffix=" €",
                    **{**_CL, "margin": dict(l=0, r=8, t=32, b=0)},
                    xaxis=dict(tickfont=dict(size=12), gridcolor="rgba(255,255,255,0.07)",
                               tickformat=".2s",
                               showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1),
                    yaxis=dict(tickfont=dict(size=12),
                               showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1),
                )
                _fig.update_traces(
                    textfont_size=11,
                    hovertemplate="<b>%{y}</b><br>%{x:,.0f} €<extra></extra>",
                )
                st.plotly_chart(_fig, width='stretch')
            else:
                st.info("No product duty data.")
        else:
            st.info("No product column in data.")

        # ── Duties Paid by COI (bar) ───────────────────────────────────────
        st.markdown("**Duties Paid by COI**")
        if "coi" in df.columns and paid_s > 0:
            _grp = (
                df.groupby("coi")["duty paid"]
                .apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())
                .reset_index()
                .rename(columns={"duty paid": "val"})
            )
            _grp = _grp[_grp["val"] > 0].sort_values("val", ascending=True)
            if not _grp.empty:
                _fig = px.bar(_grp, x="val", y="coi", orientation="h",
                              template="plotly_dark",
                              color_discrete_sequence=[ACCENTURE_PURPLE_LIGHT],
                              text_auto=".2s")
                _fig.update_layout(
                    height=280, xaxis_ticksuffix=" €",
                    **{**_CL, "margin": dict(l=0, r=8, t=32, b=0)},
                    xaxis=dict(tickfont=dict(size=12), gridcolor="rgba(255,255,255,0.07)",
                               tickformat=".2s",
                               showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1),
                    yaxis=dict(tickfont=dict(size=12),
                               showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1),
                )
                _fig.update_traces(
                    textfont_size=11,
                    hovertemplate="<b>%{y}</b><br>%{x:,.0f} €<extra></extra>",
                )
                st.plotly_chart(_fig, width='stretch')
            else:
                st.info("No COI duty data.")

    # ── Download Report ────────────────────────────────────────────────────
    if not df.empty:
        from src.logic import build_report_html as _build_report
        import datetime as _dt
        _fname = f"duty_report_{ref_date or _dt.date.today().isoformat()}.html"
        try:
            _report_bytes = _build_report(
                df_merged=df, df_failed=df_failed, df_missing=df_missing,
                run_summary=run_summary, ref_date=ref_date or "",
                account_label=account_label, environment=environment,
            )
            _btn_ph.download_button(
                label="Download Report", data=_report_bytes,
                file_name=_fname, mime="text/html", width='stretch',
            )
        except Exception as _rep_err:
            _btn_ph.warning(f"Report error: {_rep_err}")

    # ── Results table ──────────────────────────────────────────────────────
    st.markdown("### Results table")
    _edit_mode = st.session_state.get("db_edit_mode", "view")
    _HIDE_RES = {"saved_at", "customs_value_original", "__mdt", "__msort", "__mlbl"}
    _df_res = df[[c for c in df.columns if c not in _HIDE_RES]]
    if _edit_mode == "view":
        st.dataframe(_stripe(_make_arrow_safe(_df_res)), width='stretch', column_config=_auto_col_cfg(_df_res))
    render_db_editor_section(df_merged=df_merged, df_filtered=df)


# -----------------------------------------------------------------------------
# DB editor section (inline + Excel corrections)
# -----------------------------------------------------------------------------

# Columns shown to the user but not editable
_EDITOR_READONLY_COLS = [
    "invoice number", "material number", "date", "ref_date", "status",
    "calcName", "incoCalcBasis", "Input Date",
    "Min Duty Program", "Min Duty Rate", "Min Duty Program Description",
    "Minimum Duties", "Currency Min Duties",
    "Default Duty Program", "Default Duty Rate", "Default Duty Program Description",
    "Default Duties", "Currency Default Duties",
]
# Columns hidden entirely from the editor grid
_EDITOR_HIDDEN_COLS = ["run_id", "ref_date", "saved_at"]


def render_db_editor_section(
    df_merged: pd.DataFrame,
    df_filtered: pd.DataFrame,
) -> None:
    """
    Renders the DB editor section below the results table.

    Offers two correction paths:
    1. Inline editing via st.data_editor with diff/confirm step.
    2. Excel roundtrip: export → edit offline → import with diff/confirm.

    Uses st.session_state keys:
      db_edit_mode       : "view" | "inline" | "inline_review" | "corrections_review"
      db_editor_base_df  : df used as starting point for inline editor
      db_inline_changes  : list[dict] — computed inline update diff
      db_inline_deletes  : list[int]  — ids to delete from inline editor
      db_corrections_diff: dict       — diff from Excel corrections parse
      db_corrections_errors: list[str]
    """
    from src.db import update_merged_rows, delete_merged_rows, EDITABLE_COL_DF_TO_DB
    from src.logic import export_merged_to_excel, parse_corrections_excel

    edit_mode = st.session_state.get("db_edit_mode", "view")

    st.markdown("---")
    st.markdown("#### Edit / Correct Records")

    # ── Action bar ────────────────────────────────────────────────────────────
    if edit_mode == "view":
        col_a, col_b, col_c = st.columns([2, 2, 3])

        with col_a:
            if st.button("Edit inline", key="db_btn_edit_inline", width='stretch'):
                # Prepare the editor df: add _delete col, keep id hidden
                base = df_filtered.copy()
                base.insert(0, "_delete", False)
                st.session_state.db_editor_base_df = base
                st.session_state.db_edit_mode = "inline"
                st.rerun()

        with col_b:
            # Excel export of the filtered view
            if "id" in df_filtered.columns and not df_filtered.empty:
                import datetime as _dt
                _xls_bytes = export_merged_to_excel(df_filtered)
                st.download_button(
                    label="Download Excel (corrections)",
                    data=_xls_bytes,
                    file_name=f"corrections_{_dt.date.today().isoformat()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch',
                    key="db_btn_download_xls",
                )

        with col_c:
            corr_file = st.file_uploader(
                "Import corrections (.xlsx)",
                type=["xlsx"],
                key="db_corrections_uploader",
                label_visibility="collapsed",
            )
            if corr_file is not None:
                diff, errors = parse_corrections_excel(corr_file, df_merged)
                st.session_state.db_corrections_diff = diff
                st.session_state.db_corrections_errors = errors
                if diff is not None:
                    st.session_state.db_edit_mode = "corrections_review"
                    st.rerun()
                else:
                    for err in errors:
                        st.error(err)

    # ── Inline editor ─────────────────────────────────────────────────────────
    elif edit_mode == "inline":
        st.info(
            "Edit cells directly. Check **_delete** to mark a row for deletion. "
            "Grey columns are read-only."
        )

        base_df = st.session_state.get("db_editor_base_df", df_filtered)

        # Build column config: hide internal cols, lock read-only cols, configure editable ones
        col_cfg: dict = {}
        for col in _EDITOR_HIDDEN_COLS + ["id"]:
            col_cfg[col] = None  # hidden
        col_cfg["_delete"] = st.column_config.CheckboxColumn(
            "Delete", default=False, width="small"
        )
        for col in _EDITOR_READONLY_COLS:
            if col in base_df.columns:
                col_cfg[col] = st.column_config.TextColumn(col, disabled=True)
        # Numeric editable columns
        for num_col, fmt in [
            ("customs value", "%.2f"), ("weight", "%.4f"), ("duty paid", "%.2f"),
        ]:
            if num_col in base_df.columns:
                col_cfg[num_col] = st.column_config.NumberColumn(num_col, format=fmt)

        edited_df = st.data_editor(
            _make_arrow_safe(base_df),
            column_config=col_cfg,
            hide_index=True,
            width='stretch',
            num_rows="fixed",
            key="db_inline_editor",
        )

        btn_col1, btn_col2 = st.columns([2, 1])
        with btn_col1:
            btn_review = st.button(
                "Review changes", type="primary", key="db_btn_review_inline"
            )
        with btn_col2:
            btn_cancel = st.button("Cancel", key="db_btn_cancel_inline")

        if btn_cancel:
            st.session_state.db_edit_mode = "view"
            st.session_state.db_editor_base_df = None
            st.rerun()

        if btn_review:
            # Compute diff between base and edited
            editable_df_cols = list(EDITABLE_COL_DF_TO_DB.keys())
            changes: list = []
            deletes: list = []

            # Align by position (data_editor returns same row order)
            base_arr = base_df.reset_index(drop=True)
            edit_arr = edited_df.reset_index(drop=True)

            for i in range(len(base_arr)):
                if i >= len(edit_arr):
                    break
                b_row = base_arr.iloc[i]
                e_row = edit_arr.iloc[i]
                row_id = b_row.get("id")

                # Delete flagged rows
                if e_row.get("_delete") is True or e_row.get("_delete") == 1:
                    if row_id is not None:
                        deletes.append(int(row_id))
                    continue

                # Detect editable column changes
                row_diff: dict = {"id": row_id}
                for df_col, db_col in EDITABLE_COL_DF_TO_DB.items():
                    if df_col not in b_row.index or df_col not in e_row.index:
                        continue
                    from src.logic import _corr_vals_equal, _coerce_correction
                    if not _corr_vals_equal(b_row[df_col], e_row[df_col]):
                        row_diff[db_col] = _coerce_correction(e_row[df_col], db_col)

                if len(row_diff) > 1:
                    changes.append(row_diff)

            st.session_state.db_editor_base_df = edited_df  # preserve for "back"
            st.session_state.db_inline_changes = changes
            st.session_state.db_inline_deletes = deletes
            st.session_state.db_edit_mode = "inline_review"
            st.rerun()

    # ── Inline review / confirm ───────────────────────────────────────────────
    elif edit_mode == "inline_review":
        changes = st.session_state.get("db_inline_changes", [])
        deletes = st.session_state.get("db_inline_deletes", [])

        if not changes and not deletes:
            st.info("No changes detected compared to the current DB state.")
        else:
            if changes:
                st.markdown(f"**{len(changes)} row(s) with changes:**")
                # Build preview df with old→new format
                from src.db import EDITABLE_COL_DF_TO_DB as _cmap
                _db_to_df = {v: k for k, v in _cmap.items()}
                preview_rows = []
                for ch in changes:
                    row = {"id": ch["id"]}
                    for db_col, new_val in ch.items():
                        if db_col == "id":
                            continue
                        df_col = _db_to_df.get(db_col, db_col)
                        row[df_col] = new_val
                    preview_rows.append(row)
                st.dataframe(_stripe(pd.DataFrame(preview_rows)), width='stretch', hide_index=True)

            if deletes:
                st.markdown(f"**{len(deletes)} row(s) to delete** (IDs: {deletes})")

        rc1, rc2, rc3 = st.columns([2, 2, 1])
        with rc1:
            btn_apply = st.button(
                "Apply changes", type="primary", key="db_btn_apply_inline",
                disabled=(not changes and not deletes),
            )
        with rc2:
            btn_back = st.button("Back to editor", key="db_btn_back_inline")
        with rc3:
            btn_cancel2 = st.button("Cancel", key="db_btn_cancel_review")

        if btn_cancel2:
            st.session_state.db_edit_mode = "view"
            st.session_state.db_editor_base_df = None
            st.rerun()

        if btn_back:
            st.session_state.db_edit_mode = "inline"
            st.rerun()

        if btn_apply:
            n_upd = update_merged_rows(changes) if changes else 0
            n_del = delete_merged_rows(deletes) if deletes else 0
            st.session_state.db_edit_mode = "view"
            st.session_state.db_editor_base_df = None
            st.session_state.db_inline_changes = None
            st.session_state.db_inline_deletes = None
            st.success(f"Changes applied: {n_upd} updated, {n_del} deleted.")
            st.rerun()

    # ── Excel corrections review / confirm ────────────────────────────────────
    elif edit_mode == "corrections_review":
        diff = st.session_state.get("db_corrections_diff")
        errors = st.session_state.get("db_corrections_errors", [])

        for err in errors:
            st.warning(err)

        if diff is None:
            st.error("No valid corrections to display.")
        else:
            updates = diff.get("updates", [])
            deletes = diff.get("deletes", [])
            upd_preview: pd.DataFrame = diff.get("update_preview", pd.DataFrame())
            del_preview: pd.DataFrame = diff.get("delete_preview", pd.DataFrame())

            if updates:
                st.markdown(f"**{len(updates)} row(s) with detected changes:**")
                st.dataframe(
                    _stripe(_make_arrow_safe(upd_preview)), width='stretch', hide_index=True
                )
            else:
                st.info("No changes detected in editable columns.")

            if deletes:
                st.markdown(f"**{len(deletes)} row(s) marked for deletion:**")
                if not del_preview.empty:
                    st.dataframe(
                        _stripe(_make_arrow_safe(del_preview)), width='stretch', hide_index=True
                    )

            if not updates and not deletes:
                st.info("The file contains no changes compared to the current DB.")

            ec1, ec2 = st.columns([2, 1])
            with ec1:
                btn_apply_xls = st.button(
                    "Apply corrections",
                    type="primary",
                    key="db_btn_apply_xls",
                    disabled=(not updates and not deletes),
                )
            with ec2:
                btn_cancel_xls = st.button("Cancel", key="db_btn_cancel_xls")

            if btn_cancel_xls:
                st.session_state.db_edit_mode = "view"
                st.session_state.db_corrections_diff = None
                st.rerun()

            if btn_apply_xls:
                n_upd = update_merged_rows(updates) if updates else 0
                n_del = delete_merged_rows(deletes) if deletes else 0
                st.session_state.db_edit_mode = "view"
                st.session_state.db_corrections_diff = None
                st.session_state.db_corrections_errors = None
                st.success(f"Corrections applied: {n_upd} updated, {n_del} deleted.")
                st.rerun()


# -----------------------------------------------------------------------------
# Opportunities tab
# -----------------------------------------------------------------------------
def render_tab_opportunities(
    df_merged: Optional[pd.DataFrame],
    df_initiatives: Optional[pd.DataFrame] = None,
) -> None:

    if df_merged is None or df_merged.empty:
        _render_empty_state("No results yet", "💡", "Run the analysis to populate this tab.")
        return

    # Apply global sidebar filters first, then allow inline refinement
    df_merged = _apply_sidebar_filters(df_merged)

    df = df_merged.copy()
    for col in ["coo", "coi", "hs code"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Option lists needed for drill-down validation
    coo_opts = sorted(df["coo"].dropna().unique().tolist()) if "coo" in df.columns else []
    coi_opts = sorted(df["coi"].dropna().unique().tolist()) if "coi" in df.columns else []
    hs_opts  = sorted(df["hs code"].dropna().unique().tolist()) if "hs code" in df.columns else []

    # Apply drill-down filter from Initiatives tab if pending
    if "ini_drill_opp" in st.session_state:
        _drill = st.session_state.pop("ini_drill_opp")
        st.session_state["opp_coo"] = [v for v in _drill.get("coo", []) if v in coo_opts]
        st.session_state["opp_coi"] = [v for v in _drill.get("coi", []) if v in coi_opts]
        st.session_state["opp_hs"]  = [v for v in _drill.get("hs", [])  if v in hs_opts]

    coo_sel = st.session_state.get("opp_coo", [])
    coi_sel = st.session_state.get("opp_coi", [])
    hs_sel  = st.session_state.get("opp_hs",  [])

    _drill_active_opp = bool(coo_sel or coi_sel or hs_sel)
    if _drill_active_opp:
        _fc1, _fc2 = st.columns([9, 1])
        with _fc1:
            st.info("Showing results filtered from **Initiatives** drill-down.", icon="🔍")
        with _fc2:
            if st.button("Clear", key="opp_clear_drill", width='stretch'):
                st.session_state.pop("opp_coo", None)
                st.session_state.pop("opp_coi", None)
                st.session_state.pop("opp_hs", None)
                st.rerun()

    if coo_sel and "coo" in df.columns:
        df = df[df["coo"].isin(coo_sel)]
    if coi_sel and "coi" in df.columns:
        df = df[df["coi"].isin(coi_sel)]
    if hs_sel and "hs code" in df.columns:
        df = df[df["hs code"].isin(hs_sel)]

    # ── Derived numeric columns ───────────────────────────────────────────────
    def _n(col):
        return pd.to_numeric(df[col], errors="coerce").fillna(0.0) if col in df.columns else pd.Series([0.0] * len(df), index=df.index)

    df = df.copy()
    df["_customs"]    = _n("customs value")
    df["_duty_paid"]  = _n("duty paid")
    df["_def_duties"] = _n("Default Duties")
    df["_min_duties"] = _n("Minimum Duties")
    df["_overpaid"]   = df["_duty_paid"] - df["_min_duties"]

    # Minimum Duty Paid: |duty_paid - min_duties| / min_duties <= 5%
    _min_d = df["_min_duties"].abs()
    _denom = _min_d.where(_min_d > 0)
    df["_min_duty_paid"] = (
        (abs(df["_duty_paid"] - df["_min_duties"]) / _denom <= 0.05).fillna(False)
        | ((_min_d < 0.01) & (df["_duty_paid"].abs() < 0.01))
    )
    _has_date = "date" in df.columns
    if _has_date:
        df["_date_p"] = pd.to_datetime(df["date"], errors="coerce")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    n_transactions  = len(df)
    n_opportunities = int((df["_overpaid"] > 0).sum())
    customs_total   = float(df["_customs"].sum())
    duty_exposure   = float(df["_def_duties"].sum())
    duty_paid_total = float(df["_duty_paid"].sum())
    overpaid_total  = float(df["_overpaid"].clip(lower=0).sum())

    _render_kpi_cards([
        {"label": "# Transactions",   "value": _fmt_int(n_transactions),             "icon": "🧾", "sub": "Total filtered rows"},
        {"label": "# Opportunities",  "value": _fmt_int(n_opportunities),            "icon": "💡", "sub": "Rows with overpaid duties"},
        {"label": "Customs Value",    "value": _fmt_num(customs_total)   + " €", "icon": "💶", "sub": "Sum of customs value"},
        {"label": "Duty Exposure",    "value": _fmt_num(duty_exposure)   + " €", "icon": "📄", "sub": "Sum of default duties"},
        {"label": "Duty Paid",        "value": _fmt_num(duty_paid_total) + " €", "icon": "💳", "sub": "Sum of duties paid"},
        {"label": "Overpaid Duties",  "value": _fmt_num(overpaid_total)  + " €", "icon": "⚠️", "sub": "Duty Paid – Min Duties"},
    ], compact=True)

    st.markdown("")

    # ── Column detection ──────────────────────────────────────────────────────
    prod_col = next((c for c in ["product", "material number", "material"] if c in df.columns), None)
    prog_col = next(
        (c for c in ["Min Duty Program Description", "Min Duty Program", "min duty program description"] if c in df.columns),
        None,
    )

    # ── 4 charts in a row ─────────────────────────────────────────────────────
    _CHART_LAYOUT = dict(
        height=310,
        margin=dict(l=0, r=8, t=10, b=0),
        paper_bgcolor="rgba(255,255,255,0.06)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(
            ticksuffix=" €", tickfont=dict(size=12), gridcolor="rgba(255,255,255,0.07)",
            tickformat=".2s",
            showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1,
        ),
        yaxis=dict(
            tickfont=dict(size=12), gridcolor="rgba(255,255,255,0.07)",
            showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1,
        ),
    )

    ch1, ch2, ch3, ch4 = st.columns(4)

    # 1 — Overpaid Duties by Product
    with ch1:
        st.markdown("**Overpaid Duties by Product**")
        if prod_col:
            grp = (
                df.groupby(prod_col)["_overpaid"].sum()
                .reset_index()
                .pipe(lambda d: d[d["_overpaid"] > 0])
                .sort_values("_overpaid", ascending=True)
                .tail(10)
            )
            if not grp.empty:
                fig = px.bar(
                    grp, x="_overpaid", y=prod_col, orientation="h",
                    color_discrete_sequence=[ACCENTURE_PURPLE_CORE],
                    template="plotly_dark",
                )
                fig.update_layout(**_CHART_LAYOUT)
                fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f} €<extra></extra>")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No overpaid duties found.")
        else:
            st.info("No product column in data.")

    # 2 — Overpaid Duties by COI (stacked by program if available)
    with ch2:
        st.markdown("**Overpaid Duties by COI**")
        if "coi" in df.columns:
            if prog_col:
                grp = (
                    df.groupby(["coi", prog_col])["_overpaid"].sum()
                    .reset_index()
                    .pipe(lambda d: d[d["_overpaid"] > 0])
                )
                order = (
                    df.groupby("coi")["_overpaid"].sum()
                    .reset_index()
                    .pipe(lambda d: d[d["_overpaid"] > 0])
                    .sort_values("_overpaid", ascending=True)["coi"]
                    .tolist()
                )
            else:
                grp = (
                    df.groupby("coi")["_overpaid"].sum()
                    .reset_index()
                    .pipe(lambda d: d[d["_overpaid"] > 0])
                    .sort_values("_overpaid", ascending=True)
                )
                order = grp["coi"].tolist()
                prog_col_used = None

            if not grp.empty:
                color_arg = prog_col if prog_col else None
                fig = px.bar(
                    grp, x="_overpaid", y="coi", orientation="h",
                    color=color_arg,
                    color_discrete_sequence=[
                        ACCENTURE_PURPLE_CORE, ACCENTURE_PURPLE_LIGHT,
                        ACCENTURE_PURPLE_DARK, ACCENTURE_PURPLE_DARKEST,
                        ACCENTURE_PURPLE_LIGHTEST,
                    ],
                    template="plotly_dark",
                    category_orders={"coi": order},
                )
                fig.update_layout(**_CHART_LAYOUT)
                fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f} €<extra></extra>")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No overpaid duties found.")
        else:
            st.info("No COI column in data.")

    # 3 — Overpaid Duties by Trade Lane (styled table)
    with ch3:
        st.markdown("**Overpaid Duties by Trade Lane**")
        if "coi" in df.columns and "coo" in df.columns:
            lane = (
                df.groupby(["coi", "coo"])["_overpaid"].sum()
                .reset_index()
                .pipe(lambda d: d[d["_overpaid"] > 0])
                .sort_values("_overpaid", ascending=False)
                .head(15)
                .rename(columns={"coi": "COI", "coo": "COO", "_overpaid": "Overpaid Duties"})
            )
            if not lane.empty:
                st.dataframe(
                    _stripe(lane),
                    hide_index=True,
                    width='stretch',
                    height=320,
                    column_config={
                        **_auto_col_cfg(lane),
                        "Overpaid Duties": st.column_config.NumberColumn("Overpaid Duties", format="%.2f €"),
                    },
                )
            else:
                st.info("No overpaid duties found.")
        else:
            st.info("No COI/COO columns in data.")

    # 4 — Overpaid Duties by Program
    with ch4:
        st.markdown("**Overpaid Duties by Program**")
        if prog_col:
            grp = (
                df.groupby(prog_col)["_overpaid"].sum()
                .reset_index()
                .pipe(lambda d: d[d["_overpaid"] > 0])
                .sort_values("_overpaid", ascending=True)
                .tail(10)
            )
            if not grp.empty:
                fig = px.bar(
                    grp, x="_overpaid", y=prog_col, orientation="h",
                    color_discrete_sequence=[ACCENTURE_PURPLE_LIGHT],
                    template="plotly_dark",
                )
                fig.update_layout(**_CHART_LAYOUT)
                fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f} €<extra></extra>")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No overpaid duties found.")
        else:
            st.info("No program column in data.")

    # ── Build initiative lookup (coo, coi, hs_code) → status list ────────────
    _ini_lookup: Dict[tuple, List[str]] = {}
    if df_initiatives is not None and not df_initiatives.empty:
        for _, _ir in df_initiatives.iterrows():
            _k = (
                str(_ir.get("coo", "") or "").strip().upper(),
                str(_ir.get("coi", "") or "").strip().upper(),
                str(_ir.get("hs_code", "") or "").strip().upper(),
            )
            _ini_lookup.setdefault(_k, []).append(str(_ir.get("status", "") or ""))

    def _ini_label(row) -> str:
        k = (
            str(row.get("coo", "") or "").strip().upper(),
            str(row.get("coi", "") or "").strip().upper(),
            str(row.get("hs code", "") or "").strip().upper(),
        )
        statuses = _ini_lookup.get(k, [])
        if not statuses:
            return ""
        return "✓ " + " / ".join(sorted(set(statuses)))

    # ── Grouped table with row selection ──────────────────────────────────────
    st.markdown("### Opportunities table (grouped by COO · COI · HS Code · Material Number)")
    st.caption("Check rows and click **Create Initiative** to promote them.")

    group_cols = [c for c in ["coo", "coi", "hs code", "material number"] if c in df.columns]

    agg: Dict[str, Any] = {
        "_customs":    "sum",
        "_duty_paid":  "sum",
        "_def_duties": "sum",
        "_min_duties": "sum",
        "_overpaid":   "sum",
    }
    if prod_col and prod_col not in group_cols:
        agg[prod_col] = "first"
    if prog_col and prog_col not in group_cols:
        agg[prog_col] = lambda x: ", ".join(x.dropna().astype(str).unique()[:2])
    for extra in ["Default Duty Rate", "Min Duty Rate"]:
        if extra in df.columns and extra not in group_cols:
            agg[extra] = "first"

    grouped = (
        df.groupby(group_cols)
        .agg(agg)
        .reset_index()
        .rename(columns={
            "_customs":    "Customs Value",
            "_duty_paid":  "Duty Paid",
            "_def_duties": "Default Duties",
            "_min_duties": "Duty To-Be Paid",
            "_overpaid":   "Overpaid Duties",
        })
        .sort_values("Overpaid Duties", ascending=False)
    )

    # Filter to rows with actual overpayment opportunity
    grouped = grouped[grouped["Overpaid Duties"] > 0].copy()

    # ── 5 new columns ─────────────────────────────────────────────────────────
    grouped["Duties Paid > Default Duties"] = (
        grouped["Duty Paid"] > grouped["Default Duties"] * 1.25
    )

    if _has_date and "_date_p" in df.columns:
        _fta_rows = df[df["_min_duty_paid"]].copy()
        if not _fta_rows.empty and group_cols:
            _fta_dates = (
                _fta_rows.groupby(group_cols)["_date_p"]
                .agg(["min", "max"])
                .reset_index()
                .rename(columns={"min": "first_fta", "max": "last_fta"})
            )
            _op_rows = df[df["_overpaid"] > 0].copy()
            if not _op_rows.empty:
                _op_dates = (
                    _op_rows.groupby(group_cols)["_date_p"]
                    .agg(["min", "max"])
                    .reset_index()
                    .rename(columns={"min": "min_op", "max": "max_op"})
                )
            else:
                _op_dates = pd.DataFrame(columns=group_cols + ["min_op", "max_op"])
            grouped = grouped.merge(_fta_dates, on=group_cols, how="left")
            grouped = grouped.merge(_op_dates, on=group_cols, how="left")
            grouped["FTA Applied Previously"] = (
                grouped["first_fta"].notna()
                & grouped["min_op"].notna()
                & (grouped["first_fta"] < grouped["min_op"])
            )
            grouped["FTA Applied Afterwards"] = (
                grouped["last_fta"].notna()
                & grouped["max_op"].notna()
                & (grouped["last_fta"] > grouped["max_op"])
            )
            grouped = grouped.rename(columns={"first_fta": "First FTA Rate Paid", "last_fta": "Last FTA Rate Paid"})
            grouped = grouped.drop(columns=["min_op", "max_op"])
        else:
            for _c in ["FTA Applied Previously", "FTA Applied Afterwards"]:
                grouped[_c] = False
            for _c in ["First FTA Rate Paid", "Last FTA Rate Paid"]:
                grouped[_c] = pd.NaT
    else:
        for _c in ["FTA Applied Previously", "FTA Applied Afterwards"]:
            grouped[_c] = False
        for _c in ["First FTA Rate Paid", "Last FTA Rate Paid"]:
            grouped[_c] = pd.NaT

    # Indicator column: shows existing initiative status or blank
    grouped["Initiative"] = grouped.apply(_ini_label, axis=1)

    grouped = grouped.reset_index(drop=True)

    # Highlight True cells in boolean columns with a light red background
    _bool_highlight = [
        c for c in ["Duties Paid > Default Duties", "FTA Applied Previously", "FTA Applied Afterwards"]
        if c in grouped.columns
    ]

    def _bool_style(col):
        if col.name in _bool_highlight:
            return col.map(lambda v: "background-color: rgba(210,40,40,0.65); color: #fff;" if v else "")
        return [""] * len(col)

    money_cfg = {
        "Initiative":      st.column_config.TextColumn("Initiative", disabled=True, width="medium"),
        "material number": st.column_config.TextColumn("Material Number", disabled=True),
        **{
            c: st.column_config.NumberColumn(c, format="%.2f €")
            for c in ["Customs Value", "Duty Paid", "Default Duties", "Duty To-Be Paid", "Overpaid Duties"]
            if c in grouped.columns
        },
        **{
            c: st.column_config.CheckboxColumn(c, disabled=True)
            for c in ["Duties Paid > Default Duties", "FTA Applied Previously", "FTA Applied Afterwards"]
            if c in grouped.columns
        },
        **{
            c: st.column_config.DateColumn(c, format="YYYY-MM-DD")
            for c in ["First FTA Rate Paid", "Last FTA Rate Paid"]
            if c in grouped.columns
        },
    }

    opp_event = st.dataframe(
        _stripe(_make_arrow_safe(grouped)).apply(_bool_style),
        width='stretch',
        column_config={**_auto_col_cfg(grouped), **money_cfg},
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
        key="opp_table_editor",
    )

    selected_indices = opp_event.selection.rows
    n_sel = len(selected_indices)

    # Split selected into new vs already-existing
    sel_rows_all = grouped.iloc[selected_indices].copy()
    already_exist_mask = sel_rows_all["Initiative"].str.len() > 0
    n_existing = int(already_exist_mask.sum())
    n_new = n_sel - n_existing

    _opp_btn1, _opp_btn2, info_col = st.columns([2, 2, 4])
    with _opp_btn1:
        create_clicked = st.button(
            f"Create Initiative ({n_sel} rows)" if n_sel > 0 else "Create Initiative",
            type="primary",
            disabled=(n_sel == 0),
            key="opp_btn_create_initiative",
            width='stretch',
        )
    with _opp_btn2:
        drill_results_clicked = st.button(
            f"Show Details ({n_sel})" if n_sel > 0 else "Show Details",
            key="opp_btn_drill_results",
            disabled=(n_sel == 0),
            width='stretch',
            help="Show matching transactions in the Results tab",
        )
    with info_col:
        if n_sel > 0:
            if n_existing > 0 and n_new > 0:
                st.warning(
                    f"{n_existing} row(s) already have an initiative and will be **skipped**. "
                    f"{n_new} new row(s) will be created.",
                    icon="⚠️",
                )
            elif n_existing > 0 and n_new == 0:
                st.error(
                    f"All {n_existing} selected row(s) already have an initiative. Nothing will be created.",
                    icon="🚫",
                )
            else:
                st.caption(f"{n_new} new row(s) selected — click to promote to Initiatives tab.")

    if drill_results_clicked and n_sel > 0:
        st.session_state["opp_drill_results"] = {
            "coo": sel_rows_all["coo"].dropna().astype(str).str.strip().unique().tolist(),
            "coi": sel_rows_all["coi"].dropna().astype(str).str.strip().unique().tolist(),
            "hs":  sel_rows_all["hs code"].dropna().astype(str).str.strip().unique().tolist(),
        }
        st.session_state["goto_tab"] = 1  # Results tab
        st.rerun()

    if create_clicked and n_new > 0:
        from src.db import save_initiatives as _save_init
        new_rows = sel_rows_all[~already_exist_mask].drop(columns=["Initiative"], errors="ignore")
        records = []
        for _, r in new_rows.iterrows():
            ps = float(r.get("Overpaid Duties", 0) or 0)
            records.append({
                "coo":                      str(r.get("coo", "") or ""),
                "coi":                      str(r.get("coi", "") or ""),
                "hs_code":                  str(r.get("hs code", "") or ""),
                "material_number":          str(r.get("material number", "") or ""),
                "customs_value":            float(r.get("Customs Value", 0) or 0),
                "duty_paid":                float(r.get("Duty Paid", 0) or 0),
                "default_duties":           float(r.get("Default Duties", 0) or 0),
                "min_duties":               float(r.get("Duty To-Be Paid", 0) or 0),
                "potential_savings":        ps,
                "annual_savings_est":       ps,
                "savings_realized":         0.0,
                "reimbursements":           0.0,
                "potential_reimbursements": 0.0,
                "status":                   "Identified",
                "comments":                 "",
                "program_description":      str(r.get(prog_col, "") or "") if prog_col else "",
            })
        saved = _save_init(records)
        st.success(f"{saved} initiative(s) created successfully. Check the Initiatives tab.")
        st.rerun()


# -----------------------------------------------------------------------------
# Initiatives tab
# -----------------------------------------------------------------------------
_INITIATIVE_STATUS_OPTIONS = ["Identified", "Validated", "Discarded", "Completed"]
_STATUS_COLOR = {
    "Identified": ACCENTURE_PURPLE_LIGHT,
    "Validated":  ACCENTURE_PURPLE_CORE,
    "Discarded":  "rgba(255,120,120,0.85)",
    "Completed":  "rgba(120,255,200,0.85)",
}


def render_tab_initiatives(df_initiatives: Optional[pd.DataFrame]) -> None:

    from src.db import update_initiatives as _upd_init, delete_initiatives as _del_init

    if df_initiatives is None or df_initiatives.empty:
        _render_empty_state(
            "No initiatives yet", "🎯",
            "Select rows in the Opportunities tab and click Create Initiative.",
        )
        return

    # Apply sidebar COO/COI filter to initiatives (uses hs_code variant too)
    _sf_coo = st.session_state.get("sf_coo", "All")
    _sf_coi = st.session_state.get("sf_coi", "All")
    df = df_initiatives.copy()
    if _sf_coo and _sf_coo != "All" and "coo" in df.columns:
        df = df[df["coo"].astype(str).str.strip() == _sf_coo]
    if _sf_coi and _sf_coi != "All" and "coi" in df.columns:
        df = df[df["coi"].astype(str).str.strip() == _sf_coi]

    # Period dates (read from session_state before any computation)
    _today     = date.today()
    _def_ps    = date(_today.year, 1, 1)
    _period_ps = pd.Timestamp(st.session_state.get("ini_period_start", _def_ps))
    _period_pe = pd.Timestamp(st.session_state.get("ini_period_end",   _today))

    # ── Group A: computed display columns ─────────────────────────────────────
    def _fn(col): return pd.to_numeric(df[col], errors="coerce").fillna(0.0) if col in df.columns else pd.Series([0.0] * len(df), index=df.index)

    _cv   = _fn("customs_value")
    _dp   = _fn("duty_paid")
    _md   = _fn("min_duties")
    _sr   = _fn("savings_realized")
    _rei  = _fn("reimbursements")
    _pr   = _fn("potential_reimbursements")

    df = df.copy()
    df["_asis_rate"]              = (_dp / _cv.where(_cv > 0) * 100).round(4)
    df["_tobe_rate"]              = (_md / _cv.where(_cv > 0) * 100).round(4)
    df["_initial_overpaid"]       = (_dp - _md).round(2)
    df["_total_savings_realized"] = (_sr + _rei).round(2)

    def _end_date(row):
        if str(row.get("status", "")) in ("Completed", "Closed"):
            impl = str(row.get("implementation_date", "") or "").strip()
            if impl:
                try:
                    return (pd.to_datetime(impl) + pd.Timedelta(days=365)).strftime("%Y-%m-%d")
                except Exception:
                    pass
        return ""

    df["_end_date"]         = df.apply(_end_date, axis=1)
    df["_final_overpaid"]   = (df["_initial_overpaid"] - _rei).round(2)

    # ── Groups C + D: cross-reference with stored transactions (single pass) ────
    _AUTO_COLS = [
        "_est_annual_cv", "_auto_annual_savings", "_total_potential_savings",
        "_post_cv", "_post_dp", "_realized_avg_rate", "_auto_savings_realized",
        "_period_cv", "_period_dp", "_period_avg_rate", "_period_duty_savings",
        "_period_total_savings", "_period_days", "_period_expected_savings", "_period_remaining",
    ]
    try:
        from src.db import load_merged_results as _load_tx
        _df_tx_raw = _load_tx()
        _needed = ["date", "coo", "coi", "hs code", "material number",
                   "customs value", "duty paid", "Minimum Duties"]
        if not _df_tx_raw.empty and all(c in _df_tx_raw.columns for c in _needed):
            _tx = _df_tx_raw[_needed].copy()
            _tx.columns = ["_d", "_coo", "_coi", "_hs", "_mat", "_cv", "_dp", "_md"]
            _tx["_coo"] = _tx["_coo"].astype(str).str.strip().str.upper()
            _tx["_coi"] = _tx["_coi"].astype(str).str.strip().str.upper()
            _tx["_hs"]  = _tx["_hs"].astype(str).str.strip()
            _tx["_mat"] = _tx["_mat"].fillna("").astype(str).str.strip()
            _tx["_dp"]  = pd.to_numeric(_tx["_dp"], errors="coerce").fillna(0)
            _tx["_cv"]  = pd.to_numeric(_tx["_cv"], errors="coerce").fillna(0)
            _tx["_dp_"] = pd.to_datetime(_tx["_d"], errors="coerce")

            _all_rows = []
            for _, _ini in df.iterrows():
                _icoo = str(_ini.get("coo", "") or "").strip().upper()
                _icoi = str(_ini.get("coi", "") or "").strip().upper()
                _ihs  = str(_ini.get("hs_code", "") or "").strip()
                _imat = str(_ini.get("material_number", "") or "").strip()
                _icv  = float(_ini.get("customs_value", 0) or 0)
                _idp  = float(_ini.get("duty_paid", 0) or 0)
                _imd  = float(_ini.get("min_duties", 0) or 0)
                _ar   = _idp / _icv if _icv > 0 else 0.0
                _tr   = _imd / _icv if _icv > 0 else 0.0
                _ipr  = float(_ini.get("potential_reimbursements", 0) or 0)

                _m = (_tx["_coo"] == _icoo) & (_tx["_coi"] == _icoi) & (_tx["_hs"] == _ihs)
                if _imat:
                    _m = _m & (_tx["_mat"] == _imat)
                _tm = _tx[_m]

                _sd = pd.to_datetime(str(_ini.get("start_date", "") or "").strip(), errors="coerce")
                _id = pd.to_datetime(str(_ini.get("implementation_date", "") or "").strip(), errors="coerce")
                _ed = _id + pd.Timedelta(days=365) if pd.notna(_id) else pd.NaT

                # ── Group C: pre-implementation ───────────────────────────────
                _pm = _tm["_dp_"].notna()
                if pd.notna(_sd):
                    _pm = _pm & (_tm["_dp_"] > _sd)
                if pd.notna(_id):
                    _pm = _pm & (_tm["_dp_"] < _id)
                _pre = _tm[_pm]
                if _pre.empty:
                    _ecv = 0.0
                else:
                    _span = (_pre["_dp_"].max() - _pre["_dp_"].min()).days
                    _ecv = float(_pre["_cv"].sum())
                    if _span > 1:
                        _ecv = round(_ecv / _span * 365, 2)

                _auto_sav = round(_ecv * (_ar - _tr), 2)
                _tps = round(max(_auto_sav, 0) + _ipr, 2)

                # ── Group C: post-implementation ──────────────────────────────
                _pcv, _pdp, _rr, _asr = 0.0, 0.0, 0.0, 0.0
                if pd.notna(_id):
                    _pom = _tm["_dp_"].notna() & (_tm["_dp_"] >= _id)
                    if pd.notna(_ed):
                        _pom = _pom & (_tm["_dp_"] <= _ed)
                    _post = _tm[_pom]
                    if not _post.empty:
                        _pcv = round(float(_post["_cv"].sum()), 2)
                        _pdp = round(float(_post["_dp"].sum()), 2)
                        _rr  = round(_pdp / _pcv * 100, 4) if _pcv > 0 else 0.0
                        _asr = round(max(_pcv * _ar - _pdp, 0), 2)

                # ── Group D: period analysis ──────────────────────────────────
                _per_cv, _per_dp, _days = 0.0, 0.0, 0
                if pd.notna(_id):
                    _eff_s = max(_id, _period_ps)
                    _eff_e = min(_ed, _period_pe) if pd.notna(_ed) else _period_pe
                    if _eff_s <= _eff_e:
                        _periom = (
                            _tm["_dp_"].notna() &
                            (_tm["_dp_"] >= _eff_s) &
                            (_tm["_dp_"] <= _eff_e)
                        )
                        _ptx = _tm[_periom]
                        if not _ptx.empty:
                            _per_cv = round(float(_ptx["_cv"].sum()), 2)
                            _per_dp = round(float(_ptx["_dp"].sum()), 2)
                        _days = max((_eff_e - _eff_s).days, 0)

                _per_avg  = round(_per_dp / _per_cv * 100, 4) if _per_cv > 0 else 0.0
                _per_dsav = round(max(_per_cv * _ar - _per_dp, 0), 2)
                _per_tot  = _per_dsav
                _expected = round(_tps * _days / 365, 2) if _days > 0 and _tps > 0 else 0.0
                _remain   = round(max(_expected - _per_tot, 0), 2)

                _all_rows.append({
                    "id": int(_ini["id"]),
                    "_est_annual_cv":          round(_ecv, 2),
                    "_auto_annual_savings":    _auto_sav,
                    "_total_potential_savings": _tps,
                    "_post_cv":                _pcv,
                    "_post_dp":                _pdp,
                    "_realized_avg_rate":      _rr,
                    "_auto_savings_realized":  _asr,
                    "_period_cv":              _per_cv,
                    "_period_dp":              _per_dp,
                    "_period_avg_rate":        _per_avg,
                    "_period_duty_savings":    _per_dsav,
                    "_period_total_savings":   _per_tot,
                    "_period_days":            _days,
                    "_period_expected_savings":_expected,
                    "_period_remaining":       _remain,
                })

            _auto_df = pd.DataFrame(_all_rows)
            df = df.merge(_auto_df, on="id", how="left")
        else:
            for _c in _AUTO_COLS:
                df[_c] = float("nan")
    except Exception:
        for _c in _AUTO_COLS:
            df[_c] = float("nan")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    def _f(col): return pd.to_numeric(df[col], errors="coerce").fillna(0.0) if col in df.columns else pd.Series([0.0]*len(df))

    ann_savings        = float(_f("_auto_annual_savings").sum())
    pot_reimbursements = float(_f("potential_reimbursements").sum())
    pot_savings        = ann_savings + pot_reimbursements
    fta_realized       = float(_f("savings_realized").sum())
    reimbursed         = float(_f("reimbursements").sum())
    total_realized     = fta_realized + reimbursed

    _render_kpi_cards([
        {"label": "Est. Annual Savings",        "value": _fmt_num(ann_savings)        + " €", "icon": "📅", "sub": "Auto-computed from transaction data"},
        {"label": "Potential Reimbursements",  "value": _fmt_num(pot_reimbursements) + " €", "icon": "🔄", "sub": "Sum of potential reimbursements"},
        {"label": "Total Potential Savings",   "value": _fmt_num(pot_savings)        + " €", "icon": "💡", "sub": "Annual Savings + Potential Reimbursements"},
        {"label": "FTA Savings Realized",      "value": _fmt_num(fta_realized)       + " €", "icon": "✅", "sub": "Sum of savings realized"},
        {"label": "Reimbursements Realized",   "value": _fmt_num(reimbursed)         + " €", "icon": "💰", "sub": "Sum of reimbursements realized"},
        {"label": "Total Savings Realized",    "value": _fmt_num(total_realized)     + " €", "icon": "🏆", "sub": "FTA Realized + Reimbursements Realized"},
    ], compact=True)

    st.markdown("")

    # ── Charts ────────────────────────────────────────────────────────────────
    _CL = dict(
        paper_bgcolor="rgba(255,255,255,0.06)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=8, t=30, b=0), showlegend=False,
        font=dict(color="rgba(255,255,255,0.80)", size=13),
    )
    _AXIS = dict(
        gridcolor="rgba(255,255,255,0.07)", tickfont=dict(size=12),
        showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1,
    )

    cch1, cch2 = st.columns(2)

    # 1 — #Initiatives by Status (horizontal stacked by COI)
    with cch1:
        st.markdown("**#Initiatives by Status**")
        if "status" in df.columns:
            if "coi" in df.columns:
                grp = df.groupby(["status", "coi"]).size().reset_index(name="count")
            else:
                grp = df.groupby("status").size().reset_index(name="count")
                grp["coi"] = "All"

            status_order = [s for s in _INITIATIVE_STATUS_OPTIONS if s in grp["status"].unique()]
            fig = px.bar(
                grp, x="count", y="status", color="coi", orientation="h",
                template="plotly_dark",
                color_discrete_sequence=[
                    ACCENTURE_PURPLE_CORE, ACCENTURE_PURPLE_LIGHT,
                    ACCENTURE_PURPLE_DARK, ACCENTURE_PURPLE_LIGHTEST,
                    ACCENTURE_PURPLE_DARKEST,
                ],
                category_orders={"status": status_order},
            )
            fig.update_layout(height=280, **_CL)
            fig.update_xaxes(**_AXIS); fig.update_yaxes(**_AXIS)
            fig.update_traces(hovertemplate="<b>%{y}</b><br>%{fullData.name}: %{x:,d}<extra></extra>")
            st.plotly_chart(fig, width='stretch')

    # 2 — Total Potential Savings by COI (vertical bar)
    with cch2:
        st.markdown("**Total Potential Savings by COI**")
        if "coi" in df.columns:
            grp = (
                df.groupby("coi")["_total_potential_savings"].sum()
                .reset_index()
                .sort_values("_total_potential_savings", ascending=False)
            )
            fig = px.bar(
                grp, x="coi", y="_total_potential_savings",
                template="plotly_dark",
                color_discrete_sequence=[ACCENTURE_PURPLE_CORE],
            )
            fig.update_layout(height=280, yaxis_ticksuffix=" €", **_CL)
            fig.update_xaxes(**_AXIS)
            fig.update_yaxes(**_AXIS, tickformat=".2s")
            fig.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,.0f} €<extra></extra>")
            st.plotly_chart(fig, width='stretch')

    cch3, cch4 = st.columns(2)

    # 3 — Total Savings Realized by Material Number (vertical bar)
    with cch3:
        st.markdown("**Total Savings Realized by Material Number**")
        _mat_chart_col = next((c for c in ["material_number", "product"] if c in df.columns), None)
        if _mat_chart_col:
            grp = (
                df[df[_mat_chart_col].notna() & (df[_mat_chart_col] != "")]
                .groupby(_mat_chart_col)["savings_realized"].sum()
                .reset_index()
                .sort_values("savings_realized", ascending=False)
                .head(15)
            )
            if not grp.empty:
                fig = px.bar(
                    grp, x=_mat_chart_col, y="savings_realized",
                    template="plotly_dark",
                    color_discrete_sequence=[ACCENTURE_PURPLE_CORE],
                )
                fig.update_layout(height=280, yaxis_ticksuffix=" €", xaxis_tickangle=-45, **_CL)
                fig.update_xaxes(**_AXIS)
                fig.update_yaxes(**_AXIS, tickformat=".2s")
                fig.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,.0f} €<extra></extra>")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No savings realized data yet.")
        else:
            st.info("No material number column in data.")

    # 4 — Total Savings Realized by COI (stacked: FTA + Reimbursements)
    with cch4:
        st.markdown("**Total Savings Realized by COI**")
        if "coi" in df.columns:
            fta = df.groupby("coi")["savings_realized"].sum().reset_index().rename(columns={"savings_realized": "value"})
            fta["type"] = "FTA Savings"
            rei = df.groupby("coi")["reimbursements"].sum().reset_index().rename(columns={"reimbursements": "value"})
            rei["type"] = "Reimbursements"
            stacked = pd.concat([fta, rei], ignore_index=True)
            stacked = stacked[stacked["value"] > 0]
            if not stacked.empty:
                coi_order = (
                    stacked.groupby("coi")["value"].sum()
                    .sort_values(ascending=False).index.tolist()
                )
                fig = px.bar(
                    stacked, x="coi", y="value", color="type",
                    template="plotly_dark",
                    color_discrete_sequence=[ACCENTURE_PURPLE_CORE, ACCENTURE_PURPLE_LIGHT],
                    category_orders={"coi": coi_order},
                )
                fig.update_layout(
                    height=280, yaxis_ticksuffix=" €",
                    showlegend=True,
                    legend=dict(font=dict(size=12), bgcolor="rgba(0,0,0,0)"),
                    **{k: v for k, v in _CL.items() if k != "showlegend"},
                )
                fig.update_xaxes(**_AXIS)
                fig.update_yaxes(**_AXIS, tickformat=".2s")
                fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:,.0f} €<extra></extra>")
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No savings realized data yet.")

    # ── Period date-pickers ───────────────────────────────────────────────────
    st.markdown("### Period analysis")
    _pd1, _pd2, _pd3 = st.columns([2, 2, 6])
    with _pd1:
        st.date_input("Period start", value=_def_ps, key="ini_period_start")
    with _pd2:
        st.date_input("Period end", value=_today, key="ini_period_end")
    with _pd3:
        st.caption("Period columns are recomputed on each date change.")

    # ── Initiatives editor ────────────────────────────────────────────────────
    st.markdown("### Initiatives table")
    st.caption(
        "Check **Select** to view initiative details below, group, or delete. "
        "Editable fields: **Status**, **Comments**."
    )

    _NUMERIC_EDITABLE = {"savings_realized", "reimbursements", "potential_reimbursements"}
    _FRIENDLY = {
        # Initiative Definition
        "id":                         "ID",
        "coo":                        "COO",
        "coi":                        "COI",
        "hs_code":                    "HS Code",
        "material_number":            "Material Number",
        "program_description":        "Program",
        # Status
        "status":                     "Status",
        "comments":                   "Comments",
        "start_date":                 "Start Date",
        "implementation_date":        "Implementation Date",
        "_end_date":                  "End Date",
        "created_at":                 "Created At",
        # Potential Savings · Before Implementation Date
        "customs_value":              "PRE · Customs Value",
        "duty_paid":                  "PRE · Total Duty Paid",
        "default_duties":             "PRE · Default Duties",
        "min_duties":                 "PRE · Duty To-Be Paid",
        "_asis_rate":                 "PRE · As-is Rate (%)",
        "_tobe_rate":                 "PRE · To-Be Rate (%)",
        "_initial_overpaid":          "PRE · Initial Overpaid",
        "_est_annual_cv":             "PRE · Est. Annual CV",
        "_auto_annual_savings":       "PRE · Est. Annual Savings",
        "potential_reimbursements":   "PRE · Potential Reimbursements",
        "_total_potential_savings":   "PRE · Total Potential Savings",
        # Total Savings Realized · After Implementation Date
        "_post_cv":                   "POST · Total CV",
        "_post_dp":                   "POST · Total Duty Paid",
        "_realized_avg_rate":         "POST · Avg. Rate (%)",
        "_auto_savings_realized":     "POST · Duty Savings (auto)",
        "_final_overpaid":            "POST · Final Overpaid",
        "savings_realized":           "POST · Savings Realized",
        "reimbursements":             "POST · Reimbursements Realized",
        "_total_savings_realized":    "POST · Total Savings Realized",
        # Savings Realized · Period
        "_period_cv":                 "PERIOD · Total CV",
        "_period_dp":                 "PERIOD · Total Duty Paid",
        "_period_avg_rate":           "PERIOD · Avg. Rate (%)",
        "_period_duty_savings":       "PERIOD · Duty Savings",
        "_period_total_savings":      "PERIOD · Total Savings",
        "_period_days":               "PERIOD · # Days",
        "_period_expected_savings":   "PERIOD · Expected Savings",
        "_period_remaining":          "PERIOD · Remaining Savings",
    }

    # ── Group-aware display ────────────────────────────────────────────────
    has_groups = "group_id" in df.columns and df["group_id"].notna().any()
    child_ids: set = set()
    _NUM_AGG_COLS = [
        "customs_value", "duty_paid", "default_duties", "min_duties",
        "potential_savings", "savings_realized",
        "reimbursements", "potential_reimbursements",
    ]

    if has_groups:
        group_sizes: Dict[int, int] = (
            df[df["group_id"].notna()]
            .groupby("group_id")["id"]
            .count()
            .to_dict()
        )
        child_ids = set(
            df[(df["group_id"].notna()) & (df["id"] != df["group_id"])]["id"].tolist()
        )
        df_main = df[~df["id"].isin(child_ids)].copy()

        # Replace parent row numeric values with the sum across all group members
        for _gid_key, _gsz in group_sizes.items():
            if _gsz < 2:
                continue
            _all_members = df[df["group_id"] == _gid_key]
            _pidx = df_main.index[df_main["id"] == _gid_key].tolist()
            if not _pidx:
                continue
            for _nc in _NUM_AGG_COLS:
                if _nc in df.columns and _nc in df_main.columns:
                    df_main.loc[_pidx[0], _nc] = (
                        pd.to_numeric(_all_members[_nc], errors="coerce").fillna(0).sum()
                    )

        def _grp_badge(row) -> str:
            gid = row.get("group_id")
            if pd.isna(gid):
                return ""
            return f"⊞ {int(group_sizes.get(int(gid), 1))}"

        df_main["_group"] = df_main.apply(_grp_badge, axis=1)
    else:
        df_main = df.copy()

    display_cols_base = [
        "id", "coo", "coi", "hs_code", "material_number", "program_description",
        "status", "comments",
        "customs_value", "duty_paid", "_initial_overpaid",
    ]
    extra_cols = ["_group"] if has_groups else []
    display_cols = extra_cols + display_cols_base

    df_main = df_main.sort_values("id", ascending=True).reset_index(drop=True)
    disp = df_main[[c for c in display_cols if c in df_main.columns]].copy()
    disp.insert(0, "_select", False)

    col_cfg: dict = {
        "_select":      st.column_config.CheckboxColumn("Select", default=False, width="small"),
        "id":           st.column_config.NumberColumn("ID", disabled=True, width="small"),
        "status":    st.column_config.SelectboxColumn(
                         "Status", options=_INITIATIVE_STATUS_OPTIONS, width="medium"
                     ),
        "start_date": st.column_config.TextColumn(
            "Start Date", width="medium", help="Initiative start date (YYYY-MM-DD)",
        ),
        "implementation_date": st.column_config.TextColumn(
            "Implementation Date", width="medium",
            help="Target implementation date (YYYY-MM-DD)",
        ),
        "_end_date":  st.column_config.TextColumn("End Date", disabled=True, width="medium"),
        "comments":   st.column_config.TextColumn("Comments"),
        "created_at": st.column_config.TextColumn("Created At", disabled=True, width="medium"),
    }
    if has_groups:
        col_cfg["_group"] = st.column_config.TextColumn("Group", disabled=True, width="small")
    for ro in ["coo", "coi", "hs_code", "material_number", "program_description"]:
        if ro in disp.columns:
            col_cfg[ro] = st.column_config.TextColumn(_FRIENDLY.get(ro, ro), disabled=True)
    for mc in ["customs_value", "duty_paid", "default_duties", "min_duties"]:
        if mc in disp.columns:
            col_cfg[mc] = st.column_config.NumberColumn(_FRIENDLY.get(mc, mc), format="%.2f €", disabled=True)
    for mc in ["_initial_overpaid", "_final_overpaid",
               "_est_annual_cv", "_auto_annual_savings",
               "_post_cv", "_post_dp", "_auto_savings_realized",
               "_total_potential_savings", "_total_savings_realized",
               "_period_cv", "_period_dp", "_period_duty_savings",
               "_period_total_savings", "_period_expected_savings", "_period_remaining"]:
        if mc in disp.columns:
            col_cfg[mc] = st.column_config.NumberColumn(_FRIENDLY.get(mc, mc), format="%.2f €", disabled=True)
    for mc in ["_asis_rate", "_tobe_rate", "_realized_avg_rate", "_period_avg_rate"]:
        if mc in disp.columns:
            col_cfg[mc] = st.column_config.NumberColumn(_FRIENDLY.get(mc, mc), format="%.3f", disabled=True)
    if "_period_days" in disp.columns:
        col_cfg["_period_days"] = st.column_config.NumberColumn(
            _FRIENDLY.get("_period_days"), format="%d", disabled=True
        )
    for mc in _NUMERIC_EDITABLE:
        if mc in disp.columns:
            col_cfg[mc] = st.column_config.NumberColumn(_FRIENDLY.get(mc, mc), format="%.2f €")
    col_cfg["_initial_overpaid"] = st.column_config.NumberColumn("Duties Overpaid", format="%.2f €", disabled=True)

    edited_ini = st.data_editor(
        _make_arrow_safe(disp),
        width='stretch',
        column_config=col_cfg,
        hide_index=True,
        num_rows="fixed",
        key="ini_table_editor",
    )

    # ── Expanded group sub-tables ──────────────────────────────────────────
    if has_groups:
        all_group_ids = sorted([int(g) for g in df["group_id"].dropna().unique()])
        for _gid in all_group_ids:
            _members = df[df["group_id"] == _gid].copy()
            _parent = _members[_members["id"] == _gid]
            _plabel = ""
            _gname = ""
            if not _parent.empty:
                _p = _parent.iloc[0]
                _plabel = f"{_p.get('coo','')} · {_p.get('coi','')} · {_p.get('hs_code','')}"
                _gname = str(_p.get("group_name", "") or "").strip()
            _exp_header = f"{_gname or f'Group {_gid}'} — {_plabel}  ({len(_members)} initiatives)"
            with st.expander(_exp_header, expanded=False):
                _sub = _members[[c for c in display_cols_base if c in _members.columns]].copy()
                _sub_friendly = {c: _FRIENDLY.get(c, c) for c in _sub.columns}
                _sub_renamed = _sub.rename(columns=_sub_friendly)
                st.dataframe(
                    _stripe(_make_arrow_safe(_sub_renamed)),
                    width='stretch',
                    hide_index=True,
                    column_config=_auto_col_cfg(_sub_renamed),
                )
                _rc1, _rc2 = st.columns([5, 1])
                with _rc1:
                    _new_gname = st.text_input(
                        "Group name",
                        value=_gname,
                        placeholder=f"Group {_gid}",
                        key=f"ini_gname_{_gid}",
                        label_visibility="collapsed",
                    )
                with _rc2:
                    if st.button("Rename", key=f"ini_rename_{_gid}", width='stretch'):
                        from src.db import save_group_name as _save_gname
                        _save_gname(_gid, _new_gname)
                        st.rerun()
                from src.db import ungroup_initiatives as _ungroup_init
                if st.button("Ungroup all", key=f"ini_ungroup_{_gid}"):
                    _ungroup_init([int(i) for i in _members["id"].tolist()])
                    st.success(f"Group {_gid} ungrouped.")
                    st.rerun()

    # ── Gather selected ids (for actions) ─────────────────────────────────
    sel_mask_ini = edited_ini["_select"] == True
    sel_rows_ini = edited_ini[sel_mask_ini].copy()
    n_sel_ini = int(sel_mask_ini.sum())
    sel_ids_ini = [int(r["id"]) for _, r in sel_rows_ini.iterrows()] if n_sel_ini > 0 else []

    # ── Check ungroup eligibility ──────────────────────────────────────────
    can_ungroup_sel = (
        n_sel_ini >= 1
        and has_groups
        and "group_id" in df.columns
        and all(
            not df[df["id"] == sid]["group_id"].isna().all()
            for sid in sel_ids_ini
        )
    )

    # ── Action buttons ─────────────────────────────────────────────────────
    _bcols = st.columns([2, 2, 2, 2])
    with _bcols[0]:
        save_ini = st.button("Save changes", type="primary", key="ini_btn_save", width='stretch')
    with _bcols[1]:
        del_ini = st.button("Delete selected", key="ini_btn_del", width='stretch')
    with _bcols[2]:
        group_clicked = st.button(
            f"Group Initiatives ({n_sel_ini})" if n_sel_ini >= 2 else "Group Initiatives",
            key="ini_btn_group",
            disabled=(n_sel_ini < 2),
            width='stretch',
            help="Merge selected initiatives into a collapsible group",
        )
    with _bcols[3]:
        ungroup_clicked = st.button(
            "Ungroup Selected",
            key="ini_btn_ungroup_sel",
            disabled=(not can_ungroup_sel),
            width='stretch',
            help="Remove selected initiatives from their group",
        )

    # ── Handle Group ───────────────────────────────────────────────────────
    if group_clicked and n_sel_ini >= 2:
        from src.db import group_initiatives as _grp_init
        _grp_init(sel_ids_ini)
        st.success(f"{n_sel_ini} initiatives grouped.")
        st.rerun()

    # ── Handle Ungroup selected ────────────────────────────────────────────
    if ungroup_clicked and can_ungroup_sel:
        from src.db import ungroup_initiatives as _ungroup_sel
        _ungroup_sel(sel_ids_ini)
        st.success(f"{n_sel_ini} initiative(s) removed from their group.")
        st.rerun()

    # ── Save / Delete ──────────────────────────────────────────────────────
    def _vals_differ(old_val, new_val, col: str) -> bool:
        if col in _NUMERIC_EDITABLE:
            try:
                return abs(float(old_val or 0) - float(new_val or 0)) > 1e-6
            except (TypeError, ValueError):
                pass
        return str(old_val) != str(new_val)

    if save_ini:
        base = disp.reset_index(drop=True)
        edit = edited_ini.reset_index(drop=True)
        changes = []
        editable_cols = _NUMERIC_EDITABLE | {"status", "implementation_date", "start_date", "comments"}
        for i in range(min(len(base), len(edit))):
            b, e = base.iloc[i], edit.iloc[i]
            diff: dict = {"id": int(b["id"])}
            for col in editable_cols:
                if col in b.index and col in e.index and _vals_differ(b[col], e[col], col):
                    diff[col] = e[col]
            if len(diff) > 1:
                changes.append(diff)
        if changes:
            n = _upd_init(changes)
            st.success(f"{n} initiative(s) updated.")
            st.rerun()
        else:
            st.info("No changes detected.")

    if del_ini:
        to_del = [
            int(edited_ini.iloc[i]["id"])
            for i in range(len(edited_ini))
            if edited_ini.iloc[i].get("_select") is True or edited_ini.iloc[i].get("_select") == 1
        ]
        if to_del:
            n = _del_init(to_del)
            st.success(f"{n} initiative(s) deleted.")
            st.rerun()
        else:
            st.warning("No rows selected for deletion.")

    # ── Per-initiative detail expanders (selected rows only) ──────────────
    if sel_ids_ini:
        st.markdown("---")
        st.markdown("### Initiative Details")

        def _show_analysis_section(label: str, col_map: dict, rows: pd.DataFrame) -> None:
            st.markdown(f"**{label}**")
            _keys = [k for k in col_map if k in rows.columns]
            if _keys:
                _r = rows[_keys].copy().rename(columns={k: col_map[k] for k in _keys})
                st.dataframe(_stripe(_make_arrow_safe(_r)), hide_index=True, width='stretch',
                             column_config=_auto_col_cfg(_r))

        try:
            from src.db import load_merged_results as _load_tx_detail
            _df_tx_all = _load_tx_detail()
        except Exception:
            _df_tx_all = pd.DataFrame()

        for _ini_id in sel_ids_ini:
            _ini_rows = df_main[df_main["id"] == _ini_id]
            if _ini_rows.empty:
                continue
            _ini = _ini_rows.iloc[0]
            _icoo = str(_ini.get("coo", "") or "").strip()
            _icoi = str(_ini.get("coi", "") or "").strip()
            _ihs  = str(_ini.get("hs_code", "") or "").strip()
            _imat = str(_ini.get("material_number", "") or "").strip()

            _exp_label = f"ID {_ini_id} · {_icoo} · {_icoi} · {_ihs}"
            if _imat:
                _exp_label += f" · {_imat}"

            with st.expander(_exp_label, expanded=True):
                # ── Transactions ───────────────────────────────────────
                st.markdown("**Transactions**")
                if not _df_tx_all.empty and "coo" in _df_tx_all.columns:
                    _tmask = (
                        (_df_tx_all["coo"].astype(str).str.strip().str.upper() == _icoo.upper()) &
                        (_df_tx_all["coi"].astype(str).str.strip().str.upper() == _icoi.upper()) &
                        (_df_tx_all["hs code"].astype(str).str.strip() == _ihs)
                    )
                    if _imat and "material number" in _df_tx_all.columns:
                        _tmask = _tmask & (
                            _df_tx_all["material number"].fillna("").astype(str).str.strip() == _imat
                        )
                    _tx_match = _df_tx_all[_tmask]
                    if _tx_match.empty:
                        st.info("No matching transactions found.")
                    else:
                        _tx_cols = [c for c in [
                            "date", "invoice number", "material number",
                            "coo", "coi", "hs code",
                            "customs value", "cv currency",
                            "duty paid", "dp currency",
                            "Minimum Duties", "status",
                        ] if c in _tx_match.columns]
                        _tx_sub = _tx_match[_tx_cols]
                        st.dataframe(
                            _stripe(_make_arrow_safe(_tx_sub)),
                            hide_index=True, width='stretch',
                            column_config=_auto_col_cfg(_tx_sub),
                        )
                else:
                    st.info("No transaction data available.")

                # ── Dates ──────────────────────────────────────────────
                _show_analysis_section("Dates", {
                    "start_date":          "Start Date",
                    "implementation_date": "Implementation Date",
                    "_end_date":           "End Date",
                }, _ini_rows)

                # ── PRE ────────────────────────────────────────────────
                _show_analysis_section("PRE (Before Implementation)", {
                    "customs_value":            "Customs Value",
                    "duty_paid":                "Total Duty Paid",
                    "min_duties":               "Duty To-Be Paid",
                    "_asis_rate":               "As-is Rate (%)",
                    "_tobe_rate":               "To-Be Rate (%)",
                    "_initial_overpaid":        "Duties Overpaid",
                    "_est_annual_cv":           "Est. Annual CV",
                    "_auto_annual_savings":     "Est. Annual Savings",
                    "potential_reimbursements": "Potential Reimbursements",
                    "_total_potential_savings": "Total Potential Savings",
                }, _ini_rows)

                # ── POST ───────────────────────────────────────────────
                _show_analysis_section("POST (After Implementation)", {
                    "_post_cv":               "Total CV",
                    "_post_dp":               "Total Duty Paid",
                    "_realized_avg_rate":     "Avg. Rate (%)",
                    "_auto_savings_realized": "Duty Savings (auto)",
                    "_final_overpaid":        "Final Overpaid",
                    "savings_realized":       "Savings Realized",
                    "reimbursements":         "Reimbursements Realized",
                    "_total_savings_realized":"Total Savings Realized",
                }, _ini_rows)

                # ── PERIOD ─────────────────────────────────────────────
                _show_analysis_section("PERIOD", {
                    "_period_cv":               "Total CV",
                    "_period_dp":               "Total Duty Paid",
                    "_period_avg_rate":         "Avg. Rate (%)",
                    "_period_duty_savings":     "Duty Savings",
                    "_period_total_savings":    "Total Savings",
                    "_period_days":             "# Days",
                    "_period_expected_savings": "Expected Savings",
                    "_period_remaining":        "Remaining Savings",
                }, _ini_rows)


# -----------------------------------------------------------------------------
# Logs tab
# -----------------------------------------------------------------------------
def render_tab_logs(
    logs: List[Dict[str, Any]],
    run_summary: Optional[Dict[str, Any]],
    run_history: Optional[pd.DataFrame] = None,
    total_queries: int = 0,
) -> None:
    st.subheader("Logs")

    # ── Date filter (by execution date) ───────────────────────────────────
    rh = None
    if run_history is not None and not run_history.empty:
        rh = run_history.copy()
        rh["_date"] = pd.to_datetime(rh["started_at"], errors="coerce").dt.date
        min_date = rh["_date"].dropna().min()
        max_date = rh["_date"].dropna().max()

        if min_date and max_date:
            col_a, col_b = st.columns(2)
            with col_a:
                from_date = st.date_input("Execution date from", value=min_date, min_value=min_date, max_value=max_date, key="log_from")
            with col_b:
                to_date = st.date_input("Execution date to", value=max_date, min_value=min_date, max_value=max_date, key="log_to")
            rh = rh[(rh["_date"] >= from_date) & (rh["_date"] <= to_date)]

    # ── KPIs (computed from filtered run history) ──────────────────────────
    if rh is not None and not rh.empty:
        rh_nc = rh[rh["cancelled"] == 0]
        ok_sum = int(rh_nc["total_ok"].fillna(0).sum())
        fail_sum = int(rh_nc["total_failed"].fillna(0).sum())
        miss_sum = int(rh_nc["total_missing"].fillna(0).sum())
        queries = ok_sum + fail_sum
        total_runs = len(rh_nc)
        denom = ok_sum + fail_sum + miss_sum
        success_rate = ok_sum / denom if denom > 0 else None
    else:
        queries = total_queries
        total_runs = 0
        success_rate = None

    _render_kpi_cards([
        {
            "label": "Total lanes processed",
            "value": _fmt_int(queries),
            "icon": "🔢",
            "sub": "non-cancelled runs (filtered period)",
        },
        {
            "label": "Total Runs",
            "value": _fmt_int(total_runs),
            "icon": "▶️",
            "sub": "completed (non-cancelled)",
        },
        {
            "label": "Success Rate",
            "value": _fmt_pct(success_rate) if success_rate is not None else "N/A",
            "icon": "✅",
            "sub": "ok / (ok + failed + missing)",
        },
    ])
    st.markdown("")

    # ── Run history table ──────────────────────────────────────────────────
    st.markdown("### Run history")
    if rh is not None and not rh.empty:
        _keep = ["id", "ref_date", "started_at", "total_candidates", "total_ok",
                 "total_failed", "total_missing", "cancelled", "account_key",
                 "account_label", "environment"]
        display_cols = [c for c in _keep if c in rh.columns]
        st.caption(f"{len(rh):,} run(s) shown")
        _rh_disp = rh[display_cols]
        st.dataframe(_stripe(_make_arrow_safe(_rh_disp)), width='stretch', column_config=_auto_col_cfg(_rh_disp))
    else:
        st.info("No previous runs found in the database.")

    # ── Current session event log ──────────────────────────────────────────
    if not logs:
        return

    rows = [item for item in logs if item.get("event") != "session_output"]
    df_logs = pd.DataFrame(rows)
    if df_logs.empty:
        return

    st.markdown("### Current session events")
    _dl = df_logs.tail(200)
    st.dataframe(_stripe(_make_arrow_safe(_dl)), width='stretch', column_config=_auto_col_cfg(_dl))
