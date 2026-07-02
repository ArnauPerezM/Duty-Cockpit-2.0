from __future__ import annotations

from typing import Any

import streamlit as st

DEFAULT_STATE: dict[str, Any] = {
    # Auth
    "auth_ok": False,
    "e2open_env": "UAT",
    "e2open_username": "",
    "e2open_password": "",
    "e2open_tenant": "",
    # Account
    "account_key": "",
    "account_label": "",
    # Run lifecycle
    "run_state": "ready",
    "last_run_id": 0,
    "logs": [],
    "df_clean": None,
    "df_missing": None,
    "df_failed": None,
    "df_ok": None,
    "df_merged": None,
    "run_summary": None,
    # Duplicate-check flow
    "dup_rows": None,
    "dup_check_error": None,
    # Executed subset (may differ from df_clean when duplicates are skipped)
    "df_executed": None,
    # DB save error (set when API succeeded but DB persistence failed)
    "db_save_error": None,
    # DB editor flow
    "db_edit_mode": "view",
    "db_editor_base_df": None,
    "db_inline_changes": None,
    "db_inline_deletes": None,
    "db_corrections_diff": None,
    "db_corrections_errors": None,
    # Navigation
    "active_tab": "Process",
    # Sidebar filters
    "sf_date_from": None,
    "sf_date_to": None,
    "sf_coo": [],
    "sf_coi": [],
    "sf_hs": [],
    "sf_material": [],
}


def init_session_state() -> None:
    for key, default in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default
