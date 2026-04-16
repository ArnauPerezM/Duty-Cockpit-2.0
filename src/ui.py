from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, List

import pandas as pd
import plotly.express as px
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

.sb-title{{
  font-size: 26px;
  font-weight: 800;
  margin: 0 0 8px 0;
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
  font-size: 26;
  color: rgba(255,255,255,0.74);
  margin: 0;
}}

.kpi-icon {{
  font-size: 18px;
  opacity: 0.95;
}}

.kpi-value {{
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 0.2px;
  line-height: 1.1;
}}

.kpi-sub {{
  margin-top: 6px;
  font-size: 12px;
  color: rgba(255,255,255,0.60);
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
# Sidebar controls
# -----------------------------------------------------------------------------
def render_sidebar_controls() -> Dict[str, Any]:

    st.image("src/logo.png", width="content")
    st.divider() 
    st.markdown('<div class="sb-title">Controls</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload input Excel",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
    )

    sheet_name = st.text_input("Sheet name", value="Transactions", help="Default: Transactions")

    ref_date = st.date_input(
        "Reference date",
        value=date.today(),
        help="Reference date to obtain the information",
    )
    ref_date_str = ref_date.strftime("%Y-%m-%d")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        analyze_clicked = st.button("Run", type="primary", width="stretch")
    with col2:
        cancel_clicked = st.button("Cancel", width="stretch")

    return {
        "uploaded_file": uploaded_file,
        "sheet_name": sheet_name,
        "ref_date": ref_date_str,
        "analyze_clicked": analyze_clicked,
        "cancel_clicked": cancel_clicked,
    }


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
        submitted = st.form_submit_button("Connect to E2Open", type="primary", use_container_width=True)

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
    return st.button("Logout", use_container_width=True)








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
            }}
            .kpi-card-compact::before {{
              content: "";
              position: absolute;
              left: 0; top: 0;
              height: 2px; width: 100%;
              background: linear-gradient(90deg, {ACCENTURE_PURPLE_DARKEST}, {ACCENTURE_PURPLE_CORE}, {ACCENTURE_PURPLE_LIGHT});
            }}
            .kpi-card-compact .kpi-label {{ font-size: 11px; color: rgba(255,255,255,0.65); margin:0; }}
            .kpi-card-compact .kpi-value {{ font-size: 16px; font-weight: 800; line-height: 1.2; }}
            .kpi-card-compact .kpi-sub   {{ font-size: 10px; color: rgba(255,255,255,0.50); margin-top:2px; }}
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
        icon = _esc(k.get("icon") or "•")
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
            f'  <div class="kpi-head">'
            f'    <div class="kpi-label">{label}</div>'
            f'    <div class="kpi-icon">{icon}</div>'
            f'  </div>'
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
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar=dict(
            outlinewidth=0,
            tickcolor="rgba(255,255,255,0.45)",
            tickfont=dict(color="rgba(255,255,255,0.65)"),
            title=dict(font=dict(color="rgba(255,255,255,0.75)")),
        ),
        title_font=dict(color="rgba(255,255,255,0.88)"),
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

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Top 10 countries (selected metric)")
    if top_money_cols:
        sty = top_df.style.format({c: (lambda v: _fmt_human(v, decimals=1)) for c in top_money_cols})
        st.dataframe(sty, width="stretch")
    else:
        st.dataframe(_make_arrow_safe(top_df), width="stretch")


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
        st.dataframe(_make_arrow_safe(df_clean), width="stretch")
    else:
        st.info("No candidate rows found (or all rows are already marked as analyzed).")

    if df_missing is not None and not df_missing.empty:
        with st.expander("Missing rows (skipped)"):
            st.dataframe(_make_arrow_safe(df_missing), width="stretch")


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
        st.subheader("Results dashboard")
    _btn_ph = _btn_col.empty()  # filled later once data is ready

    if df_merged is None or df_merged.empty:
        st.info("No results yet. Run the analysis to populate this tab.")
        return

    df = df_merged.copy()
    for col in ["coo", "coi", "hs code"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    st.markdown("### Filters")
    c1, c2, c3 = st.columns([1, 1, 1.2])

    coo_opts = sorted(df["coo"].dropna().unique().tolist()) if "coo" in df.columns else []
    coi_opts = sorted(df["coi"].dropna().unique().tolist()) if "coi" in df.columns else []
    hs_opts = sorted(df["hs code"].dropna().unique().tolist()) if "hs code" in df.columns else []

    with c1:
        coo_sel = st.multiselect("COO", options=coo_opts, default=[])
    with c2:
        coi_sel = st.multiselect("COI", options=coi_opts, default=[])
    with c3:
        hs_sel = st.multiselect("HS Code", options=hs_opts, default=[])

    if coo_sel and "coo" in df.columns:
        df = df[df["coo"].isin(coo_sel)]
    if coi_sel and "coi" in df.columns:
        df = df[df["coi"].isin(coi_sel)]
    if hs_sel and "hs code" in df.columns:
        df = df[df["hs code"].isin(hs_sel)]

    st.caption(f"Rows after filters: {len(df):,} / {len(df_merged):,}")

    st.markdown("### KPIs")

    min_duties  = pd.to_numeric(df.get("Minimum Duties", pd.Series([0] * len(df))), errors="coerce") if "Minimum Duties" in df.columns else None
    def_duties  = pd.to_numeric(df.get("Default Duties", pd.Series([0] * len(df))), errors="coerce") if "Default Duties" in df.columns else None
    customs_val = pd.to_numeric(df.get("customs value",  pd.Series([0] * len(df))), errors="coerce") if "customs value"  in df.columns else None
    duty_paid   = pd.to_numeric(df.get("duty paid",      pd.Series([0] * len(df))), errors="coerce") if "duty paid"      in df.columns else None

    customs_sum   = float(customs_val.fillna(0).sum()) if customs_val is not None else None
    min_sum       = float(min_duties.fillna(0).sum())  if min_duties  is not None else None
    def_sum       = float(def_duties.fillna(0).sum())  if def_duties  is not None else None
    paid_sum      = float(duty_paid.fillna(0).sum())   if duty_paid   is not None else None
    savings_total = float((duty_paid.fillna(0) - min_duties.fillna(0)).sum()) if (duty_paid is not None and min_duties is not None) else None

    k1 = [
        {"label": "Filtered rows",      "value": _fmt_int(len(df)), "sub": "Current scope", "icon": "🔎"},
        {"label": "Distinct COI",       "value": _fmt_int(df["coi"].nunique() if "coi" in df.columns else 0), "sub": "Geographic coverage", "icon": "🌍"},
        {"label": "Distinct HS",        "value": _fmt_int(df["hs code"].nunique() if "hs code" in df.columns else 0), "sub": "Classification breadth", "icon": "🏷️"},
        {"label": "Customs Value (EUR)", "value": _fmt_num(customs_sum) + " €", "sub": "Sum of customs value", "icon": "💶"},
    ]
    _render_kpi_cards(k1)

    st.markdown("")
    k2 = [
        {"label": "Duties Paid (EUR)",     "value": _fmt_num(paid_sum)      + " €", "sub": "Sum of duties paid",      "icon": "💳"},
        {"label": "Default Duties (EUR)",  "value": _fmt_num(def_sum)       + " €", "sub": "Sum of default duties",   "icon": "📄"},
        {"label": "Minimum Duties (EUR)",  "value": _fmt_num(min_sum)       + " €", "sub": "Sum of minimum duties",   "icon": "🧾"},
        {"label": "Potential Savings (EUR)", "value": _fmt_num(savings_total) + " €", "sub": "Duties Paid - Minimum", "icon": "💡"},
    ]
    _render_kpi_cards(k2)

    # ── Download Report (top-right placeholder, all visible data) ────────────
    if not df.empty:
        from src.logic import build_report_html as _build_report
        import datetime as _dt
        _fname = f"duty_report_{ref_date or _dt.date.today().isoformat()}.html"
        try:
            _report_bytes = _build_report(
                df_merged=df,
                df_failed=df_failed,
                df_missing=df_missing,
                run_summary=run_summary,
                ref_date=ref_date or "",
                account_label=account_label,
                environment=environment,
            )
            _btn_ph.download_button(
                label="Download Report",
                data=_report_bytes,
                file_name=_fname,
                mime="text/html",
                use_container_width=True,
            )
        except Exception as _rep_err:
            _btn_ph.warning(f"Report error: {_rep_err}")

    st.markdown("### Results table (filtered)")
    st.dataframe(_make_arrow_safe(df), width="stretch")


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
        st.dataframe(_make_arrow_safe(rh[display_cols]), use_container_width=True)
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
    st.dataframe(_make_arrow_safe(df_logs.tail(200)), use_container_width=True)
