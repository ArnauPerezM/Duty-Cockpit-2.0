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
)
from src.ui import (
    render_sidebar_controls,
    render_hero_header,
    render_process_pre,
    render_process_post,
    render_tab_resultados,
    render_tab_logs,
    render_process_auth_gate,
    render_logout_control,
)


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
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# Safety net: if auth_ok but account_key not yet set (e.g. after hot reload)
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

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    sidebar = render_sidebar_controls()
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

uploaded_file = sidebar["uploaded_file"]
sheet_name = sidebar["sheet_name"]
ref_date = sidebar["ref_date"]
analyze_clicked = sidebar["analyze_clicked"]
cancel_clicked = sidebar["cancel_clicked"]

render_hero_header(
    title="E2Open Duty Analyzer",
    subtitle="MVP • Streamlit",
    run_state=st.session_state.run_state,
    account_label=st.session_state.account_label,
)

if cancel_clicked:
    st.session_state.cancel_requested = True
    st.sidebar.info("Cancel requested. The run will stop after the current row finishes.")

tabs = st.tabs(["Process", "Results", "Logs"])

# -------------------------
# 1) Load + validate
# -------------------------
df_loaded = None
load_error = None
warnings_info = None

if uploaded_file is not None:
    try:
        df_loaded = load_transactions_excel(uploaded_file, sheet_name=sheet_name)
        st.session_state.df_preview = df_loaded
    except Exception as e:
        load_error = str(e)

if df_loaded is not None and load_error is None:
    try:
        df_clean, df_missing, warnings_info = validate_and_clean_transactions(df_loaded)
        st.session_state.df_clean = df_clean
        st.session_state.df_missing = df_missing
    except Exception as e:
        load_error = str(e)

if uploaded_file is None:
    st.session_state.run_state = "ready"
elif load_error:
    st.session_state.run_state = "failed"
else:
    if st.session_state.run_state not in ("completed", "cancelled", "failed", "running"):
        st.session_state.run_state = "ready"

# -------------------------
# 2) Process tab
# -------------------------
with tabs[0]:
    render_process_pre(
        uploaded_file=uploaded_file,
        sheet_name=sheet_name,
        load_error=load_error,
        df_clean=st.session_state.df_clean,
        df_missing=st.session_state.df_missing,
        warnings_info=warnings_info,
    )

    # Auth gate — only if not connected
    if not st.session_state.auth_ok:
        render_process_auth_gate()

    exec_container = st.container()
    post_container = st.container()

# -------------------------
# 3) Execution
# -------------------------
if analyze_clicked:
    st.session_state.last_run_id += 1
    st.session_state.cancel_requested = False
    st.session_state.logs = []
    st.session_state.df_merged = None
    st.session_state.df_failed = None
    st.session_state.df_ok = None
    st.session_state.run_summary = None
    st.session_state.run_state = "running"

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
        with exec_container:
            st.subheader("Execution")
            status = st.status("Starting E2Open session and processing rows...", expanded=True)
            progress_bar = st.progress(0)

            total = len(st.session_state.df_clean)

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
                    "tenant": st.session_state.e2open_tenant,
                    "environment": st.session_state.e2open_env,
                }
                failed_df, ok_df, logs = run_api_loop(
                    df_in=st.session_state.df_clean,
                    ref_date=ref_date,
                    credentials=_credentials,
                    progress_cb=progress_cb,
                    should_cancel=should_cancel,
                )

                st.session_state.logs = logs
                st.session_state.df_failed = failed_df
                st.session_state.df_ok = ok_df

                processed = int(ok_df.shape[0] + failed_df.shape[0])
                missing_n = int(st.session_state.df_missing.shape[0]) if st.session_state.df_missing is not None else 0

                _account_key = st.session_state.account_key or None
                _account_label = st.session_state.account_label or None
                _environment = st.session_state.e2open_env or None

                if should_cancel():
                    status.update(label="Cancelled by user.", state="error")
                    st.session_state.run_state = "cancelled"
                    st.session_state.run_summary = {
                        "cancelled": True,
                        "processed": processed,
                        "ok": int(ok_df.shape[0]),
                        "failed": int(failed_df.shape[0]),
                        "missing": missing_n,
                        "total_candidates": int(total),
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
                        ok_input_df=st.session_state.df_clean,
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
                        "total_candidates": int(total),
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

# Post-run block
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

# -------------------------
# 4) Results tab
# -------------------------
df_merged_all = load_merged_results()
run_history_df = get_run_history()

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

# -------------------------
# 5) Logs tab
# -------------------------
_total_queries = get_query_counter(st.session_state.account_key or None)

with tabs[2]:
    render_tab_logs(
        logs=st.session_state.logs,
        run_summary=st.session_state.run_summary,
        run_history=run_history_df,
        total_queries=_total_queries,
    )
