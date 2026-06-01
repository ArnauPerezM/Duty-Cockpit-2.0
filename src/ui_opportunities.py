from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ui_shared import (
    ACCENTURE_PURPLE_CORE,
    ACCENTURE_PURPLE_DARK,
    ACCENTURE_PURPLE_DARKEST,
    ACCENTURE_PURPLE_LIGHT,
    ACCENTURE_PURPLE_LIGHTEST,
    _OPP_CHART_CAP,
    _apply_sidebar_filters,
    _fmt_int,
    _fmt_num,
    _pre_fmt_num,
    _render_empty_state,
    _render_kpi_cards,
    _render_plotly,
    _safe_str,
    _stripe,
)


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
                    labels={"_overpaid": "Overpaid Duties (€)", prod_col: "Product"},
                )
                fig.update_layout(**_CHART_LAYOUT)
                fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f} €<extra></extra>")
                _render_plotly(fig, label="Overpaid Duties by Product")
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
                    grp.groupby("coi")["_overpaid"].sum()
                    .reset_index()
                    .sort_values("_overpaid", ascending=False)["coi"]
                    .tolist()
                )
            else:
                grp = (
                    df.groupby("coi")["_overpaid"].sum()
                    .reset_index()
                    .pipe(lambda d: d[d["_overpaid"] > 0])
                    .sort_values("_overpaid", ascending=False)
                )
                order = grp["coi"].tolist()
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
                    labels={"_overpaid": "Overpaid Duties (€)", "coi": "COI"},
                )
                fig.update_layout(**_CHART_LAYOUT)
                fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,.0f} €<extra></extra>")
                _render_plotly(fig, label="Overpaid Duties by COI")
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
                .head(_OPP_CHART_CAP)
                .rename(columns={"coi": "COI", "coo": "COO", "_overpaid": "Overpaid Duties"})
            )
            if not lane.empty:
                _lane_disp = lane.copy()
                if "Overpaid Duties" in _lane_disp.columns:
                    _lane_disp["Overpaid Duties"] = _lane_disp["Overpaid Duties"].apply(
                        lambda v: _pre_fmt_num(v, False)
                    )
                st.dataframe(
                    _stripe(_lane_disp),
                    hide_index=True,
                    width='stretch',
                    height=320,
                )
            else:
                st.info("No overpaid duties found.")
        else:
            st.info("No COI/COO columns in data.")

    # 4 — Overpaid Duties by Program
    _prog_chart_col = next(
        (c for c in ["Min Duty Program", "min duty program"] if c in df.columns),
        prog_col,
    )
    with ch4:
        st.markdown("**Overpaid Duties by Program**")
        if _prog_chart_col:
            grp = (
                df.groupby(_prog_chart_col)["_overpaid"].sum()
                .reset_index()
                .pipe(lambda d: d[d["_overpaid"] > 0])
                .sort_values("_overpaid", ascending=True)
                .tail(10)
            )
            if not grp.empty:
                def _wrap(label: str, width: int = 20) -> str:
                    words = str(label).split()
                    lines, cur = [], []
                    for w in words:
                        if cur and sum(len(x) for x in cur) + len(cur) + len(w) > width:
                            lines.append(" ".join(cur))
                            cur = [w]
                        else:
                            cur.append(w)
                    if cur:
                        lines.append(" ".join(cur))
                    return "<br>".join(lines)

                grp["_label"] = grp[_prog_chart_col].apply(_wrap)
                fig = px.bar(
                    grp, x="_overpaid", y="_label", orientation="h",
                    color_discrete_sequence=[ACCENTURE_PURPLE_LIGHT],
                    template="plotly_dark",
                    labels={"_overpaid": "Overpaid Duties (€)", "_label": "Min Duty Program"},
                )
                fig.update_layout(**_CHART_LAYOUT)
                fig.update_traces(
                    hovertemplate="<b>%{customdata[0]}</b><br>%{x:,.0f} €<extra></extra>",
                    customdata=grp[[_prog_chart_col]].values,
                )
                _render_plotly(fig, label="Overpaid Duties by Program")
            else:
                st.info("No overpaid duties found.")
        else:
            st.info("No program column in data.")

    # ── Build initiative lookup (coo, coi, hs_code) → status list ────────────
    _ini_lookup: Dict[tuple, List[str]] = {}
    if df_initiatives is not None and not df_initiatives.empty:
        for _, _ir in df_initiatives.iterrows():
            _k = (
                _safe_str(_ir.get("coo")).upper(),
                _safe_str(_ir.get("coi")).upper(),
                _safe_str(_ir.get("hs_code")).upper(),
            )
            _ini_lookup.setdefault(_k, []).append(_safe_str(_ir.get("status")))

    def _ini_label(row) -> str:
        k = (
            _safe_str(row.get("coo")).upper(),
            _safe_str(row.get("coi")).upper(),
            _safe_str(row.get("hs code")).upper(),
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
    for extra in ["Default Duty Rate", "Min Duty Rate", "Min Duty Program"]:
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
        grouped["Duty Paid"] > grouped["Default Duties"] * 1.10
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

    # ── Filter: exclude rows that already have an initiative (default ON) ──────
    _has_ini_mask = grouped["Initiative"].str.len() > 0
    _n_with_ini   = int(_has_ini_mask.sum())
    _show_ini = st.checkbox(
        f"Show opportunities with existing initiatives ({_n_with_ini})",
        value=False,
        key="opp_show_with_ini",
        help="By default, opportunities that already have an initiative in any status are hidden.",
    )
    if not _show_ini:
        grouped = grouped[~_has_ini_mask].copy()
    # Ensure FTA boolean flags appear before the FTA date columns
    _fta_bool_cols = [c for c in ["FTA Applied Previously", "FTA Applied Afterwards"] if c in grouped.columns]
    _fta_date_cols = [c for c in ["First FTA Rate Paid", "Last FTA Rate Paid"] if c in grouped.columns]
    if _fta_bool_cols and _fta_date_cols:
        _other_cols = [c for c in grouped.columns if c not in _fta_bool_cols and c not in _fta_date_cols]
        _insert_at = _other_cols.index(_fta_date_cols[0]) if _fta_date_cols[0] in _other_cols else len(_other_cols)
        _ordered = _other_cols[:_insert_at] + _fta_bool_cols + _fta_date_cols + _other_cols[_insert_at:]
        grouped = grouped[_ordered]

    if "Duty Paid" in grouped.columns and "Customs Value" in grouped.columns:
        _cv_g = pd.to_numeric(grouped["Customs Value"], errors="coerce")
        _dp_g = pd.to_numeric(grouped["Duty Paid"], errors="coerce")
        grouped.insert(
            grouped.columns.get_loc("Duty Paid") + 1,
            "Applied Rate",
            (_dp_g / _cv_g.where(_cv_g > 0) * 100).round(4),
        )

    # Highlight True cells in boolean columns with a light red background
    _bool_highlight = [
        c for c in ["Duties Paid > Default Duties", "FTA Applied Previously", "FTA Applied Afterwards"]
        if c in grouped.columns
    ]

    def _bool_style(col):
        if col.name in _bool_highlight:
            return col.map(lambda v: "background-color: rgba(210,40,40,0.65); color: #fff;" if v else "")
        return [""] * len(col)

    # Pre-format numeric columns for display (thousands separator + € / %)
    _grouped_disp = grouped.copy()
    for _mc in ["Customs Value", "Duty Paid", "Default Duties", "Duty To-Be Paid", "Overpaid Duties"]:
        if _mc in _grouped_disp.columns:
            _grouped_disp[_mc] = _grouped_disp[_mc].apply(lambda v: _pre_fmt_num(v, False))
    for _rc in ["Default Duty Rate", "Min Duty Rate"]:
        if _rc in _grouped_disp.columns and pd.api.types.is_float_dtype(_grouped_disp[_rc]):
            _grouped_disp[_rc] = _grouped_disp[_rc] * 100
    for _rc in ["Applied Rate", "Default Duty Rate", "Min Duty Rate"]:
        if _rc in _grouped_disp.columns:
            _grouped_disp[_rc] = _grouped_disp[_rc].apply(lambda v: _pre_fmt_num(v, True))

    money_cfg = {
        "Initiative": st.column_config.TextColumn(
            "Initiative", disabled=True, width="medium",
            help="Existing initiative status for this trade lane (e.g. Identified, Validated). Blank if no initiative has been created yet.",
        ),
        "material number": st.column_config.TextColumn("Material Number", disabled=True),
        **({
            "Customs Value": st.column_config.TextColumn(
                "Customs Value", disabled=True,
                help="Sum of the declared customs value of the goods across all transactions in this group. Used as the taxable base for duty calculation.",
            ),
        } if "Customs Value" in _grouped_disp.columns else {}),
        **({
            "Duty Paid": st.column_config.TextColumn(
                "Duty Paid", disabled=True,
                help="Total customs duties actually paid across all transactions in this group.",
            ),
        } if "Duty Paid" in _grouped_disp.columns else {}),
        **({
            "Default Duties": st.column_config.TextColumn(
                "Default Duties", disabled=True,
                help="Theoretical duties calculated at the standard (non-preferential / MFN) rate. Formula: Customs Value × Default Duty Rate.",
            ),
        } if "Default Duties" in _grouped_disp.columns else {}),
        **({
            "Duty To-Be Paid": st.column_config.TextColumn(
                "Duty To-Be Paid", disabled=True,
                help="Minimum duties applicable under the preferential program (FTA). Sum across transactions. Formula: Customs Value × Min Duty Rate.",
            ),
        } if "Duty To-Be Paid" in _grouped_disp.columns else {}),
        **({
            "Overpaid Duties": st.column_config.TextColumn(
                "Overpaid Duties", disabled=True,
                help="Estimated over-payment vs. the FTA minimum. Formula: Duty Paid − Duty To-Be Paid. Positive values indicate a savings opportunity.",
            ),
        } if "Overpaid Duties" in _grouped_disp.columns else {}),
        **({
            "Applied Rate": st.column_config.TextColumn(
                "Applied Rate", disabled=True,
                help="Effective duty rate actually paid. Formula: Duty Paid ÷ Customs Value × 100.",
            ),
        } if "Applied Rate" in _grouped_disp.columns else {}),
        **({
            "Default Duty Rate": st.column_config.TextColumn(
                "Default Duty Rate", disabled=True,
                help="Standard MFN (Most Favoured Nation) tariff rate for this HS Code, without any preferential program.",
            ),
        } if "Default Duty Rate" in _grouped_disp.columns else {}),
        **({
            "Min Duty Rate": st.column_config.TextColumn(
                "Min Duty Rate", disabled=True,
                help="Preferential duty rate under the applicable FTA or program for this trade lane.",
            ),
        } if "Min Duty Rate" in _grouped_disp.columns else {}),
        **({
            "Min Duty Program": st.column_config.TextColumn(
                "Min Duty Program", disabled=True,
                help="Code or name of the preferential tariff program (e.g. FTA) that yields the minimum duty rate.",
            ),
        } if "Min Duty Program" in _grouped_disp.columns else {}),
        **({
            "Duties Paid > Default Duties": st.column_config.CheckboxColumn(
                "Duties Paid > Default Duties", disabled=True,
                help="True when Duty Paid exceeds Default Duties by more than 10%. May indicate a data issue or an incorrect tariff classification.",
            ),
        } if "Duties Paid > Default Duties" in grouped.columns else {}),
        **({
            "FTA Applied Previously": st.column_config.CheckboxColumn(
                "FTA Applied Previously", disabled=True,
                help="True when the FTA rate was applied in at least one transaction before the earliest overpayment. Suggests the program was known but not consistently applied.",
            ),
        } if "FTA Applied Previously" in grouped.columns else {}),
        **({
            "FTA Applied Afterwards": st.column_config.CheckboxColumn(
                "FTA Applied Afterwards", disabled=True,
                help="True when the FTA rate was applied after the last overpayment. Indicates the issue has since been corrected.",
            ),
        } if "FTA Applied Afterwards" in grouped.columns else {}),
        **({
            "First FTA Rate Paid": st.column_config.DateColumn(
                "First FTA Rate Paid", format="YYYY-MM-DD",
                help="Date of the earliest transaction where the FTA (minimum duty) rate was applied.",
            ),
        } if "First FTA Rate Paid" in grouped.columns else {}),
        **({
            "Last FTA Rate Paid": st.column_config.DateColumn(
                "Last FTA Rate Paid", format="YYYY-MM-DD",
                help="Date of the most recent transaction where the FTA rate was applied.",
            ),
        } if "Last FTA Rate Paid" in grouped.columns else {}),
    }

    opp_event = st.dataframe(
        _stripe(_grouped_disp).apply(_bool_style),
        width='stretch',
        column_config=money_cfg,
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
        st.rerun()

    if st.session_state.get("opp_drill_results"):
        st.info("Drill-down active — click the **Results** tab to view filtered transactions.", icon="→")

    if create_clicked and n_new > 0:
        from src.db import save_initiatives as _save_init
        new_rows = sel_rows_all[~already_exist_mask].drop(columns=["Initiative"], errors="ignore")
        records = []
        for _, r in new_rows.iterrows():
            ps = float(r.get("Overpaid Duties", 0) or 0)
            records.append({
                "coo":                      _safe_str(r.get("coo")),
                "coi":                      _safe_str(r.get("coi")),
                "hs_code":                  _safe_str(r.get("hs code")),
                "material_number":          _safe_str(r.get("material number")),
                "customs_value":            float(r.get("Customs Value", 0) or 0),
                "duty_paid":                float(r.get("Duty Paid", 0) or 0),
                "default_duties":           float(r.get("Default Duties", 0) or 0),
                "min_duties":               float(r.get("Duty To-Be Paid", 0) or 0),
                "min_duty_rate":            float(r.get("Min Duty Rate", 0) or 0),
                "min_duty_program":         _safe_str(r.get("Min Duty Program")),
                "potential_savings":        ps,
                "annual_savings_est":       ps,
                "savings_realized":         0.0,
                "reimbursements":           0.0,
                "potential_reimbursements": 0.0,
                "status":                   "Identified",
                "comments":                 "",
                "program_description":      _safe_str(r.get(prog_col)) if prog_col else "",
            })
        saved = _save_init(records)
        st.success(f"{saved} initiative(s) created successfully. Check the Initiatives tab.")
        st.rerun()
