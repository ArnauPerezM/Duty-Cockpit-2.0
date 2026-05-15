import streamlit as st

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
    render_process_auth_gate,
    render_logout_control,
)
from src.db import load_initiatives


def _init_state():
    defaults = {
        # Auth
        "auth_ok": False,
        "e2open_env": "UAT",
        "e2open_username": "",
        "e2open_password": "",
        "e2open_tenant": "",
        # Account
        "account_key": "",
        "account_label": "",
        # Run state
        "run_state": "ready",
        "last_run_id": 0,
        "cancel_requested": False,
        "logs": [],
        "df_preview": None,
        "df_clean": None,
        "df_missing": None,
        "df_failed": None,
        "df_ok": None,
        "df_merged": None,
        "run_summary": None,
        # Duplicate-check flow
        "dup_rows": None,
        "dup_decision": None,
        # DB editor flow
        "db_edit_mode": "view",
        "db_editor_base_df": None,
        "db_inline_changes": None,
        "db_inline_deletes": None,
        "db_corrections_diff": None,
        "db_corrections_errors": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# Safety net: if auth_ok but account_key not yet set
if st.session_state.auth_ok and not st.session_state.account_key:
    _ak = f"{st.session_state.e2open_env}:{st.session_state.e2open_username}:{st.session_state.e2open_tenant}"
    st.session_state.account_key = _ak
    st.session_state.account_label = get_account_label(_ak) or ""

st.markdown(
    """
    <style>
      [data-testid="stSidebar"] {
        background: linear-gradient(
          135deg,
          rgba(70,0,115,0.75) 0%,
          rgba(161,0,255,0.22) 55%,
          rgba(10,14,24,0.95) 100%
        ) !important;
        border-right: 1px solid rgba(194,163,255,0.18);
      }
      [data-testid="stSidebar"] > div:first-child { padding-top: 14px; }
      [data-testid="stSidebar"] h1,
      [data-testid="stSidebar"] h2,
      [data-testid="stSidebar"] h3 { color: rgba(255,255,255,0.92) !important; }
      [data-testid="stSidebar"] .stButton > button {
        border: 1px solid rgba(194,163,255,0.25);
        box-shadow: 0 8px 18px rgba(0,0,0,0.22);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
      .block-container {
        max-width: 100% !important;
        padding-left: 2.2rem !important;
        padding-right: 2.2rem !important;
      }
      h1, h2, h3, h4, h5, h6, p, div, span { text-align: left !important; }
      .hero-wrap, .hero-top, .hero-title, .hero-sub {
        text-align: left !important;
        justify-content: space-between !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

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

render_hero_header(
    title="E2Open Duty Analyzer",
    subtitle="MVP • Streamlit",
    run_state=st.session_state.run_state,
    account_label=st.session_state.account_label,
)

tabs = st.tabs(["Process", "Results", "Opportunities", "Initiatives", "Logs"])

# Auto-navigate to a tab when a drill-down "Show Details" was clicked
if "goto_tab" in st.session_state:
    import streamlit.components.v1 as _stc
    _goto_idx = st.session_state.pop("goto_tab")
    _stc.html(
        f"""<script>
        setTimeout(function(){{
            var t = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
            if (t && t[{_goto_idx}]) t[{_goto_idx}].click();
        }}, 80);
        </script>""",
        height=0,
    )

# ─────────────────────────────────────────────────────────────────────────────
# 1) Process tab — controls rendered inline at top of tab
# ─────────────────────────────────────────────────────────────────────────────

# Safe defaults
uploaded_file   = None
sheet_name      = "Transactions"
ref_date        = ""
analyze_clicked = False
cancel_clicked  = False
df_loaded       = None
load_error      = None
warnings_info   = None
exec_container  = None
post_container  = None

with tabs[0]:
    _ctrl         = render_sidebar_controls()
    uploaded_file   = _ctrl["uploaded_file"]
    sheet_name      = _ctrl["sheet_name"]
    ref_date        = _ctrl["ref_date"]
    analyze_clicked = _ctrl["analyze_clicked"]
    cancel_clicked  = _ctrl["cancel_clicked"]

    if cancel_clicked:
        st.session_state.cancel_requested = True
        st.info("Cancel requested. The run will stop after the current row finishes.")

    # ── Load + validate ───────────────────────────────────────────────────
    if uploaded_file is not None:
        try:
            df_loaded = load_transactions_excel(uploaded_file, sheet_name=sheet_name)
            st.session_state.df_preview = df_loaded
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


# ─────────────────────────────────────────────────────────────────────────────
# 3) Execution helper
# ─────────────────────────────────────────────────────────────────────────────
def _execute_api_run(df_to_run):
    st.session_state.run_state = "running"

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

        except Exception as e:
            status.update(label="Execution failed.", state="error")
            st.session_state.run_state = "failed"
            st.exception(e)


# ─────────────────────────────────────────────────────────────────────────────
# 4) Handle analyze click
# ─────────────────────────────────────────────────────────────────────────────
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
        with tabs[0]:
            with exec_container:
                st.warning("Authentication required. Please connect to E2Open above before running the analysis.")
    elif uploaded_file is None:
        with tabs[0]:
            st.error("Please upload an Excel file before running the analysis.")
    elif load_error:
        with tabs[0]:
            st.error(f"Excel load/validation failed: {load_error}")
    elif st.session_state.df_clean is None or st.session_state.df_clean.empty:
        with tabs[0]:
            st.warning("No candidate rows to process (or all rows are already marked as analyzed).")
    else:
        try:
            dups = find_duplicate_transactions(st.session_state.df_clean, ref_date)
        except Exception as _dup_err:
            with tabs[0]:
                st.warning(f"Duplicate check failed ({_dup_err}). Proceeding without duplicate check.")
            dups = None

        if dups is None or dups.empty:
            _execute_api_run(st.session_state.df_clean)
        else:
            st.session_state.dup_rows  = dups
            st.session_state.run_state = "duplicate_decision"


# ─────────────────────────────────────────────────────────────────────────────
# 5) Duplicate decision UI
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.run_state == "duplicate_decision" and st.session_state.dup_rows is not None:
    with tabs[0]:
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
                st.session_state.dup_decision = "skip"
                _execute_api_run(df_new)
            elif btn_all:
                st.session_state.dup_decision = "all"
                _execute_api_run(st.session_state.df_clean)


# ─────────────────────────────────────────────────────────────────────────────
# 6) Post-run block
# ─────────────────────────────────────────────────────────────────────────────
with tabs[0]:
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
# 7) Results tab
# ─────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    render_tab_resultados(
        df_merged=df_merged_all,
        run_summary=st.session_state.run_summary,
        df_failed=st.session_state.df_failed,
        df_missing=st.session_state.df_missing,
        ref_date=ref_date,
        account_label=st.session_state.account_label,
        environment=st.session_state.e2open_env,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8) Opportunities tab
# ─────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    render_tab_opportunities(df_merged=df_merged_all, df_initiatives=df_initiatives_all)


# ─────────────────────────────────────────────────────────────────────────────
# 9) Initiatives tab
# ─────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    render_tab_initiatives(df_initiatives=df_initiatives_all)


# ─────────────────────────────────────────────────────────────────────────────
# 10) Logs tab
# ─────────────────────────────────────────────────────────────────────────────
_total_queries = get_query_counter(st.session_state.account_key or None)

with tabs[4]:
    render_tab_logs(
        logs=st.session_state.logs,
        run_summary=st.session_state.run_summary,
        run_history=run_history_df,
        total_queries=_total_queries,
    )
