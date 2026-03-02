import streamlit as st
# test
from src.logic import (
    load_transactions_excel,
    validate_and_clean_transactions,
    run_api_loop,
    postprocess_results,
)
from src.ui import (
    render_sidebar_controls,
    render_hero_header,
    render_process_pre,   
    render_process_post,  
    render_tab_resultados,
    render_tab_logs,
)

def _init_state():
    defaults = {
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
        "warnings_gate_ok": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

st.markdown(
    """
    <style>
      /* Sidebar background similar to hero */
      [data-testid="stSidebar"] {
        background: linear-gradient(
          135deg,
          rgba(70,0,115,0.75) 0%,
          rgba(161,0,255,0.22) 55%,
          rgba(10,14,24,0.95) 100%
        ) !important;
        border-right: 1px solid rgba(194,163,255,0.18);
      }

      /* Sidebar padding polish */
      [data-testid="stSidebar"] > div:first-child {
        padding-top: 14px;
      }

      /* Make sidebar headers pop */
      [data-testid="stSidebar"] h1,
      [data-testid="stSidebar"] h2,
      [data-testid="stSidebar"] h3 {
        color: rgba(255,255,255,0.92) !important;
      }

      /* Accent for buttons in sidebar (optional but nice) */
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
      /* Force left alignment everywhere */
      .block-container {
        max-width: 100% !important;
        padding-left: 2.2rem !important;
        padding-right: 2.2rem !important;
      }

      /* Ensure text is left-aligned (some themes center headings) */
      h1, h2, h3, h4, h5, h6, p, div, span {
        text-align: left !important;
      }

      /* Hero: ensure left alignment inside the custom header */
      .hero-wrap, .hero-top, .hero-title, .hero-sub {
        text-align: left !important;
        justify-content: space-between !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar controls
with st.sidebar:
    sidebar = render_sidebar_controls()

uploaded_file = sidebar["uploaded_file"]
sheet_name = sidebar["sheet_name"]
ref_date = sidebar["ref_date"]
continue_hs_warning = sidebar["continue_hs_warning"]
continue_iso_warning = sidebar["continue_iso_warning"]
analyze_clicked = sidebar["analyze_clicked"]
cancel_clicked = sidebar["cancel_clicked"]

render_hero_header(
    title="E2Open Duty Analyzer",
    subtitle="MVP • Streamlit",
    run_state=st.session_state.run_state,
)

if cancel_clicked:
    st.session_state.cancel_requested = True
    st.sidebar.info("Cancel requested. The run will stop after the current row finishes.")

# Create tabs early (so Process tab always shows validation + row summary before execution)
tabs = st.tabs(["Process", "Results", "Logs"])

# -------------------------
# 1) Load + validate (always happens before execution)
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

# Blocking warnings gate logic
warnings_gate_ok = True
if uploaded_file is None:
    st.session_state.run_state = "ready"
elif load_error:
    st.session_state.run_state = "failed"
elif not warnings_gate_ok:
    st.session_state.run_state = "blocked"
else:
    # Ready to run (has file, validated, gate ok)
    # If a previous run exists, keep completed/cancelled/failed as-is.
    if st.session_state.run_state not in ("completed", "cancelled", "failed", "running"):
        st.session_state.run_state = "ready"

if warnings_info is not None:
    if warnings_info.get("hs_ratio_ok") is False:
        warnings_gate_ok = warnings_gate_ok and continue_hs_warning
    if warnings_info.get("iso_ratio_ok") is False:
        warnings_gate_ok = warnings_gate_ok and continue_iso_warning

st.session_state.warnings_gate_ok = warnings_gate_ok

# -------------------------
# 2) Process tab: render validation + row summary + candidates BEFORE execution
# -------------------------
with tabs[0]:
    render_process_pre(
        uploaded_file=uploaded_file,
        sheet_name=sheet_name,
        load_error=load_error,
        df_clean=st.session_state.df_clean,
        df_missing=st.session_state.df_missing,
        warnings_info=warnings_info,
        continue_hs_warning=continue_hs_warning,
        continue_iso_warning=continue_iso_warning,
        warnings_gate_ok=warnings_gate_ok,
    )

    # Execution area placeholder (always below the pre-run sections)
    exec_container = st.container()

    # Post-run area placeholder (always after execution)
    post_container = st.container()

# -------------------------
# 3) Execution (runs only when button clicked; displayed inside Process tab BELOW pre-run sections)
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

    if uploaded_file is None:
        with tabs[0]:
            st.error("Please upload an Excel file before running the analysis.")
    elif load_error:
        with tabs[0]:
            st.error(f"Excel load/validation failed: {load_error}")
    elif st.session_state.df_clean is None or st.session_state.df_clean.empty:
        with tabs[0]:
            st.warning("No candidate rows to process (or all rows are already marked as analyzed).")
    elif not warnings_gate_ok:
        with tabs[0]:
            st.warning("Blocking warnings are not acknowledged. Enable the relevant 'Continue' toggles to proceed.")
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

                failed_df, ok_df, logs = run_api_loop(
                    df_in=st.session_state.df_clean,
                    ref_date=ref_date,
                    progress_cb=progress_cb,
                    should_cancel=should_cancel,
                )

                st.session_state.logs = logs
                st.session_state.df_failed = failed_df
                st.session_state.df_ok = ok_df

                processed = int(ok_df.shape[0] + failed_df.shape[0])
                missing_n = int(st.session_state.df_missing.shape[0]) if st.session_state.df_missing is not None else 0

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

            except Exception as e:
                status.update(label="Execution failed.", state="error")
                st.session_state.run_state = "failed"
                st.exception(e)

       
# If there is already a previous run in session_state, still show the post-run block even without rerunning
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
# 4) Other tabs
# -------------------------
with tabs[1]:
    render_tab_resultados(df_merged=st.session_state.df_merged, run_summary=st.session_state.run_summary)

with tabs[2]:
    render_tab_logs(logs=st.session_state.logs, run_summary=st.session_state.run_summary)
