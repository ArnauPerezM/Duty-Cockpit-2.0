from __future__ import annotations

from typing import Optional

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
    _render_plotly,
    _fmt_num,
    _render_empty_state,
    _render_kpi_cards,
)

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

_PURPLE_SCALE = [
    [0.0,  "rgba(70,0,115,0.15)"],
    [0.25, "rgba(115,0,192,0.40)"],
    [0.5,  "rgba(161,0,255,0.60)"],
    [0.75, "rgba(194,163,255,0.80)"],
    [1.0,  "rgba(230,220,255,1.0)"],
]

_HEAT_SCALE = [
    [0.0,  "#111318"],
    [0.30, "#2d1a4a"],
    [0.60, "#6a2fa0"],
    [0.85, "#c0a0f0"],
    [1.0,  "#ecdeff"],
]

# Minimal ISO-2 → ISO-3 lookup (covers most trade-relevant countries)
_ISO2_TO_ISO3: dict[str, str] = {
    "AD":"AND","AE":"ARE","AF":"AFG","AG":"ATG","AL":"ALB","AM":"ARM","AO":"AGO",
    "AR":"ARG","AT":"AUT","AU":"AUS","AZ":"AZE","BA":"BIH","BB":"BRB","BD":"BGD",
    "BE":"BEL","BF":"BFA","BG":"BGR","BH":"BHR","BI":"BDI","BJ":"BEN","BN":"BRN",
    "BO":"BOL","BR":"BRA","BS":"BHS","BT":"BTN","BW":"BWA","BY":"BLR","BZ":"BLZ",
    "CA":"CAN","CD":"COD","CF":"CAF","CG":"COG","CH":"CHE","CI":"CIV","CL":"CHL",
    "CM":"CMR","CN":"CHN","CO":"COL","CR":"CRI","CU":"CUB","CV":"CPV","CY":"CYP",
    "CZ":"CZE","DE":"DEU","DJ":"DJI","DK":"DNK","DO":"DOM","DZ":"DZA","EC":"ECU",
    "EE":"EST","EG":"EGY","ER":"ERI","ES":"ESP","ET":"ETH","FI":"FIN","FJ":"FJI",
    "FR":"FRA","GA":"GAB","GB":"GBR","GD":"GRD","GE":"GEO","GH":"GHA","GM":"GMB",
    "GN":"GIN","GQ":"GNQ","GR":"GRC","GT":"GTM","GW":"GNB","GY":"GUY","HN":"HND",
    "HR":"HRV","HT":"HTI","HU":"HUN","ID":"IDN","IE":"IRL","IL":"ISR","IN":"IND",
    "IQ":"IRQ","IR":"IRN","IS":"ISL","IT":"ITA","JM":"JAM","JO":"JOR","JP":"JPN",
    "KE":"KEN","KG":"KGZ","KH":"KHM","KI":"KIR","KM":"COM","KN":"KNA","KP":"PRK",
    "KR":"KOR","KW":"KWT","KZ":"KAZ","LA":"LAO","LB":"LBN","LC":"LCA","LI":"LIE",
    "LK":"LKA","LR":"LBR","LS":"LSO","LT":"LTU","LU":"LUX","LV":"LVA","LY":"LBY",
    "MA":"MAR","MC":"MCO","MD":"MDA","ME":"MNE","MG":"MDG","MK":"MKD","ML":"MLI",
    "MM":"MMR","MN":"MNG","MR":"MRT","MT":"MLT","MU":"MUS","MV":"MDV","MW":"MWI",
    "MX":"MEX","MY":"MYS","MZ":"MOZ","NA":"NAM","NE":"NER","NG":"NGA","NI":"NIC",
    "NL":"NLD","NO":"NOR","NP":"NPL","NR":"NRU","NZ":"NZL","OM":"OMN","PA":"PAN",
    "PE":"PER","PG":"PNG","PH":"PHL","PK":"PAK","PL":"POL","PT":"PRT","PW":"PLW",
    "PY":"PRY","QA":"QAT","RO":"ROU","RS":"SRB","RU":"RUS","RW":"RWA","SA":"SAU",
    "SB":"SLB","SC":"SYC","SD":"SDN","SE":"SWE","SG":"SGP","SI":"SVN","SK":"SVK",
    "SL":"SLE","SM":"SMR","SN":"SEN","SO":"SOM","SR":"SUR","SS":"SSD","ST":"STP",
    "SV":"SLV","SY":"SYR","SZ":"SWZ","TD":"TCD","TG":"TGO","TH":"THA","TJ":"TJK",
    "TL":"TLS","TM":"TKM","TN":"TUN","TO":"TON","TR":"TUR","TT":"TTO","TV":"TUV",
    "TZ":"TZA","UA":"UKR","UG":"UGA","US":"USA","UY":"URY","UZ":"UZB","VA":"VAT",
    "VC":"VCT","VE":"VEN","VN":"VNM","VU":"VUT","WS":"WSM","YE":"YEM","ZA":"ZAF",
    "ZM":"ZMB","ZW":"ZWE",
}


def _iso3(code: str) -> Optional[str]:
    if not code or len(code) < 2:
        return None
    c = code.strip().upper()
    if len(c) == 3:
        return c
    return _ISO2_TO_ISO3.get(c[:2])


# -----------------------------------------------------------------------------
# Styled chart helper (consistent dark/purple look)
# -----------------------------------------------------------------------------
def _styled_fig(fig: go.Figure, height: int = 280) -> go.Figure:
    fig.update_layout(
        height=height,
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=24, b=8),
        font=dict(family="sans-serif", size=12, color="rgba(255,255,255,0.80)"),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=11),
        ),
    )
    return fig


def _section(title: str) -> None:
    st.markdown(
        f'<div style="margin:24px 0 8px 0;">'
        f'<span style="font-size:13px;font-weight:700;letter-spacing:0.8px;'
        f'text-transform:uppercase;color:rgba(255,255,255,0.55);">{title}</span>'
        f'<div style="height:1px;background:linear-gradient(90deg,'
        f'{ACCENTURE_PURPLE_CORE}55,transparent);margin-top:4px;"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _chart_card(fig: go.Figure, label: str = "") -> None:
    # All figures here already set a visible title via fig.update_layout(title=...),
    # which renders as <title> in the SVG and is read by screen readers.
    # The `label` arg overrides only if no title is set.
    _render_plotly(fig, label=label)


# -----------------------------------------------------------------------------
# Reporting tab renderer
# -----------------------------------------------------------------------------
def render_tab_reporting(
    df_merged: Optional[pd.DataFrame],
    df_initiatives: Optional[pd.DataFrame],
    df_failed: Optional[pd.DataFrame] = None,
    df_missing: Optional[pd.DataFrame] = None,
    run_summary=None,
    ref_date: str = "",
    account_label: str = "",
    environment: str = "",
) -> None:
    if df_merged is None or df_merged.empty:
        _render_empty_state(
            "No data to report",
            "📈",
            "Run an analysis in the Process tab to populate this reporting dashboard.",
        )
        return

    df = df_merged.copy()
    for col in ["coo", "coi", "hs code"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()

    # Numeric guards
    for col in ["customs value", "duty paid", "Minimum Duties", "Default Duties",
                "Min Duty Rate", "Default Duty Rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Apply global sidebar filters so charts, KPIs and the downloaded report all
    # reflect exactly what the user has filtered in the sidebar.
    df = _apply_sidebar_filters(df)

    # ── Compute top-level KPIs ────────────────────────────────────────────────
    total_cv   = df["customs value"].sum() if "customs value" in df.columns else 0.0
    total_dp   = df["duty paid"].sum()     if "duty paid"     in df.columns else 0.0
    n_rows     = len(df)

    avg_rate = (total_dp / total_cv * 100) if total_cv > 0 else 0.0

    # Overpaid duties from transactions (Duty Paid − Minimum Duties)
    overpaid_total = 0.0
    if "duty paid" in df.columns and "Minimum Duties" in df.columns:
        overpaid_total = (df["duty paid"] - df["Minimum Duties"].fillna(0)).clip(lower=0).sum()

    # Initiative-level savings metrics
    ini_savings_realized = 0.0
    if df_initiatives is not None and not df_initiatives.empty:
        _ini_s = df_initiatives.copy()
        for _c in ["savings_realized", "reimbursements"]:
            if _c in _ini_s.columns:
                _ini_s[_c] = pd.to_numeric(_ini_s[_c], errors="coerce").fillna(0.0)
        ini_savings_realized = float(
            (_ini_s["savings_realized"].sum() if "savings_realized" in _ini_s.columns else 0.0)
            + (_ini_s["reimbursements"].sum() if "reimbursements" in _ini_s.columns else 0.0)
        )

    # ── Download Report button (top-right, own row) ───────────────────────────
    import datetime as _dt
    from src.logic import build_report_html as _build_report
    _fname = f"duty_report_{ref_date or _dt.date.today().isoformat()}.html"
    _, _dl_col = st.columns([4, 1])
    with _dl_col:
        try:
            _report_bytes = _build_report(
                df_merged=df, df_failed=df_failed, df_missing=df_missing,
                run_summary=run_summary, ref_date=ref_date or "",
                account_label=account_label, environment=environment,
                df_initiatives=df_initiatives,
            )
            st.download_button(
                label="Download Report", data=_report_bytes,
                file_name=_fname, mime="text/html", width="stretch",
                type="primary",
            )
        except Exception as _rep_err:
            st.warning(f"Report error: {_rep_err}")

    # ── KPI cards — 5 columns full width ─────────────────────────────────────
    _capture_rate = (ini_savings_realized / overpaid_total * 100) if overpaid_total > 0 else 0.0
    _render_kpi_cards(cols=5, kpis=[
        {"label": "Total Customs Value", "value": f"{_fmt_num(total_cv)} €",
         "sub": "Cumulative across all runs"},
        {"label": "Total Duty Paid",     "value": f"{_fmt_num(total_dp)} €",
         "sub": "Reported duty exposure"},
        {"label": "Overpaid Duties",     "value": f"{_fmt_num(overpaid_total)} €",
         "sub": "Duty Paid − Min Duties (all transactions)"},
        {"label": "Savings Realized",    "value": f"{_fmt_num(ini_savings_realized)} €",
         "sub": "FTA savings + reimbursements from initiatives"},
        {"label": "Savings Capture Rate", "value": f"{_capture_rate:.1f}%",
         "sub": "Savings Realized / Overpaid Duties"},
    ])

    # ── 1. World Map ──────────────────────────────────────────────────────────
    _section("World Map by Country of Import")

    _map_opts_avail = []
    if "customs value" in df.columns: _map_opts_avail.append("Customs Value")
    if "duty paid"     in df.columns: _map_opts_avail.append("Duty Paid")
    if "duty paid" in df.columns and "Minimum Duties" in df.columns:
        _map_opts_avail.append("Overpaid Duties")

    if "coi" in df.columns and _map_opts_avail:
        _map_sel, _map_spacer = st.columns([2, 8])
        with _map_sel:
            _map_metric = st.selectbox(
                "Metric", _map_opts_avail,
                index=_map_opts_avail.index("Duty Paid") if "Duty Paid" in _map_opts_avail else 0,
                key="rep_map_metric",
                label_visibility="collapsed",
            )

        _df_map = df.copy()
        if _map_metric == "Customs Value":
            _map_src, _map_label = "customs value", "Customs Value (€)"
        elif _map_metric == "Overpaid Duties":
            _df_map["_map_val"] = (
                _df_map["duty paid"] - _df_map["Minimum Duties"].fillna(0)
            ).clip(lower=0)
            _map_src, _map_label = "_map_val", "Overpaid Duties (€)"
        else:
            _map_src, _map_label = "duty paid", "Duty Paid (€)"

        map_df = (
            _df_map.groupby("coi", as_index=False)[_map_src]
            .sum()
            .rename(columns={"coi": "COI", _map_src: _map_label})
        )
        map_df["iso3"] = map_df["COI"].apply(_iso3)
        map_df = map_df.dropna(subset=["iso3"])

        if not map_df.empty:
            fig_map = px.choropleth(
                map_df,
                locations="iso3",
                color=_map_label,
                hover_name="COI",
                hover_data={"iso3": False, _map_label: ":,.0f"},
                color_continuous_scale=_PURPLE_SCALE,
                labels={_map_label: _map_label},
            )
            fig_map.update_geos(
                projection_type="natural earth",
                showframe=False,
                showcoastlines=True,
                coastlinecolor="rgba(255,255,255,0.18)",
                coastlinewidth=0.6,
                showland=True,
                landcolor="rgba(38,28,60,0.92)",
                showocean=True,
                oceancolor="rgba(22,16,40,0.92)",
                showlakes=False,
                showrivers=False,
                showcountries=True,
                countrycolor="rgba(255,255,255,0.10)",
                countrywidth=0.4,
                bgcolor="rgba(0,0,0,0)",
                lataxis_showgrid=True,
                lataxis_gridcolor="rgba(255,255,255,0.05)",
                lonaxis_showgrid=True,
                lonaxis_gridcolor="rgba(255,255,255,0.05)",
            )
            fig_map.update_coloraxes(
                colorbar=dict(
                    thickness=10,
                    len=0.65,
                    tickfont=dict(size=10, color="rgba(255,255,255,0.60)"),
                    title=dict(font=dict(size=10, color="rgba(255,255,255,0.60)")),
                    bgcolor="rgba(0,0,0,0)",
                    borderwidth=0,
                )
            )
            _styled_fig(fig_map, height=480)
            fig_map.update_layout(margin=dict(l=0, r=0, t=4, b=0))
            _chart_card(fig_map)
        else:
            st.caption("No valid country codes found for map rendering.")
    else:
        st.caption("COI column or required metrics unavailable.")

    # ── 2. Top 10 Import Countries — Duties Paid (left) + Overpaid (right) ──────
    _section("Top 10 Import Countries — Duties Paid & Overpaid")

    col_l, col_r = st.columns(2)

    with col_l:
        if "coi" in df.columns and "duty paid" in df.columns:
            top_dp = (
                df.groupby("coi", as_index=False)["duty paid"]
                .sum()
                .sort_values("duty paid", ascending=False)
                .head(10)
                .rename(columns={"coi": "COI", "duty paid": "Duty Paid (€)"})
                .sort_values("Duty Paid (€)", ascending=True)
            )
            if not top_dp.empty:
                fig_dp = px.bar(
                    top_dp, x="Duty Paid (€)", y="COI", orientation="h",
                    title="Top 10 Import Countries — Duties Paid",
                    color_discrete_sequence=[ACCENTURE_PURPLE_CORE],
                    text="Duty Paid (€)",
                )
                fig_dp.update_traces(texttemplate="%{text:,.0f} €", textposition="outside", textfont=dict(size=10))
                fig_dp.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False,
                                     xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False))
                _styled_fig(fig_dp, height=300)
                _chart_card(fig_dp)
            else:
                st.caption("No duty paid data found.")

    with col_r:
        if "coi" in df.columns and "duty paid" in df.columns and "Minimum Duties" in df.columns:
            _df_op = df.copy()
            _df_op["_overpaid"] = (
                _df_op["duty paid"] - _df_op["Minimum Duties"].fillna(0)
            ).clip(lower=0)
            top_op = (
                _df_op.groupby("coi", as_index=False)["_overpaid"]
                .sum()
                .query("_overpaid > 0")
                .sort_values("_overpaid", ascending=False)
                .head(10)
                .rename(columns={"coi": "COI", "_overpaid": "Overpaid Duties (€)"})
                .sort_values("Overpaid Duties (€)", ascending=True)
            )
            if not top_op.empty:
                fig_op = px.bar(
                    top_op, x="Overpaid Duties (€)", y="COI", orientation="h",
                    title="Top 10 Import Countries — Overpaid Duties",
                    color_discrete_sequence=[ACCENTURE_PURPLE_LIGHT],
                    text="Overpaid Duties (€)",
                )
                fig_op.update_traces(texttemplate="%{text:,.0f} €", textposition="outside", textfont=dict(size=10))
                fig_op.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False,
                                     xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False))
                _styled_fig(fig_op, height=300)
                _chart_card(fig_op)
            else:
                st.caption("No overpaid duties found.")

    # ── 3. Heat Map — COO × COI ──────────────────────────────────────────────
    _section("Heat Map (Origin × Import Country)")

    _heat_cols_avail = []
    if "customs value" in df.columns: _heat_cols_avail.append("Customs Value")
    if "duty paid"     in df.columns: _heat_cols_avail.append("Duty Paid")
    if "duty paid" in df.columns and "Minimum Duties" in df.columns: _heat_cols_avail.append("Savings Realized")

    if "coo" in df.columns and "coi" in df.columns and _heat_cols_avail:
        _heat_metric = st.selectbox(
            "Metric", _heat_cols_avail,
            key="rep_heat_metric",
            label_visibility="collapsed",
        )

        _df_heat = df.copy()
        if _heat_metric == "Customs Value":
            _heat_col_src = "customs value"
            _heat_label   = "Customs Value (€)"
            _heat_hover   = "Customs Value"
        elif _heat_metric == "Savings Realized":
            _df_heat["_heat_val"] = (
                _df_heat["duty paid"] - _df_heat["Minimum Duties"].fillna(_df_heat["duty paid"])
            ).clip(lower=0)
            _heat_col_src = "_heat_val"
            _heat_label   = "Overpaid Duties (€)"
            _heat_hover   = "Overpaid"
        else:
            _heat_col_src = "duty paid"
            _heat_label   = "Duty Paid (€)"
            _heat_hover   = "Duty Paid"

        top_coo_list = (
            _df_heat.groupby("coo")[_heat_col_src].sum()
            .sort_values(ascending=False).head(12).index.tolist()
        )
        top_coi_list = (
            _df_heat.groupby("coi")[_heat_col_src].sum()
            .sort_values(ascending=False).head(12).index.tolist()
        )
        heat_df = (
            _df_heat[_df_heat["coo"].isin(top_coo_list) & _df_heat["coi"].isin(top_coi_list)]
            .groupby(["coo", "coi"], as_index=False)[_heat_col_src].sum()
        )

        if not heat_df.empty:
            pivot = heat_df.pivot(index="coo", columns="coi", values=_heat_col_src).fillna(0)
            pivot = pivot.loc[
                pivot.sum(axis=1).sort_values(ascending=False).index,
                pivot.sum(axis=0).sort_values(ascending=False).index,
            ]
            # Format text annotations (K / M)
            def _fmt_cell(v):
                if v == 0: return ""
                if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
                if v >= 1_000:     return f"{v/1_000:.0f}K"
                return f"{v:.0f}"

            _zmax = pivot.values.max() if pivot.values.max() > 0 else 1

            fig_heat = go.Figure(go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale=_HEAT_SCALE,
                hoverongaps=False,
                xgap=3, ygap=3,
                hovertemplate=f"COO: %{{y}}<br>COI: %{{x}}<br>{_heat_hover}: %{{z:,.0f}} €<extra></extra>",
                colorbar=dict(
                    thickness=10,
                    tickfont=dict(size=10, color="rgba(255,255,255,0.60)"),
                    title=dict(text="€", font=dict(size=10)),
                ),
            ))
            # Per-cell text annotations with contrast-aware colour
            for ri, row_vals in enumerate(pivot.values):
                for ci, v in enumerate(row_vals):
                    if v == 0:
                        continue
                    fig_heat.add_annotation(
                        x=pivot.columns[ci], y=pivot.index[ri],
                        text=_fmt_cell(v),
                        showarrow=False,
                        font=dict(
                            size=11,
                            color="#1a0a2e" if v / _zmax > 0.55 else "rgba(255,255,255,0.88)",
                        ),
                        xref="x", yref="y",
                    )

            fig_heat.update_layout(
                xaxis=dict(title="Country of Import", tickangle=-35),
                yaxis=dict(title="Country of Origin", autorange="reversed"),
                title=f"{_heat_metric} (€) — Top 12 Origins × Top 12 Import Markets",
            )
            _styled_fig(fig_heat, height=420)
            _chart_card(fig_heat)
        else:
            st.caption("Not enough COO/COI combinations for heat map.")
    else:
        st.caption("COO, COI or metric columns unavailable.")

    # ── 4. Monthly Trend — Duty Paid vs Overpaid Duties ──────────────────────
    _section("Monthly Trend — Duty Paid vs Overpaid Duties")

    _date_col = next(
        (c for c in ["Input Date", "input_date", "ref_date", "date"] if c in df.columns),
        None,
    )
    if _date_col and "duty paid" in df.columns:
        trend = df.copy()
        trend["_month"] = pd.to_datetime(trend[_date_col], errors="coerce").dt.to_period("M")
        trend = trend.dropna(subset=["_month"])

        if not trend.empty:
            _has_min = "Minimum Duties" in trend.columns
            _agg = {"Duty Paid": ("duty paid", "sum")}
            if _has_min:
                _agg["Minimum Duties"] = ("Minimum Duties", "sum")

            monthly = trend.groupby("_month").agg(**_agg).reset_index()
            monthly["_month"] = monthly["_month"].astype(str)
            if _has_min:
                monthly["Minimum Duties"] = monthly["Minimum Duties"].fillna(0)

            fig_trend = go.Figure()

            # Trace 1 (bottom): Minimum Duties — fill to x-axis (efficient portion)
            if _has_min:
                fig_trend.add_trace(go.Scatter(
                    x=monthly["_month"], y=monthly["Minimum Duties"],
                    name="Minimum Duties",
                    mode="lines+markers",
                    line=dict(color=ACCENTURE_PURPLE_LIGHT, width=2, dash="dot"),
                    marker=dict(size=4),
                    fill="tozeroy",
                    fillcolor="rgba(161,0,255,0.18)",
                    hovertemplate="%{x}<br>Min Duties: %{y:,.0f} €<extra></extra>",
                ))

            # Trace 2 (top): Duty Paid — fill to previous trace = Overpaid area (amber)
            fig_trend.add_trace(go.Scatter(
                x=monthly["_month"], y=monthly["Duty Paid"],
                name="Duty Paid",
                mode="lines+markers",
                line=dict(color=ACCENTURE_PURPLE_CORE, width=2),
                marker=dict(size=5),
                fill="tonexty" if _has_min else "tozeroy",
                fillcolor="rgba(161,0,255,0.35)" if _has_min else "rgba(161,0,255,0.20)",
                hovertemplate="%{x}<br>Duty Paid: %{y:,.0f} €<extra></extra>",
            ))

            fig_trend.update_layout(
                title="Monthly Trend — Duty Paid vs Minimum Duties",
                xaxis=dict(title=None, showgrid=False, tickangle=-35),
                yaxis=dict(title="EUR", showgrid=True,
                           gridcolor="rgba(255,255,255,0.06)"),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            xanchor="right", x=1, font=dict(size=12)),
            )
            _styled_fig(fig_trend, height=300)
            _chart_card(fig_trend)
        else:
            st.caption("No valid date data for trend chart.")
    else:
        st.caption("Date column not available for trend chart.")

    # ── 5. Initiative Impact ──────────────────────────────────────────────────
    _section("Initiative Impact")

    if df_initiatives is not None and not df_initiatives.empty:
        _ini = df_initiatives.copy()
        for _c in ["duty_paid", "min_duties", "savings_realized", "reimbursements",
                   "potential_reimbursements", "customs_value"]:
            if _c in _ini.columns:
                _ini[_c] = pd.to_numeric(_ini[_c], errors="coerce").fillna(0.0)

        # Compute annual expected savings via cross-reference with transactions
        try:
            from src.ui_initiatives import _compute_initiative_metrics as _cim
            _auto_df = _cim(_ini, df)
            _ini = _ini.merge(
                _auto_df[["id", "_auto_annual_savings", "_auto_savings_realized"]],
                on="id", how="left",
            )
            for _ac in ["_auto_annual_savings", "_auto_savings_realized"]:
                _ini[_ac] = pd.to_numeric(_ini[_ac], errors="coerce").fillna(0.0)
        except Exception:
            _ini["_auto_annual_savings"]  = 0.0
            _ini["_auto_savings_realized"] = 0.0

        _imp_l, _imp_r = st.columns([5, 3])

        with _imp_l:
            if "coi" in _ini.columns:
                _exp_g = _ini.groupby("coi")["_auto_annual_savings"].sum().reset_index()
                _exp_g["metric"] = "Est. Annual Savings"
                _exp_g = _exp_g.rename(columns={"_auto_annual_savings": "value"})

                _real_g = _ini.groupby("coi")["_auto_savings_realized"].sum().reset_index()
                _real_g["metric"] = "Savings Realized (annual)"
                _real_g = _real_g.rename(columns={"_auto_savings_realized": "value"})

                _impact_df = pd.concat([_exp_g, _real_g])
                _impact_df = _impact_df[_impact_df["value"] > 0]
                if not _impact_df.empty:
                    _coi_order = (
                        _exp_g.sort_values("value", ascending=False)["coi"].tolist()
                    )
                    fig_imp = px.bar(
                        _impact_df, x="value", y="coi", color="metric",
                        orientation="h", barmode="group",
                        color_discrete_sequence=[ACCENTURE_PURPLE_CORE, ACCENTURE_PURPLE_LIGHT],
                        category_orders={"coi": _coi_order},
                        labels={"value": "", "coi": "", "metric": ""},
                    )
                    fig_imp.update_traces(
                        hovertemplate="<b>%{y}</b><br>%{fullData.name}: %{x:,.0f} €<extra></extra>",
                    )
                    _styled_fig(fig_imp, height=320)
                    fig_imp.update_layout(
                        title="Est. Annual Savings vs Savings Realized by COI",
                        xaxis_title=None, yaxis_title=None,
                        margin=dict(l=8, r=8, t=40, b=52),
                        legend=dict(
                            orientation="h", yanchor="top", y=-0.12,
                            xanchor="center", x=0.5, font=dict(size=11),
                            bgcolor="rgba(0,0,0,0)", title_text="",
                        ),
                    )
                    fig_imp.update_xaxes(
                        ticksuffix=" €", tickformat=".2s",
                        showgrid=True, gridcolor="rgba(255,255,255,0.07)",
                        zeroline=False,
                        showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1,
                    )
                    fig_imp.update_yaxes(
                        showgrid=False,
                        showline=True, linecolor="rgba(255,255,255,0.25)", linewidth=1,
                    )
                    _chart_card(fig_imp)
                else:
                    st.caption("No initiative savings data to display yet.")

        with _imp_r:
            if "status" in _ini.columns:
                _st_cnt = _ini.groupby("status").size().reset_index(name="count")
                _total_ini = int(_st_cnt["count"].sum())
                if not _st_cnt.empty:
                    _color_map = {
                        "Identified":  ACCENTURE_PURPLE_LIGHTEST,
                        "Validated":   ACCENTURE_PURPLE_LIGHT,
                        "Completed":   ACCENTURE_PURPLE_CORE,
                        "Discarded":   ACCENTURE_PURPLE_DARKEST,
                    }
                    _st_cnt["color"] = _st_cnt["status"].map(_color_map).fillna(ACCENTURE_PURPLE_DARK)
                    fig_donut = go.Figure(go.Pie(
                        labels=_st_cnt["status"],
                        values=_st_cnt["count"],
                        hole=0.62,
                        marker=dict(
                            colors=_st_cnt["color"].tolist(),
                            line=dict(color="rgba(0,0,0,0.3)", width=2),
                        ),
                        textinfo="label+percent",
                        textfont=dict(size=12),
                        hovertemplate="<b>%{label}</b><br>%{value} initiatives (%{percent})<extra></extra>",
                    ))
                    fig_donut.update_layout(
                        title="Initiative Portfolio by Status",
                        annotations=[dict(
                            text=f"<b>{_total_ini}</b><br><span style='font-size:10px'>initiatives</span>",
                            x=0.5, y=0.5, showarrow=False,
                            font=dict(size=18, color="rgba(255,255,255,0.92)"),
                            xanchor="center",
                        )],
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="top", y=-0.12,
                                    xanchor="center", x=0.5, font=dict(size=11)),
                    )
                    _styled_fig(fig_donut, height=320)
                    fig_donut.update_layout(margin=dict(l=8, r=8, t=40, b=52))
                    _chart_card(fig_donut)
                else:
                    st.caption("No initiative status data yet.")
    else:
        st.caption("No initiative data available. Create initiatives in the Opportunities tab to see impact analysis here.")

    # ── 6. Top Trade Lanes table ──────────────────────────────────────────────
    _section("Top Trade Lanes")

    if "coo" in df.columns and "coi" in df.columns and "duty paid" in df.columns:
        lanes = (
            df.groupby(["coo", "coi"], as_index=False)
            .agg(
                **{
                    "Transactions": ("duty paid", "count"),
                    "Duty Paid (€)": ("duty paid", "sum"),
                    **({"Customs Value (€)": ("customs value", "sum")} if "customs value" in df.columns else {}),
                }
            )
            .sort_values("Duty Paid (€)", ascending=False)
            .head(20)
            .rename(columns={"coo": "Origin (COO)", "coi": "Import (COI)"})
        )
        if "Customs Value (€)" in lanes.columns:
            lanes["Eff. Rate"] = (
                lanes["Duty Paid (€)"] / lanes["Customs Value (€)"].replace(0, float("nan"))
            ).map(lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A")

        for col in ["Duty Paid (€)", "Customs Value (€)"]:
            if col in lanes.columns:
                lanes[col] = lanes[col].map(lambda x: f"{x:,.0f} €")

        st.dataframe(
            lanes.reset_index(drop=True),
            width='stretch',
            hide_index=True,
            height=380,
        )
    else:
        st.caption("Trade lane data unavailable.")
