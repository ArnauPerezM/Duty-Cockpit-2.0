from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from E2Open import E2OpenSession
from src.db import load_fta_explorer_requests, save_fta_explorer_request
from src.logic import (
    _clean_country,
    _clean_hs,
    extract_fta_programs_from_session_output,
    get_effective_hs_from_session_output,
)
from src.ui_shared import _auto_col_cfg, _stripe

_PROGRAMS_EMPTY = pd.DataFrame(columns=["Program", "Rate %", "Description", "HS Code"])

_REQUEST_COL_LABELS: dict[str, str] = {
    "requested_at": "Requested At",
    "country_of_import": "Country Of Import",
    "hs_code": "HS Code",
    "comment": "Comment",
    "program_count": "Program Count",
}


def _request_col_cfg(display_cols: list[str]) -> dict:
    return {
        col: st.column_config.Column(
            label=_REQUEST_COL_LABELS.get(col, col.replace("_", " ").title())
        )
        for col in display_cols
    }


def render_tab_fta_explorer() -> None:
    st.subheader("FTA Explorer")
    st.caption("Query e2open for available duty programs by country and HS code, then keep a history of each lookup.")

    st.session_state.setdefault("fta_explorer_last_result", None)
    st.session_state.setdefault("fta_explorer_last_programs", None)
    st.session_state.setdefault("fta_explorer_search_count", 0)

    with st.form("fta_explorer_form", clear_on_submit=False):
        col_a, col_b = st.columns([1, 1])
        with col_a:
            country_of_import = st.text_input(
                "Country of import",
                value=st.session_state.get("fta_explorer_country", ""),
                placeholder="e.g. DE",
                help="Use the ISO country code for the importing country.",
            )
        with col_b:
            hs_code = st.text_input(
                "HS code",
                value=st.session_state.get("fta_explorer_hs", ""),
                placeholder="e.g. 8518302000",
                help="Enter the HS code without spaces or punctuation.",
            )

        submitted = st.form_submit_button("Lookup duty programs", type="primary", use_container_width=True)

    if submitted:
        cleaned_country = _clean_country(country_of_import)
        cleaned_hs = _clean_hs(hs_code)
        st.session_state["fta_explorer_country"] = cleaned_country
        st.session_state["fta_explorer_hs"] = cleaned_hs

        if not cleaned_country or not cleaned_hs:
            st.warning("Both the country and HS code are required.")
            return

        if not st.session_state.auth_ok:
            st.warning("Connect to e2open first from the Process tab before running an FTA lookup.")
            return

        try:
            ref_date = st.session_state.get("ref_date") or ""
            session = E2OpenSession(
                st.session_state.e2open_username,
                st.session_state.e2open_password,
                st.session_state.e2open_tenant,
                st.session_state.e2open_env,
            )
            _, _, _, _, _, _, status_code, comment = session.getImportCost(
                cleaned_country,
                cleaned_country,
                cleaned_hs,
                0,
                "EUR",
                1,
                ref_date,
            )
            programs_df = extract_fta_programs_from_session_output(session.output)
            effective_hs = get_effective_hs_from_session_output(session.output, cleaned_hs)
            payload_json = json.dumps(session.output, default=str)
            program_count = int(len(programs_df)) if programs_df is not None else 0

            request_record = {
                "requested_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                "country_of_import": cleaned_country,
                "hs_code": cleaned_hs,
                "ref_date": ref_date,
                "account_key": st.session_state.account_key or "",
                "account_label": st.session_state.account_label or "",
                "environment": st.session_state.e2open_env or "",
                "status": str(status_code),
                "comment": comment or "",
                "program_count": program_count,
                "payload_json": payload_json,
            }
            save_fta_explorer_request(request_record)
            st.cache_data.clear()
            st.session_state["fta_explorer_search_count"] += 1

            st.session_state["fta_explorer_last_result"] = {
                "country_of_import": cleaned_country,
                "hs_code": cleaned_hs,
                "effective_hs": effective_hs,
                "ref_date": ref_date,
                "status_code": status_code,
                "comment": comment,
                "program_count": program_count,
            }
            st.session_state["fta_explorer_last_programs"] = programs_df

            st.session_state.logs.append({
                "ts": time.time(),
                "event": "fta_explorer_request",
                "country_of_import": cleaned_country,
                "hs_code": cleaned_hs,
                "ref_date": ref_date,
                "status": str(status_code),
                "comment": comment or "",
                "program_count": program_count,
            })

            st.success(f"Lookup completed for {cleaned_country} / {cleaned_hs}.")
        except Exception as exc:
            st.session_state["fta_explorer_last_result"] = {
                "country_of_import": cleaned_country,
                "hs_code": cleaned_hs,
                "effective_hs": cleaned_hs,
                "ref_date": st.session_state.get("ref_date") or "",
                "status_code": "ERROR",
                "comment": str(exc),
                "program_count": 0,
            }
            st.session_state["fta_explorer_last_programs"] = _PROGRAMS_EMPTY.copy()
            st.error(f"The lookup failed: {exc}")

    # ── Previous requests table ───────────────────────────────────────────────
    st.markdown("### Previous requests")
    st.caption("Click a row to see the duty programs found for that request.")
    history_df = load_fta_explorer_requests()

    selected_history_row: Optional[pd.Series] = None

    if history_df is None or history_df.empty:
        st.info("No previous FTA explorer requests have been saved yet.")
    else:
        history_disp = history_df.copy()
        history_disp = history_disp.sort_values(
            "requested_at", ascending=False, kind="mergesort"
        ).reset_index(drop=True)
        display_cols = [
            c for c in ["requested_at", "country_of_import", "hs_code", "comment", "program_count"]
            if c in history_disp.columns
        ]
        sel = st.dataframe(
            history_disp[display_cols],
            use_container_width=True,
            column_config=_request_col_cfg(display_cols),
            on_select="rerun",
            selection_mode="single-row",
            key=f"fta_history_{st.session_state.fta_explorer_search_count}",
            hide_index=True,
        )
        selected_rows = (sel.get("selection") or {}).get("rows") or []
        if selected_rows:
            row_pos = selected_rows[0]
            if 0 <= row_pos < len(history_disp):
                selected_history_row = history_disp.iloc[row_pos]

    # ── Programs panel ────────────────────────────────────────────────────────
    if selected_history_row is not None:
        requested_hs = str(selected_history_row.get("hs_code") or "")
        raw_payload = selected_history_row.get("payload_json")
        if raw_payload and str(raw_payload) not in ("", "<NA>", "None"):
            try:
                stored_output = json.loads(str(raw_payload))
                programs_df = extract_fta_programs_from_session_output(stored_output)
                effective_hs = get_effective_hs_from_session_output(stored_output, requested_hs)
            except Exception:
                programs_df = _PROGRAMS_EMPTY.copy()
                effective_hs = requested_hs
        else:
            programs_df = _PROGRAMS_EMPTY.copy()
            effective_hs = requested_hs

        hs_label = (
            f"{effective_hs} (alternative for {requested_hs})"
            if effective_hs != requested_hs
            else effective_hs
        )
        label = (
            f"{selected_history_row.get('country_of_import', '')} / "
            f"HS {hs_label} @ "
            f"{selected_history_row.get('requested_at', '')}"
        )
        st.markdown(f"#### Programs for: {label}")
        if programs_df is not None and not programs_df.empty:
            st.dataframe(
                _stripe(programs_df),
                use_container_width=True,
                column_config=_auto_col_cfg(programs_df),
            )
        else:
            st.info("No duty programs were recorded for this request.")

    else:
        last_result = st.session_state.get("fta_explorer_last_result")
        if last_result:
            effective_hs = last_result.get("effective_hs") or last_result["hs_code"]
            requested_hs = last_result["hs_code"]
            hs_label = (
                f"{effective_hs} (alternative for {requested_hs})"
                if effective_hs != requested_hs
                else effective_hs
            )
            st.markdown("### Latest lookup")
            st.write(
                f"Country: **{last_result['country_of_import']}** | "
                f"HS Code: **{hs_label}** | "
                f"Status: **{last_result['status_code']}** | "
                f"Programs: **{last_result['program_count']}**"
            )
            if last_result.get("comment"):
                st.caption(last_result["comment"])
            programs_df = st.session_state.get("fta_explorer_last_programs")
            if programs_df is not None and not programs_df.empty:
                st.dataframe(
                    _stripe(programs_df),
                    use_container_width=True,
                    column_config=_auto_col_cfg(programs_df),
                )
            else:
                st.info("No duty programs were returned for this request.")
