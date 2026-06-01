from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from src.ui_shared import (
    _auto_col_cfg,
    _fmt_int,
    _fmt_pct,
    _render_kpi_cards,
    _stripe,
    _strip_date_cols,
)


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
        _rh_disp = _strip_date_cols(rh[display_cols], ["started_at", "ref_date"])
        st.dataframe(_stripe(_rh_disp), width='stretch', column_config=_auto_col_cfg(_rh_disp))
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
    st.dataframe(_stripe(_dl), width='stretch', column_config=_auto_col_cfg(_dl))
