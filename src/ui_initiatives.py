from __future__ import annotations

import html as _html
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
    _fmt_num,
    _pre_fmt_num,
    _render_empty_state,
    _render_kpi_cards,
    _render_plotly,
    _safe_str,
    _stripe,
    _strip_date_cols,
)


_INITIATIVE_STATUS_OPTIONS = ["Identified", "Validated", "Discarded", "Completed"]

_AUTO_COLS = [
    "_est_annual_cv", "_auto_annual_savings", "_total_potential_savings",
    "_post_cv", "_post_dp", "_realized_avg_rate", "_auto_savings_realized",
]


@st.cache_data(ttl=60, show_spinner=False)
def _compute_initiative_metrics(df_ini: pd.DataFrame, df_tx_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Cross-reference initiatives with transactions to compute PRE/POST metrics.
    Returns a DataFrame with one row per initiative id, holding _AUTO_COLS + _mdp.

    Cached: re-runs only when df_ini or df_tx_raw change. DB writes elsewhere
    call st.cache_data.clear() which invalidates this cache too.
    """
    base_cols = _AUTO_COLS + ["_mdp"]
    if df_ini is None or df_ini.empty:
        return pd.DataFrame(columns=["id"] + base_cols)

    empty_row = {c: float("nan") for c in _AUTO_COLS}
    empty_row["_mdp"] = ""
    empty = pd.DataFrame([{**empty_row, "id": rid} for rid in df_ini["id"]])

    if df_tx_raw is None or df_tx_raw.empty:
        return empty

    _needed_base = ["date", "coo", "coi", "hs code", "material number",
                    "customs value", "duty paid", "Minimum Duties"]
    if not all(c in df_tx_raw.columns for c in _needed_base):
        return empty

    _has_mdr = "Min Duty Rate" in df_tx_raw.columns
    _has_mdp = "Min Duty Program" in df_tx_raw.columns
    _cols_to_load = _needed_base[:]
    if _has_mdr:
        _cols_to_load.append("Min Duty Rate")
    if _has_mdp:
        _cols_to_load.append("Min Duty Program")

    _tx = df_tx_raw[_cols_to_load].copy()
    _base_names = ["_d", "_coo", "_coi", "_hs", "_mat", "_cv", "_dp", "_md"]
    if _has_mdr:
        _base_names.append("_mr")
    if _has_mdp:
        _base_names.append("_mp")
    _tx.columns = _base_names
    if not _has_mdr:
        _tx["_mr"] = float("nan")
    if not _has_mdp:
        _tx["_mp"] = ""
    _tx["_coo"] = _tx["_coo"].fillna("").astype(str).str.strip().str.upper()
    _tx["_coi"] = _tx["_coi"].fillna("").astype(str).str.strip().str.upper()
    _tx["_hs"]  = _tx["_hs"].fillna("").astype(str).str.strip()
    _tx["_mat"] = _tx["_mat"].fillna("").astype(str).str.strip()
    _tx["_dp"]  = pd.to_numeric(_tx["_dp"], errors="coerce").fillna(0)
    _tx["_cv"]  = pd.to_numeric(_tx["_cv"], errors="coerce").fillna(0)
    _tx["_mr"]  = pd.to_numeric(_tx["_mr"], errors="coerce")
    _tx["_mp"]  = _tx["_mp"].fillna("").astype(str).str.strip()
    _tx["_dp_"] = pd.to_datetime(_tx["_d"], errors="coerce")

    _ini_keys = df_ini[[
        "id", "coo", "coi", "hs_code", "material_number", "min_duty_rate",
        "customs_value", "duty_paid", "min_duties",
        "status", "implementation_date", "potential_reimbursements",
    ]].copy()
    _ini_keys["_icoo"] = _ini_keys["coo"].fillna("").astype(str).str.strip().str.upper()
    _ini_keys["_icoi"] = _ini_keys["coi"].fillna("").astype(str).str.strip().str.upper()
    _ini_keys["_ihs"]  = _ini_keys["hs_code"].fillna("").astype(str).str.strip()
    _ini_keys["_imat"] = _ini_keys["material_number"].fillna("").astype(str).str.strip()
    _ini_keys["_imr"]  = pd.to_numeric(_ini_keys["min_duty_rate"], errors="coerce").fillna(0.0)
    _icv_s             = pd.to_numeric(_ini_keys["customs_value"], errors="coerce").fillna(0.0)
    _idp_s             = pd.to_numeric(_ini_keys["duty_paid"],     errors="coerce").fillna(0.0)
    _imd_s             = pd.to_numeric(_ini_keys["min_duties"],    errors="coerce").fillna(0.0)
    _ini_keys["_ipr"]  = pd.to_numeric(_ini_keys["potential_reimbursements"], errors="coerce").fillna(0.0)
    _ini_keys["_ar"]   = (_idp_s / _icv_s.where(_icv_s > 0)).fillna(0.0)
    _ini_keys["_tr"]   = (_imd_s / _icv_s.where(_icv_s > 0)).fillna(0.0)
    _ini_keys["_impl_dt"] = pd.to_datetime(
        _ini_keys["implementation_date"].fillna("").astype(str).str.strip(),
        format="mixed",
        errors="coerce",
    )

    _paired = _ini_keys.merge(
        _tx[["_coo", "_coi", "_hs", "_mat", "_mr", "_cv", "_dp", "_mp", "_dp_"]],
        left_on=["_icoo", "_icoi", "_ihs"],
        right_on=["_coo", "_coi", "_hs"],
        how="left",
    )

    _has_mat_ini = _paired["_imat"] != ""
    _paired = _paired[~_has_mat_ini | (_paired["_mat"] == _paired["_imat"])].copy()

    if _has_mdr:
        _has_mdr_ini = _paired["_imr"] != 0
        _paired = _paired[~_has_mdr_ini | (_paired["_mr"] == _paired["_imr"])].copy()

    _paired["_end_dt"] = _paired["_impl_dt"] + pd.Timedelta(days=365)
    _paired["_is_post"] = (
        _paired["status"].isin(["Completed", "Closed"])
        & _paired["_impl_dt"].notna()
        & _paired["_dp_"].notna()
        & (_paired["_dp_"] > _paired["_impl_dt"])
        & (_paired["_dp_"] < _paired["_end_dt"])
    )

    _dated = _paired[_paired["_dp_"].notna()]
    if not _dated.empty:
        _cv_sum  = _dated.groupby("id")["_cv"].sum()
        _dp_span = _dated.groupby("id")["_dp_"].agg(lambda s: (s.max() - s.min()).days)
        _ecv_df = pd.DataFrame({"_cv_sum": _cv_sum, "_span": _dp_span})
        _ecv_df["_est_annual_cv"] = _ecv_df.apply(
            lambda r: round(r["_cv_sum"] / r["_span"] * 365, 2)
            if r["_span"] > 1 else r["_cv_sum"],
            axis=1,
        ).fillna(0.0)
    else:
        _ecv_df = pd.DataFrame(columns=["_est_annual_cv"])

    _mp_first = (
        _paired[_paired["_mp"].notna() & (_paired["_mp"] != "")]
        .groupby("id")["_mp"].first()
        .rename("_mdp")
    )
    _pre = _ecv_df[["_est_annual_cv"]].join(_mp_first, how="outer")
    _pre["_est_annual_cv"] = _pre["_est_annual_cv"].fillna(0.0)
    _pre["_mdp"]           = _pre["_mdp"].fillna("")

    _ini_rates = _ini_keys.set_index("id")[["_ar", "_tr", "_ipr"]]
    _pre = _pre.join(_ini_rates)
    _pre["_auto_annual_savings"]     = (_pre["_est_annual_cv"] * (_pre["_ar"] - _pre["_tr"])).round(2)
    _pre["_total_potential_savings"] = (
        _pre["_auto_annual_savings"].clip(lower=0) + _pre["_ipr"]
    ).round(2)

    _post_rows = _paired[_paired["_is_post"]]
    if not _post_rows.empty:
        _post = _post_rows.groupby("id").agg(
            _post_cv=("_cv", "sum"),
            _post_dp=("_dp", "sum"),
        ).round(2)
        _post = _post.join(_ini_rates[["_ar"]])
        _post["_realized_avg_rate"] = (
            _post["_post_dp"] / _post["_post_cv"].where(_post["_post_cv"] > 0) * 100
        ).fillna(0.0).round(4)
        _post["_auto_savings_realized"] = (
            _post["_post_cv"] * _post["_ar"] - _post["_post_dp"]
        ).clip(lower=0).round(2)
    else:
        _post = pd.DataFrame(
            columns=["_post_cv", "_post_dp", "_realized_avg_rate", "_auto_savings_realized"]
        )

    auto_df = (
        _pre[["_est_annual_cv", "_auto_annual_savings", "_total_potential_savings", "_mdp"]]
        .join(
            _post[["_post_cv", "_post_dp", "_realized_avg_rate", "_auto_savings_realized"]],
            how="left",
        )
        .fillna({
            "_post_cv": 0.0, "_post_dp": 0.0,
            "_realized_avg_rate": 0.0, "_auto_savings_realized": 0.0,
        })
    )
    auto_df["_mdp"] = auto_df["_mdp"].fillna("")
    return auto_df.reset_index()


# -----------------------------------------------------------------------------
# Initiatives tab
# -----------------------------------------------------------------------------
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

    # Strip time component — keep only YYYY-MM-DD
    def _date_only(v: Any) -> str:
        s = str(v) if v is not None else ""
        return s[:10] if s[:4].isdigit() else ("" if s in ("nan", "None", "NaT") else s)
    df = _strip_date_cols(df, ["created_at", "start_date", "implementation_date"])
    if _sf_coo and _sf_coo != "All" and "coo" in df.columns:
        df = df[df["coo"].astype(str).str.strip() == _sf_coo]
    if _sf_coi and _sf_coi != "All" and "coi" in df.columns:
        df = df[df["coi"].astype(str).str.strip() == _sf_coi]

    # ── Group A: computed display columns ─────────────────────────────────────
    def _fn(col): return pd.to_numeric(df[col], errors="coerce").fillna(0.0) if col in df.columns else pd.Series([0.0] * len(df), index=df.index)

    _cv   = _fn("customs_value")
    _dp   = _fn("duty_paid")
    _md   = _fn("min_duties")
    _rei  = _fn("reimbursements")

    df = df.copy()
    df["_asis_rate"]        = (_dp / _cv.where(_cv > 0) * 100).round(4)
    df["_tobe_rate"]        = (_md / _cv.where(_cv > 0) * 100).round(4)
    df["_initial_overpaid"] = (_dp - _md).round(2)

    def _end_date(row):
        if str(row.get("status", "")) in ("Completed", "Closed"):
            impl = _safe_str(row.get("implementation_date"))
            if impl:
                try:
                    return (pd.to_datetime(impl) + pd.Timedelta(days=365)).strftime("%Y-%m-%d")
                except Exception:
                    pass
        return ""

    df["_end_date"]         = df.apply(_end_date, axis=1)
    df["_final_overpaid"]   = (df["_initial_overpaid"] - _rei).round(2)

    # ── Groups C + D: cross-reference with stored transactions (cached) ────────
    try:
        from src.db import load_merged_results as _load_tx
        _df_tx_raw = _load_tx()
        _auto_df = _compute_initiative_metrics(df, _df_tx_raw)
        df = df.merge(_auto_df, on="id", how="left")

        # Back-fill min_duty_program in DB for initiatives that have none yet.
        # Side effect (DB write) intentionally lives outside the cached function.
        if "_mdp" in df.columns:
            _needs_fill = (
                df["min_duty_program"].fillna("").astype(str).str.strip() == ""
            ) & (df["_mdp"].fillna("").astype(str).str.strip() != "")
            if _needs_fill.any():
                df.loc[_needs_fill, "min_duty_program"] = df.loc[_needs_fill, "_mdp"]
                _upd_init([
                    {"id": int(r["id"]), "min_duty_program": str(r["_mdp"])}
                    for _, r in df[_needs_fill].iterrows()
                ])
            df = df.drop(columns=["_mdp"], errors="ignore")
    except Exception:
        for _c in _AUTO_COLS:
            df[_c] = float("nan")

    # _total_savings_realized = Duty Savings Realized + Reimbursements Realized
    df["_total_savings_realized"] = (
        pd.to_numeric(df["_auto_savings_realized"], errors="coerce").fillna(0.0)
        + pd.to_numeric(df["reimbursements"], errors="coerce").fillna(0.0)
    ).round(2)

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
                labels={"count": "# Initiatives", "status": "Status", "coi": "COI"},
            )
            fig.update_layout(height=280, **_CL)
            fig.update_xaxes(**_AXIS); fig.update_yaxes(**_AXIS)
            fig.update_traces(hovertemplate="<b>%{y}</b><br>%{fullData.name}: %{x:,d}<extra></extra>")
            _render_plotly(fig, label="#Initiatives by Status")

    # 2 — Total Savings Realized by COI (stacked: FTA + Reimbursements)
    with cch2:
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
                    labels={"value": "Savings Realized (€)", "coi": "COI", "type": ""},
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
                _render_plotly(fig, label="Total Savings Realized by COI")
            else:
                st.info("No savings realized data yet.")

    # ── Initiatives editor ────────────────────────────────────────────────────
    st.markdown("### Initiatives table")
    st.caption("Check **Select** to view initiative details below, group, or delete.")

    _NUMERIC_EDITABLE = {"reimbursements", "potential_reimbursements"}
    _FRIENDLY = {
        # Initiative Definition (text columns — configured via explicit TextColumn loops)
        "coo":                        "COO",
        "coi":                        "COI",
        "hs_code":                    "HS Code",
        "material_number":            "Material Number",
        "min_duty_program":           "Min Duty Program",
        "program_description":        "Min Duty Program Description",
        # PRE · numeric computed columns
        "customs_value":              "PRE · Customs Value",
        "duty_paid":                  "PRE · Total Duty Paid",
        "default_duties":             "PRE · Default Duties",
        "min_duties":                 "PRE · Duty To-Be Paid",
        "_asis_rate":                 "PRE · As-is Rate (%)",
        "_tobe_rate":                 "PRE · To-Be Rate (%)",
        "_initial_overpaid":          "Duties Overpaid",
        "_est_annual_cv":             "PRE · Est. Annual CV",
        "_auto_annual_savings":       "PRE · Est. Annual Savings",
        "potential_reimbursements":   "PRE · Potential Reimbursements",
        "_total_potential_savings":   "PRE · Total Potential Savings",
        # POST · numeric computed columns
        "_post_cv":                   "POST · Total CV",
        "_post_dp":                   "POST · Total Duty Paid",
        "_realized_avg_rate":         "POST · Avg. Rate (%)",
        "_auto_savings_realized":     "POST · Duty Savings (auto)",
        "_final_overpaid":            "POST · Final Overpaid",
        "reimbursements":             "POST · Reimbursements Realized",
        "_total_savings_realized":    "POST · Total Savings Realized",
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
        "id", "coo", "coi", "hs_code", "material_number", "min_duty_program", "program_description",
        "status", "comments",
        "customs_value", "duty_paid", "_applied_rate_disp", "_initial_overpaid",
        "potential_reimbursements", "reimbursements", "_total_savings_realized",
    ]
    extra_cols = ["_group"] if has_groups else []
    display_cols = extra_cols + display_cols_base

    df_main = df_main.sort_values("id", ascending=True).reset_index(drop=True)
    _cv_i = pd.to_numeric(df_main.get("customs_value", pd.Series(dtype=float)), errors="coerce")
    _dp_i = pd.to_numeric(df_main.get("duty_paid", pd.Series(dtype=float)), errors="coerce")
    df_main["_applied_rate_disp"] = (_dp_i / _cv_i.where(_cv_i > 0) * 100).round(4)
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
        "_end_date":  st.column_config.TextColumn("End Date", width="medium"),
        "comments":   st.column_config.TextColumn("Comments"),
        "created_at": st.column_config.TextColumn("Created At", disabled=True, width="medium"),
    }
    if has_groups:
        col_cfg["_group"] = st.column_config.TextColumn("Group", disabled=True, width="small")
    for ro in ["coo", "coi", "hs_code", "material_number", "min_duty_program", "program_description"]:
        if ro in disp.columns:
            col_cfg[ro] = st.column_config.TextColumn(_FRIENDLY.get(ro, ro), disabled=True)
    # Pre-format read-only numeric columns as display strings (thousands separator + €/%)
    _ini_rate_cols = {"_applied_rate_disp", "_asis_rate", "_tobe_rate", "_realized_avg_rate"}
    _ini_curr_cols = {
        "customs_value", "duty_paid", "default_duties", "min_duties",
        "_initial_overpaid", "_final_overpaid", "_est_annual_cv", "_auto_annual_savings",
        "_post_cv", "_post_dp", "_auto_savings_realized", "_total_potential_savings", "_total_savings_realized",
    }
    for _mc in _ini_rate_cols:
        if _mc in disp.columns:
            disp[_mc] = disp[_mc].apply(lambda v: _pre_fmt_num(v, True))
    for _mc in _ini_curr_cols:
        if _mc in disp.columns:
            disp[_mc] = disp[_mc].apply(lambda v: _pre_fmt_num(v, False))
    for mc in ["customs_value", "duty_paid", "default_duties", "min_duties"]:
        if mc in disp.columns:
            col_cfg[mc] = st.column_config.TextColumn(_FRIENDLY.get(mc, mc), disabled=True)
    if "_applied_rate_disp" in disp.columns:
        col_cfg["_applied_rate_disp"] = st.column_config.TextColumn("Applied Rate", disabled=True)
    for mc in ["_initial_overpaid", "_final_overpaid",
               "_est_annual_cv", "_auto_annual_savings",
               "_post_cv", "_post_dp", "_auto_savings_realized",
               "_total_potential_savings", "_total_savings_realized"]:
        if mc in disp.columns:
            col_cfg[mc] = st.column_config.TextColumn(_FRIENDLY.get(mc, mc), disabled=True)
    for mc in ["_asis_rate", "_tobe_rate", "_realized_avg_rate"]:
        if mc in disp.columns:
            col_cfg[mc] = st.column_config.TextColumn(_FRIENDLY.get(mc, mc), disabled=True)
    for mc in _NUMERIC_EDITABLE:
        if mc in disp.columns:
            col_cfg[mc] = st.column_config.NumberColumn(_FRIENDLY.get(mc, mc), format="%.0f €")

    edited_ini = st.data_editor(
        disp,
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
                _gname = _safe_str(_p.get("group_name"))
            _exp_header = f"{_gname or f'Group {_gid}'} — {_plabel}  ({len(_members)} initiatives)"
            with st.expander(_exp_header, expanded=False):
                _sub = _members[[c for c in display_cols_base if c in _members.columns]].copy()
                _sub_friendly = {c: _FRIENDLY.get(c, c) for c in _sub.columns}
                _sub_renamed = _sub.rename(columns=_sub_friendly)
                for _sc in _sub_renamed.columns:
                    if pd.api.types.is_float_dtype(_sub_renamed[_sc]):
                        _ir = "rate" in _sc.lower()
                        _ic = "weight" not in _sc.lower()
                        _sub_renamed[_sc] = _sub_renamed[_sc].apply(lambda v, _x=_ir, _c=_ic: _pre_fmt_num(v, _x, _c))
                st.dataframe(
                    _stripe(_sub_renamed),
                    width='stretch',
                    hide_index=True,
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

        def _ini_section(title: str) -> None:
            """Section header with a thin purple accent rule beneath."""
            st.markdown(
                f'<div class="ini-section-title"><span>{_html.escape(title)}</span></div>'
                f'<div class="ini-section-rule"></div>',
                unsafe_allow_html=True,
            )

        def _metric_value(row: pd.Series, key: str, is_rate: bool = False) -> str:
            return _pre_fmt_num(row.get(key), is_rate) if key in row.index else ""

        def _render_deflist(metrics: List[tuple], cols: int) -> None:
            """Render a definition-list row: label above value, no card decoration.

            Each metric is (label, value) or (label, value, tooltip_text).
            """
            parts = [f'<div class="ini-deflist" style="--ini-cols: {cols};">']
            for item in metrics:
                _lbl = item[0]
                _val = item[1]
                _tip = item[2] if len(item) > 2 else ""
                _txt = _val if _val else "—"
                _cls = "" if _val else " muted"
                _tip_attr = f' data-tooltip="{_html.escape(str(_tip))}"' if _tip else ""
                parts.append(
                    f'<div class="ini-deflist-item">'
                    f'<div class="ini-deflist-label"{_tip_attr}>{_html.escape(str(_lbl))}</div>'
                    f'<div class="ini-deflist-value{_cls}">{_html.escape(str(_txt))}</div>'
                    f'</div>'
                )
            parts.append('</div>')
            st.markdown("".join(parts), unsafe_allow_html=True)

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
            _icoo = _safe_str(_ini.get("coo"))
            _icoi = _safe_str(_ini.get("coi"))
            _ihs  = _safe_str(_ini.get("hs_code"))
            _imat = _safe_str(_ini.get("material_number"))

            _exp_label = f"ID {_ini_id} · {_icoo} · {_icoi} · {_ihs}"
            if _imat:
                _exp_label += f" · {_imat}"

            with st.expander(_exp_label, expanded=True):
                # ── DATES (editable cards) ─────────────────────────────
                _ini_section("Dates")
                _d_orig_sd  = _date_only(_ini.get("start_date", ""))
                _d_orig_id  = _date_only(_ini.get("implementation_date", ""))
                _d_end_disp = _safe_str(_ini.get("_end_date"))

                dc1, dc2, dc3 = st.columns(3)
                with dc1:
                    with st.container(border=True):
                        st.markdown(
                            '<div class="ini-date-label">Start Date</div>',
                            unsafe_allow_html=True,
                        )
                        _new_sd = st.text_input(
                            "Start Date", value=_d_orig_sd,
                            key=f"ini_sd_{_ini_id}",
                            placeholder="YYYY-MM-DD",
                            label_visibility="collapsed",
                        )
                with dc2:
                    with st.container(border=True):
                        st.markdown(
                            '<div class="ini-date-label">Implementation Date</div>',
                            unsafe_allow_html=True,
                        )
                        _new_id_val = st.text_input(
                            "Implementation Date", value=_d_orig_id,
                            key=f"ini_id_{_ini_id}",
                            placeholder="YYYY-MM-DD",
                            label_visibility="collapsed",
                        )
                with dc3:
                    _end_value_html = (
                        f'<div class="ini-date-readonly">{_d_end_disp}</div>'
                        if _d_end_disp
                        else '<div class="ini-date-readonly muted">—</div>'
                    )
                    st.markdown(
                        f'<div class="ini-date-card-static">'
                        f'<div class="ini-date-label">End Date (auto)</div>'
                        f'{_end_value_html}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                _sd_c, _ = st.columns([1, 5])
                with _sd_c:
                    if st.button("Save Dates", key=f"save_dates_{_ini_id}", type="primary"):
                        _d_diff: dict = {"id": int(_ini_id)}
                        _new_sd_v = str(_new_sd or "")[:10]
                        _new_id_v = str(_new_id_val or "")[:10]
                        if _new_sd_v != _d_orig_sd:
                            _d_diff["start_date"] = _new_sd_v or None
                        if _new_id_v != _d_orig_id:
                            _d_diff["implementation_date"] = _new_id_v or None
                        if len(_d_diff) > 1:
                            _upd_init([_d_diff])
                            st.success("Dates saved.")
                            st.rerun()
                        else:
                            st.info("No changes detected.")

                # ── PRE — Before Implementation ────────────────────────
                _ini_section("PRE — Before Implementation")
                # Row 1: factual input data (value → duties paid → rates → target)
                _render_deflist([
                    ("Customs Value",   _metric_value(_ini, "customs_value"),
                     "Declared value of the goods at import, used as the taxable base for duty calculation."),
                    ("Duty Paid",       _metric_value(_ini, "duty_paid"),
                     "Total customs duties effectively paid before applying any preferential program."),
                    ("As-is Rate",      _metric_value(_ini, "_asis_rate", True),
                     "Effective duty rate before optimization.\nFormula: Duty Paid ÷ Customs Value × 100."),
                    ("Duty To-Be Paid", _metric_value(_ini, "min_duties"),
                     "Minimum duties applicable under the preferential program (e.g. FTA rate)."),
                    ("To-Be Rate",      _metric_value(_ini, "_tobe_rate", True),
                     "Target duty rate after applying the preferential program.\nFormula: Duty To-Be Paid ÷ Customs Value × 100."),
                ], cols=5)
                # Row 2: derived savings potential
                _render_deflist([
                    ("Initial Overpaid",         _metric_value(_ini, "_initial_overpaid"),
                     "Estimated overpayment relative to the program minimum.\nFormula: Duty Paid − Duty To-Be Paid."),
                    ("Potential Reimbursements", _metric_value(_ini, "potential_reimbursements"),
                     "Manually entered estimate of duties eligible for reimbursement from customs authorities."),
                    ("Total Potential Savings",  _metric_value(_ini, "_total_potential_savings"),
                     "Combined savings potential for this initiative.\nFormula: Est. Annual Savings + Potential Reimbursements."),
                ], cols=3)

                # ── POST — After Implementation ────────────────────────
                _ini_section("POST — After Implementation")
                # Row 1: factual post-implementation volume & rate (mirrors PRE row 1)
                _render_deflist([
                    ("Total Customs Value", _metric_value(_ini, "_post_cv"),
                     "Cumulative customs value of transactions recorded after implementation (rolling 12-month window)."),
                    ("Total Duty Paid",     _metric_value(_ini, "_post_dp"),
                     "Total duties paid on post-implementation transactions within the 12-month window."),
                    ("Realized Avg. Rate",  _metric_value(_ini, "_realized_avg_rate", True),
                     "Effective duty rate achieved after implementation.\nFormula: Total Duty Paid ÷ Total Customs Value × 100."),
                ], cols=3)
                # Row 2: realized savings & outcome (mirrors PRE row 2)
                _render_deflist([
                    ("Duty Savings Realized",   _metric_value(_ini, "_auto_savings_realized"),
                     "Savings auto-computed from post-implementation transactions.\nFormula: (Pre As-is Rate − Realized Avg. Rate) × Total Customs Value."),
                    ("Reimbursements Realized", _metric_value(_ini, "reimbursements"),
                     "Actual reimbursements received from customs authorities, entered manually."),
                    ("Final Overpaid",          _metric_value(_ini, "_final_overpaid"),
                     "Remaining overpayment after deducting reimbursements received.\nFormula: Initial Overpaid − Reimbursements Realized."),
                    ("Total Savings Realized",  _metric_value(_ini, "_total_savings_realized"),
                     "Total confirmed savings for this initiative.\nFormula: Duty Savings Realized + Reimbursements Realized."),
                ], cols=4)

                # ── TRANSACTIONS ───────────────────────────────────────
                _ini_section("Transactions")
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
                        _tx_sub = _strip_date_cols(_tx_match[_tx_cols], ["date"])
                        _tx_disp = _tx_sub.copy()
                        for _tc in _tx_disp.columns:
                            if pd.api.types.is_float_dtype(_tx_disp[_tc]):
                                _ir = "rate" in _tc.lower()
                                _ic = "weight" not in _tc.lower()
                                _tx_disp[_tc] = _tx_disp[_tc].apply(lambda v, _x=_ir, _c=_ic: _pre_fmt_num(v, _x, _c))
                        st.dataframe(
                            _stripe(_tx_disp),
                            hide_index=True, width='stretch',
                        )
                else:
                    st.info("No transaction data available.")
