from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.ui_shared import (
    ACCENTURE_PURPLE_CORE,
    ACCENTURE_PURPLE_DARK,
    ACCENTURE_PURPLE_DARKEST,
    ACCENTURE_PURPLE_LIGHT,
    ACCENTURE_PURPLE_LIGHTEST,
    _apply_sidebar_filters,
    _fmt_int,
    _fmt_num,
    _pre_fmt_num,
    _render_empty_state,
    _render_kpi_cards,
    _render_plotly,
    _stripe,
    _strip_date_cols,
)


# -----------------------------------------------------------------------------
# Results tab (filters + KPI cards)
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


def render_tab_resultados(df_merged: Optional[pd.DataFrame]) -> None:
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
        if _drill_coo and "coo" in df.columns:
            df = df[df["coo"].isin(_drill_coo)]
        if _drill_coi and "coi" in df.columns:
            df = df[df["coi"].isin(_drill_coi)]
        if _drill_hs and "hs code" in df.columns:
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
    _render_kpi_cards(cols=6, kpis=[
        {"label": "# Transactions", "value": _fmt_int(len(df)),          "sub": "Filtered rows"},
        {"label": "# COI",          "value": _fmt_int(n_coi),            "sub": "Countries of import"},
        {"label": "# COO",          "value": _fmt_int(n_coo),            "sub": "Countries of origin"},
        {"label": "Customs Value",  "value": f"{_fmt_num(customs_s)} €", "sub": "Declared import value"},
        {"label": "Duty Exposure",  "value": f"{_fmt_num(def_s)} €",     "sub": "Sum of default duties"},
        {"label": "Duty Paid",      "value": f"{_fmt_num(paid_s)} €",    "sub": "Total duties paid"},
    ])

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
        st.markdown("**Customs Value by COI**")
        if "coi" in df.columns and customs_s > 0:
            _grp = (
                df.groupby("coi")["customs value"]
                .apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum())
                .reset_index()
                .rename(columns={"customs value": "val"})
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
            _render_plotly(_fig, label="Customs Value by COI")
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
                **({"threshold": {
                    "line": {"color": "#FFD700", "width": 3},
                    "thickness": 0.75,
                    "value": min_s,
                }} if min_s > 0 else {}),
            },
            number={"suffix": " €", "valueformat": ",.0f",
                    "font": {"size": 26, "color": "white"}},
        ))
        _fig.update_layout(
            height=240, paper_bgcolor="rgba(255,255,255,0.06)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "white"}, margin=dict(l=20, r=20, t=20, b=10),
        )
        _render_plotly(_fig, label="Duty Exposure gauge")
        st.caption(f"Paid: {_fmt_num(paid_s)} € / Min: {_fmt_num(min_s)} € / Exposure: {_fmt_num(def_s)} €")

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
            _render_plotly(_fig, label="Duties Paid by COI")
        else:
            st.info("No duty paid data.")

    # ── Results table ──────────────────────────────────────────────────────
    st.markdown("### Results table")
    _edit_mode = st.session_state.get("db_edit_mode", "view")
    _HIDE_RES = {"saved_at", "customs_value_original", "ref_date"}
    _df_res = df[[c for c in df.columns if c not in _HIDE_RES]].copy()
    _df_res = _strip_date_cols(_df_res, ["date", "Input Date", "ref_date"])
    if "duty paid" in _df_res.columns and "customs value" in _df_res.columns:
        _cv_r = pd.to_numeric(_df_res["customs value"], errors="coerce")
        _dp_r = pd.to_numeric(_df_res["duty paid"], errors="coerce")
        _df_res.insert(
            _df_res.columns.get_loc("duty paid") + 1,
            "Applied Rate",
            (_dp_r / _cv_r.where(_cv_r > 0) * 100).round(4),
        )
    if _edit_mode == "view":
        _df_res_disp = _df_res.copy()
        for _rc in ["Default Duty Rate", "Min Duty Rate"]:
            if _rc in _df_res_disp.columns and pd.api.types.is_float_dtype(_df_res_disp[_rc]):
                _df_res_disp[_rc] = _df_res_disp[_rc] * 100
        for _rc in _df_res_disp.columns:
            if pd.api.types.is_float_dtype(_df_res_disp[_rc]):
                _ir = "rate" in _rc.lower()
                _ic = "weight" not in _rc.lower()
                _df_res_disp[_rc] = _df_res_disp[_rc].apply(lambda v, _x=_ir, _c=_ic: _pre_fmt_num(v, _x, _c))
        _res_col_cfg = {
            c: cfg for c, cfg in {
                "customs value": st.column_config.TextColumn(
                    "customs value",
                    help="Declared customs value of the goods for this transaction. Used as the taxable base for duty calculation.",
                ),
                "duty paid": st.column_config.TextColumn(
                    "duty paid",
                    help="Total customs duties actually paid for this transaction.",
                ),
                "Applied Rate": st.column_config.TextColumn(
                    "Applied Rate",
                    help="Effective duty rate for this transaction. Formula: Duty Paid ÷ Customs Value × 100.",
                ),
                "Default Duty Rate": st.column_config.TextColumn(
                    "Default Duty Rate",
                    help="Standard MFN (Most Favoured Nation) tariff rate for this HS Code, without any preferential program.",
                ),
                "Default Duties": st.column_config.TextColumn(
                    "Default Duties",
                    help="Theoretical duties at the standard MFN rate. Formula: Customs Value × Default Duty Rate.",
                ),
                "Default Duty Program": st.column_config.TextColumn(
                    "Default Duty Program",
                    help="Standard tariff program applied when no preferential agreement (FTA) is used.",
                ),
                "Default Duty Program Description": st.column_config.TextColumn(
                    "Default Duty Program Description",
                    help="Full description of the standard (non-preferential) tariff program.",
                ),
                "Min Duty Rate": st.column_config.TextColumn(
                    "Min Duty Rate",
                    help="Preferential duty rate under the applicable FTA or program for this trade lane.",
                ),
                "Minimum Duties": st.column_config.TextColumn(
                    "Minimum Duties",
                    help="Duties at the preferential FTA rate. Formula: Customs Value × Min Duty Rate.",
                ),
                "Min Duty Program": st.column_config.TextColumn(
                    "Min Duty Program",
                    help="Code or name of the preferential tariff program (e.g. FTA) that yields the minimum duty rate.",
                ),
                "Min Duty Program Description": st.column_config.TextColumn(
                    "Min Duty Program Description",
                    help="Full description of the preferential tariff program.",
                ),
            }.items()
            if c in _df_res_disp.columns
        }
        st.dataframe(_stripe(_df_res_disp), width='stretch', column_config=_res_col_cfg or None)
    render_db_editor_section(df_merged=df_merged, df_filtered=df)


# -----------------------------------------------------------------------------
# DB editor section (inline + Excel corrections)
# -----------------------------------------------------------------------------
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
            ("customs value", "%.0f"), ("weight", "%.0f"), ("duty paid", "%.0f"),
        ]:
            if num_col in base_df.columns:
                col_cfg[num_col] = st.column_config.NumberColumn(num_col, format=fmt)

        edited_df = st.data_editor(
            base_df,
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
                    _stripe(upd_preview), width='stretch', hide_index=True
                )
            else:
                st.info("No changes detected in editable columns.")

            if deletes:
                st.markdown(f"**{len(deletes)} row(s) marked for deletion:**")
                if not del_preview.empty:
                    st.dataframe(
                        _stripe(del_preview), width='stretch', hide_index=True
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
