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
    _render_plotly,
    _fmt_num,
    _fmt_int,
    _render_empty_state,
    _render_kpi_cards,
)

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
_CARD_BG = "rgba(255,255,255,0.03)"
_BORDER   = "rgba(255,255,255,0.10)"

_PURPLE_SCALE = [
    [0.0,  "rgba(70,0,115,0.15)"],
    [0.25, "rgba(115,0,192,0.40)"],
    [0.5,  "rgba(161,0,255,0.60)"],
    [0.75, "rgba(194,163,255,0.80)"],
    [1.0,  "rgba(230,220,255,1.0)"],
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
        paper_bgcolor=_CARD_BG,
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=32, b=8),
        font=dict(family="sans-serif", size=12, color="rgba(255,255,255,0.80)"),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(255,255,255,0.10)",
            borderwidth=1,
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

    # ── Compute top-level KPIs ────────────────────────────────────────────────
    total_cv   = df["customs value"].sum() if "customs value" in df.columns else 0.0
    total_dp   = df["duty paid"].sum()     if "duty paid"     in df.columns else 0.0
    n_rows     = len(df)

    avg_rate = (total_dp / total_cv * 100) if total_cv > 0 else 0.0

    # Overpaid duties from transactions (Duty Paid − Minimum Duties)
    overpaid_total = 0.0
    if "duty paid" in df.columns and "Minimum Duties" in df.columns:
        overpaid_total = (df["duty paid"] - df["Minimum Duties"].fillna(df["duty paid"])).clip(lower=0).sum()

    # Initiative-level savings metrics
    ini_savings_realized = 0.0
    if df_initiatives is not None and not df_initiatives.empty:
        _ini_s = df_initiatives.copy()
        for _c in ["savings_realized", "reimbursements"]:
            if _c in _ini_s.columns:
                _ini_s[_c] = pd.to_numeric(_ini_s[_c], errors="coerce").fillna(0.0)
        ini_savings_realized = float(
            _ini_s.get("savings_realized", pd.Series([0.0])).sum()
            + _ini_s.get("reimbursements", pd.Series([0.0])).sum()
        )

    # ── Download Report button (top-right, own row) ───────────────────────────
    import datetime as _dt
    from src.logic import build_report_html as _build_report
    _fname = f"duty_report_{ref_date or _dt.date.today().isoformat()}.html"
    _, _dl_col = st.columns([4, 1])
    with _dl_col:
        try:
            _report_bytes = _build_report(
                df_merged=df_merged, df_failed=df_failed, df_missing=df_missing,
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
    _render_kpi_cards(cols=5, kpis=[
        {"label": "Total Customs Value", "value": f"{_fmt_num(total_cv)} €",
         "sub": "Cumulative across all runs"},
        {"label": "Total Duty Paid",     "value": f"{_fmt_num(total_dp)} €",
         "sub": "Reported duty exposure"},
        {"label": "Avg Effective Rate",  "value": f"{avg_rate:.1f}%",
         "sub": "Duty Paid / Customs Value"},
        {"label": "Overpaid Duties",     "value": f"{_fmt_num(overpaid_total)} €",
         "sub": "Duty Paid − Min Duties (all transactions)",
         "delta": "savings opportunity", "delta_kind": "good"},
        {"label": "Savings Realized",    "value": f"{_fmt_num(ini_savings_realized)} €",
         "sub": "FTA savings + reimbursements from initiatives",
         "delta": "from initiatives", "delta_kind": "good"},
    ])

    # ── 1. World Map — Duty Paid by COI ──────────────────────────────────────
    _section("Duty Paid by Country of Import")

    if "coi" in df.columns and "duty paid" in df.columns:
        map_df = (
            df.groupby("coi", as_index=False)["duty paid"]
            .sum()
            .rename(columns={"coi": "COI", "duty paid": "Duty Paid (€)"})
        )
        map_df["iso3"] = map_df["COI"].apply(_iso3)
        map_df = map_df.dropna(subset=["iso3"])

        if not map_df.empty:
            fig_map = px.choropleth(
                map_df,
                locations="iso3",
                color="Duty Paid (€)",
                hover_name="COI",
                hover_data={"iso3": False, "Duty Paid (€)": ":,.0f"},
                color_continuous_scale=_PURPLE_SCALE,
                labels={"Duty Paid (€)": "Duty Paid (€)"},
            )
            fig_map.update_geos(
                showframe=False,
                showcoastlines=True,
                coastlinecolor="rgba(255,255,255,0.15)",
                showland=True,
                landcolor="rgba(255,255,255,0.05)",
                showocean=True,
                oceancolor="rgba(0,0,0,0)",
                showlakes=False,
                bgcolor="rgba(0,0,0,0)",
            )
            fig_map.update_coloraxes(
                colorbar=dict(
                    thickness=10,
                    len=0.6,
                    tickfont=dict(size=10, color="rgba(255,255,255,0.60)"),
                    title=dict(font=dict(size=10)),
                )
            )
            _styled_fig(fig_map, height=340)
            _chart_card(fig_map)
        else:
            st.caption("No valid country codes found for map rendering.")
    else:
        st.caption("COI or Duty Paid columns unavailable.")

    # ── 2. Top COI (Overpaid) + COO (Customs Value) bars ─────────────────────
    _section("Top Import Markets — Overpaid Duties & Origin Customs Value")

    col_l, col_r = st.columns(2)

    with col_l:
        if "coi" in df.columns and "duty paid" in df.columns and "Minimum Duties" in df.columns:
            _df_op = df.copy()
            _df_op["_overpaid"] = (
                _df_op["duty paid"] - _df_op["Minimum Duties"].fillna(_df_op["duty paid"])
            ).clip(lower=0)
            top_coi = (
                _df_op.groupby("coi", as_index=False)["_overpaid"]
                .sum()
                .query("_overpaid > 0")
                .sort_values("_overpaid", ascending=False)
                .head(10)
                .rename(columns={"coi": "COI", "_overpaid": "Overpaid Duties (€)"})
                .sort_values("Overpaid Duties (€)", ascending=True)
            )
            if not top_coi.empty:
                fig_coi = px.bar(
                    top_coi,
                    x="Overpaid Duties (€)", y="COI",
                    orientation="h",
                    title="Top 10 Import Countries — Overpaid Duties",
                    color_discrete_sequence=[ACCENTURE_PURPLE_CORE],
                    text="Overpaid Duties (€)",
                )
                fig_coi.update_traces(
                    texttemplate="%{text:,.0f} €",
                    textposition="outside",
                    textfont=dict(size=10),
                )
                fig_coi.update_layout(
                    xaxis_title=None, yaxis_title=None,
                    showlegend=False,
                    xaxis=dict(showgrid=False, zeroline=False),
                    yaxis=dict(showgrid=False),
                )
                _styled_fig(fig_coi, height=300)
                _chart_card(fig_coi)
            else:
                st.caption("No overpaid duties found.")
        elif "coi" in df.columns and "duty paid" in df.columns:
            top_coi = (
                df.groupby("coi", as_index=False)["duty paid"]
                .sum()
                .sort_values("duty paid", ascending=False)
                .head(10)
                .rename(columns={"coi": "COI", "duty paid": "Duty Paid (€)"})
                .sort_values("Duty Paid (€)", ascending=True)
            )
            fig_coi = px.bar(
                top_coi, x="Duty Paid (€)", y="COI", orientation="h",
                title="Top 10 Import Countries — Duty Paid",
                color_discrete_sequence=[ACCENTURE_PURPLE_CORE], text="Duty Paid (€)",
            )
            fig_coi.update_traces(texttemplate="%{text:,.0f} €", textposition="outside", textfont=dict(size=10))
            fig_coi.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False,
                                  xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False))
            _styled_fig(fig_coi, height=300)
            _chart_card(fig_coi)

    with col_r:
        if "coo" in df.columns and "customs value" in df.columns:
            top_coo = (
                df.groupby("coo", as_index=False)["customs value"]
                .sum()
                .sort_values("customs value", ascending=False)
                .head(10)
                .rename(columns={"coo": "COO", "customs value": "Customs Value (€)"})
            )
            top_coo = top_coo.sort_values("Customs Value (€)", ascending=True)

            fig_coo = px.bar(
                top_coo,
                x="Customs Value (€)", y="COO",
                orientation="h",
                title="Top 10 Origin Countries — Customs Value",
                color_discrete_sequence=[ACCENTURE_PURPLE_LIGHT],
                text="Customs Value (€)",
            )
            fig_coo.update_traces(
                texttemplate="%{text:,.0f} €",
                textposition="outside",
                textfont=dict(size=10),
            )
            fig_coo.update_layout(
                xaxis_title=None, yaxis_title=None,
                showlegend=False,
                xaxis=dict(showgrid=False, zeroline=False),
                yaxis=dict(showgrid=False),
            )
            _styled_fig(fig_coo, height=300)
            _chart_card(fig_coo)

    # ── 3. Heat Map — COO × COI duty intensity ────────────────────────────────
    _section("Duty Intensity Heat Map (Origin × Import Country)")

    if "coo" in df.columns and "coi" in df.columns and "duty paid" in df.columns:
        top_coo_list = (
            df.groupby("coo")["duty paid"].sum()
            .sort_values(ascending=False)
            .head(12)
            .index.tolist()
        )
        top_coi_list = (
            df.groupby("coi")["duty paid"].sum()
            .sort_values(ascending=False)
            .head(12)
            .index.tolist()
        )

        heat_df = (
            df[df["coo"].isin(top_coo_list) & df["coi"].isin(top_coi_list)]
            .groupby(["coo", "coi"], as_index=False)["duty paid"]
            .sum()
        )

        if not heat_df.empty:
            pivot = heat_df.pivot(index="coo", columns="coi", values="duty paid").fillna(0)
            # Order axes by total
            pivot = pivot.loc[
                pivot.sum(axis=1).sort_values(ascending=False).index,
                pivot.sum(axis=0).sort_values(ascending=False).index,
            ]

            fig_heat = go.Figure(go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale=_PURPLE_SCALE,
                hoverongaps=False,
                hovertemplate="COO: %{y}<br>COI: %{x}<br>Duty Paid: %{z:,.0f} €<extra></extra>",
                colorbar=dict(
                    thickness=10,
                    tickfont=dict(size=10, color="rgba(255,255,255,0.60)"),
                    title=dict(text="€", font=dict(size=10)),
                ),
            ))
            fig_heat.update_layout(
                xaxis=dict(title="Country of Import", tickangle=-35),
                yaxis=dict(title="Country of Origin", autorange="reversed"),
                title="Duty Paid (€) — Top 12 Origins × Top 12 Import Markets",
            )
            _styled_fig(fig_heat, height=380)
            _chart_card(fig_heat)
        else:
            st.caption("Not enough COO/COI combinations for heat map.")
    else:
        st.caption("COO, COI or Duty Paid columns unavailable.")

    # ── 4. Monthly Trend ──────────────────────────────────────────────────────
    _section("Monthly Trend")

    _date_col = next(
        (c for c in ["Input Date", "input_date", "ref_date", "date"] if c in df.columns),
        None,
    )
    if _date_col and "duty paid" in df.columns:
        trend = df.copy()
        trend["_month"] = pd.to_datetime(trend[_date_col], errors="coerce").dt.to_period("M")
        trend = trend.dropna(subset=["_month"])

        if not trend.empty:
            monthly = (
                trend.groupby("_month")
                .agg(
                    **{
                        "Duty Paid (€)": ("duty paid", "sum"),
                        **({"Customs Value (€)": ("customs value", "sum")} if "customs value" in trend.columns else {}),
                    }
                )
                .reset_index()
            )
            monthly["_month"] = monthly["_month"].astype(str)

            fig_trend = go.Figure()
            if "Customs Value (€)" in monthly.columns:
                fig_trend.add_trace(go.Scatter(
                    x=monthly["_month"], y=monthly["Customs Value (€)"],
                    name="Customs Value",
                    mode="lines+markers",
                    line=dict(color=ACCENTURE_PURPLE_LIGHT, width=2),
                    marker=dict(size=5),
                    hovertemplate="%{x}<br>Customs Value: %{y:,.0f} €<extra></extra>",
                ))
            fig_trend.add_trace(go.Scatter(
                x=monthly["_month"], y=monthly["Duty Paid (€)"],
                name="Duty Paid",
                mode="lines+markers",
                line=dict(color=ACCENTURE_PURPLE_CORE, width=2),
                marker=dict(size=5),
                fill="tozeroy",
                fillcolor="rgba(161,0,255,0.08)",
                hovertemplate="%{x}<br>Duty Paid: %{y:,.0f} €<extra></extra>",
            ))
            fig_trend.update_layout(
                title="Duty Paid & Customs Value — Monthly",
                xaxis=dict(title=None, showgrid=False, tickangle=-35),
                yaxis=dict(title="EUR", showgrid=True,
                           gridcolor="rgba(255,255,255,0.06)"),
                hovermode="x unified",
            )
            _styled_fig(fig_trend, height=280)
            _chart_card(fig_trend)
        else:
            st.caption("No valid date data for trend chart.")
    else:
        st.caption("Date column not available for trend chart.")

    # ── 5. Initiative Impact ──────────────────────────────────────────────────
    _section("Initiative Impact — PRE vs POST")

    if df_initiatives is not None and not df_initiatives.empty:
        _ini = df_initiatives.copy()
        for _c in ["duty_paid", "min_duties", "savings_realized", "reimbursements", "potential_reimbursements"]:
            if _c in _ini.columns:
                _ini[_c] = pd.to_numeric(_ini[_c], errors="coerce").fillna(0.0)
        _ini["_pre_overpaid"] = (_ini["duty_paid"] - _ini["min_duties"]).clip(lower=0)
        _ini["_post_realized"] = (
            _ini.get("savings_realized", pd.Series([0.0] * len(_ini), index=_ini.index))
            + _ini.get("reimbursements", pd.Series([0.0] * len(_ini), index=_ini.index))
        )

        _imp_l, _imp_r = st.columns([3, 2])

        with _imp_l:
            if "coi" in _ini.columns:
                _pre_g  = _ini.groupby("coi")["_pre_overpaid"].sum().reset_index()
                _pre_g["phase"] = "PRE — Overpaid"
                _pre_g  = _pre_g.rename(columns={"_pre_overpaid": "value"})
                _post_g = _ini.groupby("coi")["_post_realized"].sum().reset_index()
                _post_g["phase"] = "POST — Realized"
                _post_g = _post_g.rename(columns={"_post_realized": "value"})
                _impact_df = pd.concat([_pre_g, _post_g])
                _impact_df = _impact_df[_impact_df["value"] > 0]
                if not _impact_df.empty:
                    _coi_order = (
                        _pre_g.sort_values("value", ascending=False)["coi"].tolist()
                    )
                    fig_imp = px.bar(
                        _impact_df, x="value", y="coi", color="phase",
                        orientation="h", barmode="group",
                        title="Overpaid (PRE) vs Savings Realized (POST) by COI",
                        color_discrete_sequence=[ACCENTURE_PURPLE_CORE, ACCENTURE_PURPLE_LIGHT],
                        category_orders={"coi": _coi_order},
                    )
                    fig_imp.update_traces(
                        hovertemplate="<b>%{y}</b><br>%{fullData.name}: %{x:,.0f} €<extra></extra>",
                    )
                    fig_imp.update_layout(
                        xaxis_title=None, yaxis_title=None,
                        xaxis=dict(ticksuffix=" €", tickformat=".2s", showgrid=False, zeroline=False),
                        yaxis=dict(showgrid=False),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                                    font=dict(size=11)),
                    )
                    _styled_fig(fig_imp, height=300)
                    _chart_card(fig_imp)
                else:
                    st.caption("No initiative values to display yet.")

        with _imp_r:
            if "status" in _ini.columns:
                _st_cnt = _ini.groupby("status").size().reset_index(name="count")
                _total_ini = int(_st_cnt["count"].sum())
                _total_pot = float(_ini["_pre_overpaid"].sum())
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
                        annotations=[
                            dict(
                                text=f"<b>{_total_ini}</b><br><span style='font-size:10px'>initiatives</span>",
                                x=0.5, y=0.55, showarrow=False,
                                font=dict(size=18, color="rgba(255,255,255,0.92)"),
                                xanchor="center",
                            ),
                            dict(
                                text=f"{_fmt_num(_total_pot)} €",
                                x=0.5, y=0.38, showarrow=False,
                                font=dict(size=12, color="rgba(255,255,255,0.55)"),
                                xanchor="center",
                            ),
                        ],
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="bottom", y=-0.15,
                                    xanchor="center", x=0.5, font=dict(size=11)),
                    )
                    _styled_fig(fig_donut, height=300)
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
