from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, List

import pandas as pd
import streamlit as st


# -----------------------------------------------------------------------------
# Accenture palette (purple) — mirrored in .streamlit/custom.css as CSS vars
# -----------------------------------------------------------------------------
ACCENTURE_PURPLE_CORE = "#A100FF"
ACCENTURE_PURPLE_DARK = "#7500C0"
ACCENTURE_PURPLE_DARKEST = "#460073"
ACCENTURE_PURPLE_LIGHT = "#C2A3FF"
ACCENTURE_PURPLE_LIGHTEST = "#E6DCFF"

# Max bars shown in opportunity/initiative charts; prevents visual clutter on large datasets.
_OPP_CHART_CAP = 15


# -----------------------------------------------------------------------------
# Global CSS loader — call once from app.py at startup
# -----------------------------------------------------------------------------
_CUSTOM_CSS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "custom.css"


@st.cache_data(show_spinner=False)
def _read_custom_css() -> str:
    """Read the CSS file once per process; result cached for speed."""
    try:
        return _CUSTOM_CSS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def load_custom_css() -> None:
    """
    Inject .streamlit/custom.css into the page.

    Must be called on EVERY rerun (not just once per session): Streamlit
    rebuilds the DOM each rerun, so st.markdown-injected <style> tags are
    discarded between runs. The file read itself is cached for speed.
    """
    css = _read_custom_css()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)



# -----------------------------------------------------------------------------
# Hero header renderer
# -----------------------------------------------------------------------------
def render_hero_header(
    title: str,
    subtitle: str,
    run_state: str,
    account_label: str = "",
) -> None:
    """
    Visual hero header with a status chip + a gradient status bar.
    run_state: "ready" | "blocked" | "running" | "completed" | "failed" | "cancelled"
    account_label: if set, shown as a secondary chip below the status chip.
    """
    # Styling provided by .streamlit/custom.css (loaded once via load_custom_css()).
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
        f'      <div class="hero-sub">{_esc(subtitle)}</div>'
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
# Sidebar: Backup & Restore
# -----------------------------------------------------------------------------
def _render_sidebar_backup() -> None:
    from src.db import backup_db as _backup_db, restore_db as _restore_db
    from datetime import date as _date

    st.markdown("")
    with st.expander("Backup & Restore"):
        # ── Backup ────────────────────────────────────────────────────────
        st.markdown("**Backup**")
        try:
            _bk_bytes = _backup_db()
            st.download_button(
                label="Download backup (.db)",
                data=_bk_bytes,
                file_name=f"duty_cockpit_{_date.today().isoformat()}.db",
                mime="application/octet-stream",
                key="sf_backup_dl",
                width="stretch",
            )
        except FileNotFoundError:
            st.caption("No database yet — run an analysis first.")
        except Exception as _e:
            st.error(f"Backup error: {_e}")

        # ── Restore ───────────────────────────────────────────────────────
        st.markdown("**Restore**")
        st.caption("The current database is saved automatically before any restore.")
        _uploaded = st.file_uploader(
            "Upload .db backup",
            type=["db"],
            key="sf_restore_upload",
            label_visibility="collapsed",
        )
        if _uploaded is not None:
            if st.button(
                "Restore this backup",
                key="sf_restore_confirm",
                type="primary",
                width="stretch",
            ):
                try:
                    _restore_db(_uploaded.read())
                    st.success("Restored successfully. Reloading...")
                    st.rerun()
                except ValueError as _ve:
                    st.error(str(_ve))
                except Exception as _e:
                    st.error(f"Restore failed: {_e}")


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
        _render_sidebar_backup()
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
    _render_sidebar_backup()


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


_STRIPE_BG = "background-color: rgba(255,255,255,0.09);"


def _stripe(df_or_sty):
    """Alternating row stripe for st.dataframe display."""
    sty = df_or_sty.style if isinstance(df_or_sty, pd.DataFrame) else df_or_sty
    return sty.apply(
        lambda row: [_STRIPE_BG if row.name % 2 == 0 else "" for _ in row],
        axis=1,
    )


def _auto_col_cfg(df: pd.DataFrame) -> dict:
    """Auto NumberColumn configs for all float columns: %.1f%% for rate columns, %.0f for others."""
    cfg = {}
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            fmt = "%.1f%%" if "rate" in str(col).lower() else "%.0f"
            cfg[col] = st.column_config.NumberColumn(format=fmt)
    return cfg


def _pre_fmt_num(v: Any, is_rate: bool = False, is_currency: bool = True) -> str:
    """Format a numeric value as display string: rate → '12.3%', currency → '1,234 €', plain → '1,234'."""
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if pd.isna(f):
        return ""
    if is_rate:
        return f"{f:.1f}%"
    if is_currency:
        return f"{f:,.0f} €"
    return f"{f:,.0f}"


def _safe_str(value: Any, default: str = "") -> str:
    """
    Return a clean string for a possibly-missing value.
    Handles pd.NA, NaN, None and the string literals 'nan' / '<NA>' / 'None'.

    Use this instead of `str(x or "")` when reading from DataFrames whose
    string columns are now pandas 'string' dtype (which uses pd.NA — and
    `pd.NA or ""` raises TypeError).
    """
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    s = str(value).strip()
    if s.lower() in ("nan", "<na>", "none"):
        return default
    return s


def _render_plotly(fig, label: str = "", **kwargs) -> None:
    """
    Render a Plotly chart with accessibility support.

    - If `label` is provided AND the figure has no visible title set, embeds the
      label as an invisible SVG <title> for screen readers (off-canvas, size 1).
    - If the figure already has a title (e.g. fig.update_layout(title="…")),
      leaves it untouched — the existing title already serves as the a11y label.
    - Hides the Plotly modebar by default for a cleaner UI.
    - Forwards remaining kwargs to st.plotly_chart.
    """
    existing_title = (fig.layout.title.text or "") if fig.layout.title else ""
    if label and not existing_title:
        fig.update_layout(
            title=dict(
                text=label,
                x=0, y=0,
                pad=dict(t=0, b=0, l=0, r=0),
                font=dict(size=1, color="rgba(0,0,0,0)"),
            )
        )
    kwargs.setdefault("config", {"displayModeBar": False})
    kwargs.pop("use_container_width", None)   # drop deprecated param if caller passed it
    kwargs.setdefault("width", "stretch")
    st.plotly_chart(fig, **kwargs)


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
def _render_kpi_cards(
    kpis: List[Dict[str, Any]],
    compact: bool = False,
    cols: Optional[int] = None,
) -> None:
    """
    Each KPI dict supports:
      - label (str)
      - value (str)
      - sub (str) optional
      - icon (str) optional (emoji or short text)
      - delta (str) optional (badge text)
      - delta_kind: "good" | "bad" | "neutral" (optional)
    compact=True: smaller cards; defaults to one column per KPI in a single row.
    cols: override the column count (CSS variable --kpi-cols). If None: 4 for normal, len(kpis) for compact.
    """
    # All styling lives in .streamlit/custom.css (loaded once via load_custom_css()).
    if compact:
        n = cols if cols is not None else len(kpis)
        parts = [f'<div class="kpi-grid-compact" style="--kpi-cols: {n};">']
        card_class = "kpi-card-compact"
    else:
        style = f' style="--kpi-cols: {cols};"' if cols is not None else ""
        parts = [f'<div class="kpi-grid"{style}>']
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
def _fmt_human(x: Any, decimals: int = 0) -> str:
    """Format numbers with k/M abbreviation for KPI display."""
    try:
        if x is None:
            return "N/A"
        v = float(x)
    except Exception:
        return "N/A"
    abs_v = abs(v)
    sign = "-" if v < 0 else ""
    if abs_v >= 1_000_000:
        return f"{sign}{abs_v / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"{sign}{abs_v / 1_000:.1f}k"
    if decimals == 0:
        return f"{sign}{int(round(abs_v))}"
    return f"{sign}{abs_v:.{decimals}f}"


def _fmt_num(x: Any, decimals: int = 0) -> str:
    """Format numbers with k/M abbreviation for KPI display."""
    try:
        if x is None:
            return "N/A"
        v = float(x)
    except Exception:
        return "N/A"
    abs_v = abs(v)
    sign = "-" if v < 0 else ""
    if abs_v >= 1_000_000:
        return f"{sign}{abs_v / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"{sign}{abs_v / 1_000:.1f}k"
    return f"{sign}{int(round(abs_v))}"


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


def _strip_date_cols(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """Return a copy of df with time stripped from the given columns (keep YYYY-MM-DD only)."""
    df = df.copy()
    _NA = {"nan", "None", "NaT", "nat", "none", ""}
    for c in cols:
        if c not in df.columns:
            continue
        def _trim(v, _na=_NA):
            s = str(v) if v is not None else ""
            if s in _na:
                return ""
            return s[:10] if s[:4].isdigit() else s
        df[c] = df[c].apply(_trim)
    return df
