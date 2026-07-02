import time

import streamlit as st

import src.runner as runner
from src.state import init_session_state
from src.logic import (
    load_transactions_excel,
    validate_and_clean_transactions,
)
from src.db import (
    load_merged_results,
    get_run_history,
    get_account_label,
    get_query_counter,
    find_duplicate_transactions,
    load_initiatives,
    init_db,
)
from src.ui_shared import (
    load_custom_css,
    render_hero_header,
    render_sidebar_controls,
    render_sidebar_filters,
    render_process_auth_gate,
    render_logout_control,
)
from src.ui_process import render_process_pre, render_process_post
from src.ui_results import render_tab_results
from src.ui_opportunities import render_tab_opportunities
from src.ui_initiatives import render_tab_initiatives
from src.ui_logs import render_tab_logs
from src.ui_reporting import render_tab_reporting
from src.ui_help import render_help_dialog


init_session_state()
init_db()   # initialize schema once at startup — all subsequent calls are no-ops
load_custom_css()

# Safety net: if auth_ok but account_key not yet set
if st.session_state.auth_ok and not st.session_state.account_key:
    _ak = f"{st.session_state.e2open_env}:{st.session_state.e2open_username}:{st.session_state.e2open_tenant}"
    st.session_state.account_key = _ak
    st.session_state.account_label = get_account_label(_ak) or ""


# ─────────────────────────────────────────────────────────────────────────────
# Load data early — needed for the sidebar filter panel
# ─────────────────────────────────────────────────────────────────────────────
df_merged_all    = load_merged_results()
df_initiatives_all = load_initiatives()
run_history_df   = get_run_history()

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — always shows the filter panel (not the process controls)
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_filters(df_merged_all)
    if st.session_state.auth_ok:
        if render_logout_control():
            st.session_state.auth_ok = False
            st.session_state.e2open_env = "UAT"
            st.session_state.e2open_username = ""
            st.session_state.e2open_password = ""
            st.session_state.e2open_tenant = ""
            st.session_state.account_key = ""
            st.session_state.account_label = ""
            st.rerun()

if render_hero_header(
    title="Duty Optimizer",
    subtitle="",
    run_state=st.session_state.run_state,
    account_label=st.session_state.account_label,
):
    render_help_dialog()

# ─────────────────────────────────────────────────────────────────────────────
# Tab navigation — controlled by st.session_state.active_tab so reruns
# preserve the selected tab (st.tabs has no native way to set the active tab,
# so a button click in any tab would otherwise snap back to the first tab).
# ─────────────────────────────────────────────────────────────────────────────
TAB_LABELS = ["Process", "Results", "Opportunities", "Initiatives", "Logs", "Reporting"]

with st.container(key="duty_tab_nav"):
    st.radio(
        "Section",
        options=TAB_LABELS,
        horizontal=True,
        label_visibility="collapsed",
        key="active_tab",
    )

active_tab = st.session_state.active_tab or "Process"

# Ref date is needed in multiple tabs (e.g. Reporting download). Persist via
# session_state so it survives switching to other tabs.
ref_date = st.session_state.get("ref_date", "")


# ─────────────────────────────────────────────────────────────────────────────
# Process tab
# ─────────────────────────────────────────────────────────────────────────────
if active_tab == "Process":
    # ── Sync background thread → session_state (must run first) ──────────
    # When the worker thread finishes while the user is on another tab,
    # session_state.run_state is still "running".  Detect the transition
    # here before anything else can reset it, and copy the payload in.
    _rs = runner.get_state()
    if st.session_state.run_state == "running" and _rs["status"] != "running":
        _p = _rs.get("payload") or {}
        st.session_state.df_failed     = _p.get("failed_df")
        st.session_state.df_ok         = _p.get("ok_df")
        st.session_state.logs          = _p.get("logs") or []
        st.session_state.df_merged     = _p.get("df_merged")
        st.session_state.run_summary   = _p.get("run_summary")
        st.session_state.db_save_error = _p.get("db_save_error")
        st.session_state.run_state     = _rs["status"]
        st.rerun()  # re-render with final state (updates hero header etc.)

    # Safe defaults
    uploaded_file   = None
    sheet_name      = "Transactions"
    analyze_clicked = False
    cancel_clicked  = False
    df_loaded       = None
    load_error      = None
    warnings_info   = None

    _ctrl         = render_sidebar_controls()
    uploaded_file   = _ctrl["uploaded_file"]
    sheet_name      = _ctrl["sheet_name"]
    ref_date        = _ctrl["ref_date"]
    analyze_clicked = _ctrl["analyze_clicked"]
    cancel_clicked  = _ctrl["cancel_clicked"]
    st.session_state["ref_date"] = ref_date  # share with Reporting tab

    if cancel_clicked:
        runner.request_cancel()
        st.info("Cancel requested. The run will stop after the current row finishes.")

    # ── Load + validate ───────────────────────────────────────────────────
    if uploaded_file is not None:
        try:
            df_loaded = load_transactions_excel(uploaded_file, sheet_name=sheet_name)
        except Exception as e:
            load_error = str(e)

    if df_loaded is not None and load_error is None:
        try:
            df_clean, df_missing, warnings_info = validate_and_clean_transactions(df_loaded)
            st.session_state.df_clean   = df_clean
            st.session_state.df_missing = df_missing
        except Exception as e:
            load_error = str(e)

    # Guard: don't reset run_state to "ready" when a run is active/finished.
    # The file uploader loses its widget state when the user visits another tab,
    # so uploaded_file is None on return even though the run is still live.
    _active_states = {
        "running", "completed", "cancelled", "failed",
        "completed_db_failed", "duplicate_decision", "duplicate_check_failed",
    }
    if uploaded_file is None:
        if st.session_state.run_state not in _active_states:
            st.session_state.run_state = "ready"
    elif load_error:
        st.session_state.run_state = "failed"
    else:
        if st.session_state.run_state not in _active_states:
            st.session_state.run_state = "ready"

    # When the file uploader has lost its state but we still have validated
    # data in session_state (e.g. user switched tabs mid-run), pass a truthy
    # sentinel so render_process_pre shows the row summary instead of the
    # "Upload an Excel file" prompt.
    _display_file = uploaded_file or (
        True if st.session_state.df_clean is not None
             and st.session_state.run_state in _active_states
        else None
    )
    render_process_pre(
        uploaded_file=_display_file,
        sheet_name=sheet_name,
        load_error=load_error,
        df_clean=st.session_state.df_clean,
        df_missing=st.session_state.df_missing,
        warnings_info=warnings_info,
    )

    if not st.session_state.auth_ok:
        render_process_auth_gate()

    exec_container = st.container()
    post_container = st.container()

    # ── Execution helper ──────────────────────────────────────────────────
    # DEPLOYMENT_NOTE: credentials are read from st.session_state (plain text,
    # in-process). Safe for local PyInstaller exe (single-user, no network
    # exposure). For any hosted deployment use st.secrets instead:
    #   https://docs.streamlit.io/develop/concepts/connections/secrets-management
    def _start_api_run(df_to_run):
        st.session_state.df_executed = df_to_run.copy()
        st.session_state.run_state   = "running"
        runner.start(
            df_to_run=df_to_run,
            ref_date=ref_date,
            credentials={
                "username":    st.session_state.e2open_username,
                "password":    st.session_state.e2open_password,
                "tenant":      st.session_state.e2open_tenant,
                "environment": st.session_state.e2open_env,
            },
            df_missing=st.session_state.df_missing,
            account_key=st.session_state.account_key   or None,
            account_label=st.session_state.account_label or None,
            environment=st.session_state.e2open_env    or None,
        )
        st.rerun()

    # ── Handle analyze click ──────────────────────────────────────────────
    if analyze_clicked:
        st.session_state.last_run_id   += 1
        st.session_state.logs          = []
        st.session_state.df_merged     = None
        st.session_state.df_failed     = None
        st.session_state.df_ok         = None
        st.session_state.df_executed   = None
        st.session_state.run_summary   = None
        st.session_state.dup_rows      = None
        st.session_state.dup_check_error = None
        st.session_state.db_save_error = None
        st.session_state.run_state     = "ready"
        st.session_state.db_edit_mode  = "view"
        st.session_state.db_editor_base_df = None

        if not st.session_state.auth_ok:
            with exec_container:
                st.warning("Authentication required. Please connect to e2open above before running the analysis.")
        elif uploaded_file is None:
            st.error("Please upload an Excel file before running the analysis.")
        elif load_error:
            st.error(f"Excel load/validation failed: {load_error}")
        elif st.session_state.df_clean is None or st.session_state.df_clean.empty:
            st.warning("No candidate rows to process (or all rows are already marked as analyzed).")
        else:
            try:
                dups = find_duplicate_transactions(st.session_state.df_clean, ref_date)
            except Exception as _dup_err:
                st.session_state.run_state = "duplicate_check_failed"
                st.session_state.dup_check_error = str(_dup_err)
                dups = None

            if st.session_state.run_state != "duplicate_check_failed":
                if dups is None or dups.empty:
                    _start_api_run(st.session_state.df_clean)
                else:
                    st.session_state.dup_rows  = dups
                    st.session_state.run_state = "duplicate_decision"

    # ── Duplicate decision UI ─────────────────────────────────────────────
    if st.session_state.run_state == "duplicate_decision" and st.session_state.dup_rows is not None:
        with exec_container:
            dup_n   = len(st.session_state.dup_rows)
            total_n = len(st.session_state.df_clean) if st.session_state.df_clean is not None else 0
            new_n   = total_n - dup_n

            st.warning(
                f"**{dup_n} of {total_n} transactions** have already been sent to e2open "
                f"with this reference date. **{new_n} new** transactions remain unsent."
            )

            show_cols = [c for c in ["invoice number", "material number", "coo", "coi",
                                     "hs code", "customs value", "duty paid"]
                         if c in st.session_state.dup_rows.columns]
            with st.expander(f"View {dup_n} duplicate transactions", expanded=False):
                st.dataframe(st.session_state.dup_rows[show_cols], width='stretch')

            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                btn_skip = st.button(
                    f"Skip duplicates — send {new_n} new",
                    type="primary", key="dup_btn_skip", disabled=(new_n == 0),
                )
            with col2:
                btn_all = st.button(f"Reprocess all — send {total_n}", key="dup_btn_all")
            with col3:
                btn_cancel = st.button("Cancel", key="dup_btn_cancel")

            if btn_cancel:
                st.session_state.run_state = "ready"
                st.session_state.dup_rows  = None
                st.rerun()
            elif btn_skip:
                dup_idx = set(st.session_state.dup_rows.index)
                df_new = st.session_state.df_clean[
                    ~st.session_state.df_clean.index.isin(dup_idx)
                ].copy()
                _start_api_run(df_new)
            elif btn_all:
                _start_api_run(st.session_state.df_clean)

    # ── Duplicate-check failure UI ────────────────────────────────────────
    if st.session_state.run_state == "duplicate_check_failed":
        with exec_container:
            st.error(
                f"**Duplicate check failed** — could not query the database before running the API.\n\n"
                f"Error: `{st.session_state.dup_check_error}`\n\n"
                "The API run has been blocked. You can either fix the issue and retry, or "
                "explicitly proceed without duplicate protection."
            )
            col1, col2 = st.columns([3, 1])
            with col1:
                btn_proceed = st.button(
                    "Proceed without duplicate check",
                    type="primary", key="dup_fail_proceed",
                )
            with col2:
                btn_abort = st.button("Cancel", key="dup_fail_cancel")

            if btn_abort:
                st.session_state.run_state = "ready"
                st.session_state.dup_check_error = None
                st.rerun()
            elif btn_proceed:
                st.session_state.run_state = "ready"
                st.session_state.dup_check_error = None
                _start_api_run(st.session_state.df_clean)

    # ── Running progress (visible while thread is active) ─────────────────
    if st.session_state.run_state == "running":
        _rs_now = runner.get_state()
        with exec_container:
            st.subheader("Execution")
            _cur = _rs_now["current"]
            _tot = _rs_now["total"]
            st.progress(min(_cur / _tot, 1.0) if _tot > 0 else 0)
            _msg = _rs_now.get("last_msg", "")
            st.caption(f"Row {_cur} / {_tot}" + (f" — {_msg}" if _msg else ""))

    # ── Post-run block ────────────────────────────────────────────────────
    if st.session_state.run_summary is not None:
        with post_container:
            _db_err = st.session_state.get("db_save_error")
            if _db_err:
                st.warning(
                    f"**Results are in memory only** — the database save failed and this run "
                    f"has not been persisted.\n\nError: `{_db_err}`"
                )
            _df_executed = st.session_state.get("df_executed")
            _df_for_post = _df_executed if _df_executed is not None else st.session_state.df_clean
            render_process_post(
                df_clean=_df_for_post,
                df_missing=st.session_state.df_missing,
                df_failed=st.session_state.df_failed,
                df_ok=st.session_state.df_ok,
                df_merged=st.session_state.df_merged,
                run_summary=st.session_state.run_summary,
            )

    # ── Poll while the background thread is running ───────────────────────
    if st.session_state.run_state == "running":
        time.sleep(0.5)
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Results tab
# ─────────────────────────────────────────────────────────────────────────────
elif active_tab == "Results":
    render_tab_results(df_merged=df_merged_all)


# ─────────────────────────────────────────────────────────────────────────────
# Opportunities tab
# ─────────────────────────────────────────────────────────────────────────────
elif active_tab == "Opportunities":
    render_tab_opportunities(df_merged=df_merged_all, df_initiatives=df_initiatives_all)


# ─────────────────────────────────────────────────────────────────────────────
# Initiatives tab
# ─────────────────────────────────────────────────────────────────────────────
elif active_tab == "Initiatives":
    render_tab_initiatives(df_initiatives=df_initiatives_all)


# ─────────────────────────────────────────────────────────────────────────────
# Logs tab
# ─────────────────────────────────────────────────────────────────────────────
elif active_tab == "Logs":
    _total_queries = get_query_counter(st.session_state.account_key or None)
    render_tab_logs(
        logs=st.session_state.logs,
        run_summary=st.session_state.run_summary,
        run_history=run_history_df,
        total_queries=_total_queries,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reporting tab
# ─────────────────────────────────────────────────────────────────────────────
elif active_tab == "Reporting":
    render_tab_reporting(
        df_merged=df_merged_all,
        df_initiatives=df_initiatives_all,
        df_failed=st.session_state.df_failed,
        df_missing=st.session_state.df_missing,
        run_summary=st.session_state.run_summary,
        ref_date=ref_date,
        account_label=st.session_state.account_label,
        environment=st.session_state.e2open_env,
    )
