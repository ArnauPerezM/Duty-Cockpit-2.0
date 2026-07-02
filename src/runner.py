"""Background thread runner — keeps the E2Open API loop alive across Streamlit reruns.

The module holds a single global _STATE dict that the worker thread writes to
and the Streamlit UI reads from on every rerun.  Because this is a single-user
local desktop app there is at most one run in-flight at any time.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import pandas as pd

_lock = threading.Lock()
_STATE: Dict[str, Any] = {
    "status":   "idle",   # idle | running | completed | cancelled | failed | completed_db_failed
    "current":  0,
    "total":    0,
    "last_msg": "",
    "cancel":   False,
    "payload":  None,     # filled when run finishes; dict with results
}
_thread: Optional[threading.Thread] = None


# ── Public read/control API ───────────────────────────────────────────────────

def get_state() -> Dict[str, Any]:
    """Return a snapshot copy of the current run state (thread-safe)."""
    with _lock:
        return dict(_STATE)


def request_cancel() -> None:
    """Signal the running worker to stop after the current row."""
    with _lock:
        _STATE["cancel"] = True


# ── Internal helpers ──────────────────────────────────────────────────────────

def _update(**kwargs) -> None:
    with _lock:
        _STATE.update(kwargs)


def _should_cancel() -> bool:
    with _lock:
        return bool(_STATE.get("cancel"))


# ── Launch ────────────────────────────────────────────────────────────────────

def start(
    df_to_run: pd.DataFrame,
    ref_date: str,
    credentials: Dict[str, str],
    df_missing: Optional[pd.DataFrame],
    account_key: Optional[str],
    account_label: Optional[str],
    environment: Optional[str],
) -> None:
    """Launch the API loop in a daemon background thread and return immediately."""
    global _thread

    total = len(df_to_run)

    with _lock:
        _STATE.update({
            "status":   "running",
            "current":  0,
            "total":    total,
            "last_msg": "Starting e2open session...",
            "cancel":   False,
            "payload":  None,
        })

    # Copy everything the thread needs upfront — reading st.session_state from
    # a non-Streamlit thread is not safe.
    _df      = df_to_run.copy()
    _missing = df_missing.copy() if df_missing is not None else pd.DataFrame()

    def _progress_cb(i: int, n: int, msg: str) -> None:
        with _lock:
            _STATE["current"]  = i
            _STATE["total"]    = n
            _STATE["last_msg"] = msg

    def _worker() -> None:
        from src.logic import run_api_loop, postprocess_results
        from src.db   import save_run_results

        try:
            failed_df, ok_df, logs = run_api_loop(
                df_in=_df,
                ref_date=ref_date,
                credentials=credentials,
                progress_cb=_progress_cb,
                should_cancel=_should_cancel,
            )

            processed = int(ok_df.shape[0] + failed_df.shape[0])
            missing_n = int(_missing.shape[0])

            _finish(
                    _df, ok_df, failed_df, logs, _missing,
                    processed, missing_n, total,
                    ref_date, account_key, account_label, environment,
                    cancelled=_should_cancel(),
                )

        except Exception as exc:
            _update(status="failed", payload={"error": str(exc)})

    _thread = threading.Thread(target=_worker, daemon=True, name="e2open-runner")
    _thread.start()


# ── Finish helper (called from worker thread) ─────────────────────────────────

def _finish(_df, ok_df, failed_df, logs, _missing,
            processed, missing_n, total,
            ref_date, account_key, account_label, environment,
            *, cancelled: bool):
    from src.logic import postprocess_results
    from src.db   import save_run_results

    df_merged = None
    if cancelled:
        # Postprocess whatever rows completed before the cancel so they appear
        # in Results/Reporting and are flagged as duplicates on the next run.
        if not ok_df.empty:
            try:
                df_merged = postprocess_results(
                    ok_input_df=_df, ok_df=ok_df, failed_df=failed_df,
                    df_missing=_missing, ref_date=ref_date, logs=logs,
                )
            except Exception:
                pass  # postprocess failure must not block the cancel path
    else:
        df_merged = postprocess_results(
            ok_input_df=_df, ok_df=ok_df, failed_df=failed_df,
            df_missing=_missing, ref_date=ref_date, logs=logs,
        )

    run_summary = {
        "cancelled":        cancelled,
        "processed":        processed,
        "ok":               int(ok_df.shape[0]),
        "failed":           int(failed_df.shape[0]),
        "missing":          missing_n,
        "total_candidates": total,
    }
    db_save_error = None
    final_status  = "cancelled" if cancelled else "completed"
    try:
        save_run_results(
            ok_df, failed_df, df_merged, ref_date, run_summary,
            account_key=account_key,
            account_label=account_label,
            environment=environment,
        )
    except Exception as db_err:
        db_save_error = str(db_err)
        if not cancelled:
            final_status = "completed_db_failed"

    _update(status=final_status, payload={
        "failed_df":     failed_df,
        "ok_df":         ok_df,
        "logs":          logs,
        "df_merged":     df_merged,
        "run_summary":   run_summary,
        "db_save_error": db_save_error,
    })
