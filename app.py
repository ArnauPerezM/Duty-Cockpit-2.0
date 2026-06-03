import streamlit as st

from src.state import init_session_state
from src.logic import (
    load_transactions_excel,
    validate_and_clean_transactions,
    run_api_loop,
    postprocess_results,
)
from src.db import (
    save_run_results,
    load_merged_results,
    get_run_history,
    get_account_label,
    get_query_counter,
    find_duplicate_transactions,
)
from src.ui import (
    render_sidebar_controls,
    render_sidebar_filters,
    render_hero_header,
    render_process_pre,
    render_process_post,
    render_tab_resultados,
    render_tab_opportunities,
    render_tab_initiatives,
    render_tab_logs,
    render_tab_reporting,
    render_process_auth_gate,
    render_logout_control,
)
from src.ui_shared import load_custom_css
from src.db import load_initiatives, init_db
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
    title="Duty Analyzer",
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
        st.session_state.cancel_requested = True
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

    if uploaded_file is None:
        st.session_state.run_state = "ready"
    elif load_error:
        st.session_state.run_state = "failed"
    else:
        if st.session_state.run_state not in (
            "completed", "cancelled", "failed", "running", "duplicate_decision"
        ):
            st.session_state.run_state = "ready"

    render_process_pre(
        uploaded_file=uploaded_file,
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
    def _execute_api_run(df_to_run):
        st.session_state.run_state = "running"
        _needs_rerun = False

        with exec_container:
            st.subheader("Execution")
            status = st.status("Starting E2Open session and processing rows...", expanded=True)
            progress_bar = st.progress(0)

            total_to_run = len(df_to_run)

            def progress_cb(i: int, total_n: int, msg: str):
                if total_n > 0:
                    progress_bar.progress(min(i / total_n, 1.0))
                status.write(msg)

            def should_cancel() -> bool:
                return bool(st.session_state.cancel_requested)

            try:
                status.update(label="Running API calls...", state="running")

                # DEPLOYMENT_NOTE: credentials are read from st.session_state (plain text,
                # in-process). Safe for local PyInstaller exe (single-user, no network
                # exposure). For any hosted deployment use st.secrets instead:
                #   https://docs.streamlit.io/develop/concepts/connections/secrets-management
                _credentials = {
                    "username": st.session_state.e2open_username,
                    "password": st.session_state.e2open_password,
                    "tenant":   st.session_state.e2open_tenant,
                    "environment": st.session_state.e2open_env,
                }
                failed_df, ok_df, logs = run_api_loop(
                    df_in=df_to_run,
                    ref_date=ref_date,
                    credentials=_credentials,
                    progress_cb=progress_cb,
                    should_cancel=should_cancel,
                )

                st.session_state.logs     = logs
                st.session_state.df_failed = failed_df
                st.session_state.df_ok    = ok_df

                processed  = int(ok_df.shape[0] + failed_df.shape[0])
                missing_n  = (int(st.session_state.df_missing.shape[0])
                              if st.session_state.df_missing is not None else 0)

                _account_key   = st.session_state.account_key   or None
                _account_label = st.session_state.account_label or None
                _environment   = st.session_state.e2open_env    or None

                if should_cancel():
                    status.update(label="Cancelled by user.", state="error")
                    st.session_state.run_state = "cancelled"
                    st.session_state.run_summary = {
                        "cancelled": True,
                        "processed": processed,
                        "ok": int(ok_df.shape[0]),
                        "failed": int(failed_df.shape[0]),
                        "missing": missing_n,
                        "total_candidates": total_to_run,
                    }
                    try:
                        save_run_results(
                            ok_df, failed_df, None, ref_date,
                            st.session_state.run_summary,
                            account_key=_account_key,
                            account_label=_account_label,
                            environment=_environment,
                        )
                    except Exception as db_err:
                        st.warning(f"DB save failed (cancelled run): {db_err}")
                else:
                    df_merged = postprocess_results(
                        ok_input_df=df_to_run,
                        ok_df=ok_df,
                        failed_df=failed_df,
                        df_missing=st.session_state.df_missing,
                        ref_date=ref_date,
                        logs=logs,
                    )
                    st.session_state.df_merged = df_merged

                    status.update(label="Analysis completed.", state="complete")
                    st.session_state.run_state = "completed"
                    st.session_state.run_summary = {
                        "cancelled": False,
                        "processed": processed,
                        "ok": int(ok_df.shape[0]),
                        "failed": int(failed_df.shape[0]),
                        "missing": missing_n,
                        "total_candidates": total_to_run,
                    }
                    try:
                        save_run_results(
                            ok_df, failed_df, df_merged, ref_date,
                            st.session_state.run_summary,
                            account_key=_account_key,
                            account_label=_account_label,
                            environment=_environment,
                        )
                    except Exception as db_err:
                        st.warning(f"DB save failed: {db_err}")
                    _needs_rerun = True

            except Exception as e:
                status.update(label="Execution failed.", state="error")
                st.session_state.run_state = "failed"
                st.exception(e)

        if _needs_rerun:
            st.rerun()

    # ── Handle analyze click ──────────────────────────────────────────────
    if analyze_clicked:
        st.session_state.last_run_id   += 1
        st.session_state.cancel_requested = False
        st.session_state.logs          = []
        st.session_state.df_merged     = None
        st.session_state.df_failed     = None
        st.session_state.df_ok         = None
        st.session_state.run_summary   = None
        st.session_state.dup_rows      = None
        st.session_state.dup_decision  = None
        st.session_state.run_state     = "ready"
        st.session_state.db_edit_mode  = "view"
        st.session_state.db_editor_base_df = None

        if not st.session_state.auth_ok:
            with exec_container:
                st.warning("Authentication required. Please connect to E2Open above before running the analysis.")
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
                st.warning(f"Duplicate check failed ({_dup_err}). Proceeding without duplicate check.")
                dups = None

            if dups is None or dups.empty:
                _execute_api_run(st.session_state.df_clean)
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
                f"**{dup_n} of {total_n} transactions** have already been sent to E2Open "
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
                _execute_api_run(df_new)
            elif btn_all:
                _execute_api_run(st.session_state.df_clean)

    # ── Post-run block ────────────────────────────────────────────────────
    if st.session_state.run_summary is not None:
        with post_container:
            render_process_post(
                df_clean=st.session_state.df_clean,
                df_missing=st.session_state.df_missing,
                df_failed=st.session_state.df_failed,
                df_ok=st.session_state.df_ok,
                df_merged=st.session_state.df_merged,
                run_summary=st.session_state.run_summary,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Results tab
# ─────────────────────────────────────────────────────────────────────────────
elif active_tab == "Results":
    render_tab_resultados(df_merged=df_merged_all)


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
