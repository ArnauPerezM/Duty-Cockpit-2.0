from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
import plotly.express as px
import pycountry
import streamlit as st

from src.ui_shared import (
    ACCENTURE_PURPLE_CORE,
    ACCENTURE_PURPLE_DARK,
    ACCENTURE_PURPLE_DARKEST,
    ACCENTURE_PURPLE_LIGHT,
    ACCENTURE_PURPLE_LIGHTEST,
    _fmt_num,
    _fmt_int,
    _fmt_pct,
    _render_kpi_cards,
    _render_plotly,
    _stripe,
    _auto_col_cfg,
)


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

    _render_plotly(fig, label=title)

    st.markdown("### Top 10 countries (selected metric)")
    if top_money_cols:
        sty = top_df.style.format({c: (lambda v: _fmt_num(v)) for c in top_money_cols})
        st.dataframe(_stripe(sty), width="stretch", column_config=_auto_col_cfg(top_df))
    else:
        st.dataframe(_stripe(top_df), width="stretch", column_config=_auto_col_cfg(top_df))


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
        st.dataframe(_stripe(df_clean), width="stretch", column_config=_auto_col_cfg(df_clean))
    else:
        st.info("No candidate rows found (or all rows are already marked as analyzed).")

    if df_missing is not None and not df_missing.empty:
        with st.expander("Missing rows (skipped)"):
            st.dataframe(_stripe(df_missing), width="stretch", column_config=_auto_col_cfg(df_missing))


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
