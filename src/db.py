from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_db_path() -> Path:
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "duty_cockpit.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_INITIATIVES_DDL = """
CREATE TABLE IF NOT EXISTS initiatives (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    coo                 TEXT,
    coi                 TEXT,
    hs_code             TEXT,
    customs_value       REAL,
    duty_paid           REAL,
    default_duties      REAL,
    min_duties          REAL,
    potential_savings   REAL,
    annual_savings_est  REAL,
    savings_realized    REAL DEFAULT 0,
    reimbursements      REAL DEFAULT 0,
    status              TEXT DEFAULT 'Identified',
    product             TEXT,
    program_description TEXT,
    created_at          TEXT NOT NULL
);
"""

_DDL = """
CREATE TABLE IF NOT EXISTS account_labels (
    account_key     TEXT PRIMARY KEY,
    label           TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_date            TEXT    NOT NULL,
    started_at          TEXT    NOT NULL,
    total_candidates    INTEGER,
    total_ok            INTEGER,
    total_failed        INTEGER,
    total_missing       INTEGER,
    cancelled           INTEGER DEFAULT 0,
    account_key         TEXT,
    account_label       TEXT,
    environment         TEXT
);

CREATE TABLE IF NOT EXISTS ok_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    ref_date        TEXT,
    coo             TEXT,
    coi             TEXT,
    hs_code         TEXT,
    customs_value   REAL,
    cv_currency     TEXT,
    weight          REAL,
    status          TEXT,
    comment         TEXT,
    saved_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS failed_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES runs(id),
    ref_date        TEXT,
    coo             TEXT,
    coi             TEXT,
    hs_code         TEXT,
    customs_value   REAL,
    cv_currency     TEXT,
    weight          REAL,
    error           TEXT,
    saved_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS merged_results (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                          INTEGER NOT NULL REFERENCES runs(id),
    ref_date                        TEXT,
    date                            TEXT,
    invoice_number                  TEXT,
    material_number                 TEXT,
    coo                             TEXT,
    coi                             TEXT,
    hs_code                         TEXT,
    customs_value                   REAL,
    cv_currency                     TEXT,
    weight                          REAL,
    duty_paid                       REAL,
    dp_currency                     TEXT,
    status                          TEXT,
    comment                         TEXT,
    hs_alternative                  TEXT,
    calc_name                       TEXT,
    inco_calc_basis                 TEXT,
    min_duty_program                TEXT,
    min_duty_rate                   REAL,
    min_duty_program_description    TEXT,
    minimum_duties                  REAL,
    currency_min_duties             TEXT,
    default_duty_program            TEXT,
    default_duty_rate               REAL,
    default_duty_program_description TEXT,
    default_duties                  REAL,
    currency_default_duties         TEXT,
    input_date                      TEXT,
    saved_at                        TEXT    NOT NULL
);
"""

# Safe migration: columns added to `runs` in newer deployments
_RUNS_NEW_COLS = [
    "account_key TEXT",
    "account_label TEXT",
    "environment TEXT",
]

# Safe migration: columns added to `merged_results` in newer deployments
_MERGED_NEW_COLS = [
    "customs_value_original REAL",
    "cv_currency_original TEXT",
]

# Safe migration: columns added to `initiatives` in newer deployments
_INITIATIVES_NEW_COLS = [
    "group_id INTEGER",
    "implementation_date TEXT",
    "material_number TEXT",
    "start_date TEXT",
    "comments TEXT",
    "potential_reimbursements REAL DEFAULT 0",
    "group_name TEXT",
    "min_duty_rate REAL",
    "min_duty_program TEXT",
]


def _migrate_runs(conn: sqlite3.Connection) -> None:
    for col_def in _RUNS_NEW_COLS:
        try:
            conn.execute(f"ALTER TABLE runs ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass


def _migrate_merged(conn: sqlite3.Connection) -> None:
    for col_def in _MERGED_NEW_COLS:
        try:
            conn.execute(f"ALTER TABLE merged_results ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass


def _migrate_initiatives(conn: sqlite3.Connection) -> None:
    for col_def in _INITIATIVES_NEW_COLS:
        try:
            conn.execute(f"ALTER TABLE initiatives ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass


_FX_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS fx_rates_cache (
    id         INTEGER PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    rates_json TEXT NOT NULL
);
"""

_FX_CACHE_TTL_SECONDS = 4 * 3600  # 4 hours

_DB_READY = False  # module-level flag: schema created + migrations run


def init_db() -> None:
    """Create schema and run migrations. Idempotent: only executes once per process."""
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_DDL)
        conn.executescript(_INITIATIVES_DDL)
        conn.executescript(_FX_CACHE_DDL)
        _migrate_runs(conn)
        _migrate_merged(conn)
        _migrate_initiatives(conn)
    _DB_READY = True


# ---------------------------------------------------------------------------
# Account labels
# ---------------------------------------------------------------------------

def save_account_label(account_key: str, label: str) -> None:
    """Store or update the human-readable label for an account_key."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO account_labels (account_key, label, created_at) VALUES (?, ?, ?)",
            (account_key, label.strip(), now),
        )
    st.cache_data.clear()


@st.cache_data(ttl=60, show_spinner=False)
def get_account_label(account_key: str) -> Optional[str]:
    """Return the stored label for account_key, or None if not found."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT label FROM account_labels WHERE account_key = ?", (account_key,)
        ).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Query counter
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def get_query_counter(account_key: Optional[str] = None) -> int:
    """
    Return total processed queries (ok + failed) across all non-cancelled runs.
    If account_key is provided, filter to that account only.
    """
    init_db()
    with _connect() as conn:
        if account_key:
            row = conn.execute(
                """SELECT COALESCE(SUM(COALESCE(total_ok,0) + COALESCE(total_failed,0)), 0)
                   FROM runs WHERE cancelled = 0 AND account_key = ?""",
                (account_key,),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT COALESCE(SUM(COALESCE(total_ok,0) + COALESCE(total_failed,0)), 0)
                   FROM runs WHERE cancelled = 0"""
            ).fetchone()
    return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# FX rates cache (SQLite-persisted, TTL 4 h)
# ---------------------------------------------------------------------------

def load_fx_rates() -> Optional[dict]:
    """Return the most-recently stored FX rates dict if younger than TTL, else None."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT fetched_at, rates_json FROM fx_rates_cache ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    try:
        fetched_at = datetime.fromisoformat(row[0])
        age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        if age > _FX_CACHE_TTL_SECONDS:
            return None
        return json.loads(row[1])
    except Exception:
        return None


def save_fx_rates(rates: dict) -> None:
    """Persist FX rates to SQLite, replacing any previous entry."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("DELETE FROM fx_rates_cache")
        conn.execute(
            "INSERT INTO fx_rates_cache (fetched_at, rates_json) VALUES (?, ?)",
            (now, json.dumps(rates)),
        )


# ---------------------------------------------------------------------------
# Editable column registry
# ---------------------------------------------------------------------------

# DB column names the user is allowed to update
_EDITABLE_MERGED_DB_COLS: frozenset = frozenset({
    "coo", "coi", "hs_code", "customs_value", "cv_currency",
    "weight", "duty_paid", "dp_currency", "hs_alternative", "comment",
})

# Mapping: DataFrame display column name → DB column name (editable columns only)
EDITABLE_COL_DF_TO_DB: dict = {
    "coo":            "coo",
    "coi":            "coi",
    "hs code":        "hs_code",
    "customs value":  "customs_value",
    "cv currency":    "cv_currency",
    "weight":         "weight",
    "duty paid":      "duty_paid",
    "dp currency":    "dp_currency",
    "hs alternative": "hs_alternative",
    "comment":        "comment",
}


# ---------------------------------------------------------------------------
# Update / Delete
# ---------------------------------------------------------------------------

def update_merged_rows(changes: list) -> int:
    """
    Bulk-update rows in merged_results.

    Each entry in `changes` must be a dict with:
      - "id": int  — the row's primary key
      - one or more keys from _EDITABLE_MERGED_DB_COLS with their new values

    Returns the number of rows updated.
    """
    if not changes:
        return 0
    init_db()
    count = 0
    with _connect() as conn:
        for entry in changes:
            row_id = entry.get("id")
            if row_id is None:
                continue
            safe = {k: v for k, v in entry.items()
                    if k != "id" and k in _EDITABLE_MERGED_DB_COLS}
            if not safe:
                continue
            set_clause = ", ".join(f"{col} = ?" for col in safe)
            conn.execute(
                f"UPDATE merged_results SET {set_clause} WHERE id = ?",
                list(safe.values()) + [int(row_id)],
            )
            count += 1
    st.cache_data.clear()
    return count


def delete_merged_rows(ids: list) -> int:
    """
    Delete rows from merged_results by primary key.
    Returns the number of rows deleted.
    """
    if not ids:
        return 0
    init_db()
    placeholders = ", ".join("?" * len(ids))
    with _connect() as conn:
        cur = conn.execute(
            f"DELETE FROM merged_results WHERE id IN ({placeholders})",
            [int(i) for i in ids],
        )
    st.cache_data.clear()
    return cur.rowcount


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def find_duplicate_transactions(df: pd.DataFrame, ref_date: str = "") -> pd.DataFrame:
    """
    Return the subset of rows in `df` that already exist in merged_results.

    No ref_date filter — the same transaction should not be re-sent regardless of
    which accounting period it was originally processed under.

    Match strategy (in order of reliability):
    1. invoice_number + material_number + customs_value_original + cv_currency_original
       (when both business IDs and original currency values are present in df and DB)
    2. invoice_number + material_number only
       (when DB has old rows without customs_value_original stored)
    3. coo + coi + hs_code + customs_value_original + cv_currency_original + weight
       (fallback when no invoice/material in df)

    customs_value_original is used instead of the EUR-converted customs_value to
    avoid false negatives caused by FX rate changes between runs.
    """
    init_db()

    has_invoice = "invoice number" in df.columns and df["invoice number"].notna().any()
    has_material = "material number" in df.columns and df["material number"].notna().any()
    has_cv_orig_df = "customs value original" in df.columns and df["customs value original"].notna().any()
    use_business_key = has_invoice and has_material

    with _connect() as conn:
        if use_business_key:
            db_keys = pd.read_sql_query(
                """
                SELECT DISTINCT invoice_number, material_number,
                                customs_value_original, cv_currency_original
                FROM merged_results
                WHERE invoice_number IS NOT NULL AND material_number IS NOT NULL
                """,
                conn,
            )
        else:
            db_keys = pd.read_sql_query(
                """
                SELECT DISTINCT coo, coi, hs_code,
                                customs_value_original, cv_currency_original, weight
                FROM merged_results
                """,
                conn,
            )

    if db_keys.empty:
        return pd.DataFrame(columns=df.columns)

    rename_map = {
        "invoice_number": "invoice number",
        "material_number": "material number",
        "hs_code": "hs code",
        "customs_value_original": "customs value original",
        "cv_currency_original": "cv currency original",
    }
    db_keys = db_keys.rename(columns=rename_map)

    db_has_cv_orig = (
        "customs value original" in db_keys.columns
        and db_keys["customs value original"].notna().any()
    )

    if use_business_key:
        if has_cv_orig_df and db_has_cv_orig:
            merge_on = ["invoice number", "material number",
                        "customs value original", "cv currency original"]
        else:
            merge_on = ["invoice number", "material number"]
    else:
        if has_cv_orig_df and db_has_cv_orig:
            merge_on = ["coo", "coi", "hs code",
                        "customs value original", "cv currency original", "weight"]
        else:
            merge_on = ["coo", "coi", "hs code", "weight"]

    merge_on = [c for c in merge_on if c in df.columns and c in db_keys.columns]

    if not merge_on:
        return pd.DataFrame(columns=df.columns)

    _NUM_SENTINEL = -1.0
    _STR_SENTINEL = "__null__"
    _NUMERIC_COLS = {"customs value original", "weight"}

    df_norm = df[merge_on].copy()
    db_norm = db_keys[merge_on].drop_duplicates().copy()

    for col in merge_on:
        if col in _NUMERIC_COLS:
            df_norm[col] = pd.to_numeric(df_norm[col], errors="coerce").round(2).fillna(_NUM_SENTINEL)
            db_norm[col] = pd.to_numeric(db_norm[col], errors="coerce").round(2).fillna(_NUM_SENTINEL)
        else:
            df_norm[col] = df_norm[col].fillna(_STR_SENTINEL).astype(str).str.strip().str.upper()
            db_norm[col] = db_norm[col].fillna(_STR_SENTINEL).astype(str).str.strip().str.upper()

    tagged = df_norm.merge(db_norm, on=merge_on, how="left", indicator=True)
    is_dup = (tagged["_merge"] == "both").values
    return df[is_dup].copy()


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save_run_results(
    ok_df: pd.DataFrame,
    failed_df: pd.DataFrame,
    df_merged: pd.DataFrame,
    ref_date: str,
    run_summary: dict,
    account_key: Optional[str] = None,
    account_label: Optional[str] = None,
    environment: Optional[str] = None,
) -> int:
    """Persist one run's results. Returns the auto-generated run.id."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO runs
                (ref_date, started_at, total_candidates, total_ok, total_failed,
                 total_missing, cancelled, account_key, account_label, environment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ref_date, now,
                run_summary.get("total_candidates"),
                run_summary.get("ok"),
                run_summary.get("failed"),
                run_summary.get("missing"),
                int(bool(run_summary.get("cancelled", False))),
                account_key, account_label, environment,
            ),
        )
        run_id = cur.lastrowid

        if ok_df is not None and not ok_df.empty:
            conn.executemany(
                """INSERT INTO ok_results
                   (run_id, ref_date, coo, coi, hs_code, customs_value, cv_currency, weight, status, comment, saved_at)
                   VALUES (:run_id, :ref_date, :coo, :coi, :hs_code, :customs_value, :cv_currency, :weight, :status, :comment, :saved_at)""",
                _normalise_ok(ok_df, run_id, ref_date, now),
            )

        if failed_df is not None and not failed_df.empty:
            conn.executemany(
                """INSERT INTO failed_results
                   (run_id, ref_date, coo, coi, hs_code, customs_value, cv_currency, weight, error, saved_at)
                   VALUES (:run_id, :ref_date, :coo, :coi, :hs_code, :customs_value, :cv_currency, :weight, :error, :saved_at)""",
                _normalise_failed(failed_df, run_id, ref_date, now),
            )

        if df_merged is not None and not df_merged.empty:
            conn.executemany(
                """INSERT INTO merged_results (
                    run_id, ref_date, date, invoice_number, material_number,
                    coo, coi, hs_code, customs_value, cv_currency, weight,
                    duty_paid, dp_currency, status, comment, hs_alternative,
                    calc_name, inco_calc_basis,
                    min_duty_program, min_duty_rate, min_duty_program_description,
                    minimum_duties, currency_min_duties,
                    default_duty_program, default_duty_rate, default_duty_program_description,
                    default_duties, currency_default_duties,
                    customs_value_original, cv_currency_original,
                    input_date, saved_at
                ) VALUES (
                    :run_id, :ref_date, :date, :invoice_number, :material_number,
                    :coo, :coi, :hs_code, :customs_value, :cv_currency, :weight,
                    :duty_paid, :dp_currency, :status, :comment, :hs_alternative,
                    :calc_name, :inco_calc_basis,
                    :min_duty_program, :min_duty_rate, :min_duty_program_description,
                    :minimum_duties, :currency_min_duties,
                    :default_duty_program, :default_duty_rate, :default_duty_program_description,
                    :default_duties, :currency_default_duties,
                    :customs_value_original, :cv_currency_original,
                    :input_date, :saved_at
                )""",
                _normalise_merged(df_merged, run_id, ref_date, now),
            )

    st.cache_data.clear()
    return run_id


# ---------------------------------------------------------------------------
# Row normalisers
# ---------------------------------------------------------------------------

def _normalise_ok(df, run_id, ref_date, saved_at):
    return [{
        "run_id": run_id, "ref_date": ref_date,
        "coo": _str(r.get("coo")), "coi": _str(r.get("coi")),
        "hs_code": _str(r.get("hs code")),
        "customs_value": _float(r.get("customs value")),
        "cv_currency": _str(r.get("cv currency")),
        "weight": _float(r.get("weight")),
        "status": _str(r.get("status")), "comment": _str(r.get("comment")),
        "saved_at": saved_at,
    } for r in df.to_dict("records")]


def _normalise_failed(df, run_id, ref_date, saved_at):
    return [{
        "run_id": run_id, "ref_date": ref_date,
        "coo": _str(r.get("coo")), "coi": _str(r.get("coi")),
        "hs_code": _str(r.get("hs code")),
        "customs_value": _float(r.get("customs value")),
        "cv_currency": _str(r.get("cv currency")),
        "weight": _float(r.get("weight")),
        "error": _str(r.get("error")), "saved_at": saved_at,
    } for r in df.to_dict("records")]


def _normalise_merged(df, run_id, ref_date, saved_at):
    return [{
        "run_id": run_id, "ref_date": ref_date,
        "date": _str(r.get("date")),
        "invoice_number": _str(r.get("invoice number")),
        "material_number": _str(r.get("material number")),
        "coo": _str(r.get("coo")), "coi": _str(r.get("coi")),
        "hs_code": _str(r.get("hs code")),
        "customs_value": _float(r.get("customs value")),
        "cv_currency": _str(r.get("cv currency")),
        "weight": _float(r.get("weight")),
        "duty_paid": _float(r.get("duty paid")),
        "dp_currency": _str(r.get("dp currency")),
        "status": _str(r.get("status")), "comment": _str(r.get("comment")),
        "hs_alternative": _str(r.get("hs alternative")),
        "calc_name": _str(r.get("calcName")),
        "inco_calc_basis": _str(r.get("incoCalcBasis")),
        "min_duty_program": _str(r.get("Min Duty Program")),
        "min_duty_rate": _float(r.get("Min Duty Rate")),
        "min_duty_program_description": _str(r.get("Min Duty Program Description")),
        "minimum_duties": _float(r.get("Minimum Duties")),
        "currency_min_duties": _str(r.get("Currency Min Duties")),
        "default_duty_program": _str(r.get("Default Duty Program")),
        "default_duty_rate": _float(r.get("Default Duty Rate")),
        "default_duty_program_description": _str(r.get("Default Duty Program Description")),
        "default_duties": _float(r.get("Default Duties")),
        "currency_default_duties": _str(r.get("Currency Default Duties")),
        "customs_value_original": _float(r.get("customs value original")),
        "cv_currency_original": _str(r.get("cv currency original")),
        "input_date": _str(r.get("Input Date")),
        "saved_at": saved_at,
    } for r in df.to_dict("records")]


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def load_merged_results(ref_date: Optional[str] = None) -> pd.DataFrame:
    init_db()
    q = "SELECT * FROM merged_results" + (" WHERE ref_date = ?" if ref_date else "") + " ORDER BY id"
    with _connect() as conn:
        df = pd.read_sql_query(q, conn, params=(ref_date,) if ref_date else ())
    df = df.rename(columns=_MERGED_DB_TO_DF)
    return _coerce_merged_dtypes(df)


@st.cache_data(ttl=60, show_spinner=False)
def get_run_history() -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        df = pd.read_sql_query("SELECT * FROM runs ORDER BY id DESC", conn)
    for col in ("id", "total_candidates", "total_ok", "total_failed", "total_missing", "cancelled"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    _str_cols = frozenset({
        "ref_date", "started_at", "account_key", "account_label", "environment",
    })
    return _coerce_string_cols(df, _str_cols)


# ---------------------------------------------------------------------------
# Column mapping: DB → DataFrame
# ---------------------------------------------------------------------------

# Post-rename float columns (display names after _MERGED_DB_TO_DF rename)
_MERGED_FLOAT_COLS = frozenset({
    "customs value", "weight", "duty paid",
    "Min Duty Rate", "Minimum Duties",
    "Default Duty Rate", "Default Duties",
    "customs_value_original",
})
# Post-rename integer columns
_MERGED_INT_COLS = frozenset({"id", "run_id"})
# Post-rename string columns (cast to pandas "string" dtype for Arrow safety)
_MERGED_STRING_COLS = frozenset({
    "ref_date", "date", "invoice number", "material number",
    "coo", "coi", "hs code",
    "cv currency", "dp currency",
    "status", "comment", "hs alternative",
    "calcName", "incoCalcBasis",
    "Min Duty Program", "Min Duty Program Description", "Currency Min Duties",
    "Default Duty Program", "Default Duty Program Description", "Currency Default Duties",
    "cv_currency_original", "Input Date", "saved_at",
})


def _coerce_string_cols(df: pd.DataFrame, allowed: frozenset) -> pd.DataFrame:
    """Cast all object-dtype columns to pandas 'string' dtype for Arrow safety.
    The `allowed` set is checked first; any remaining object columns are also cast."""
    for col in df.columns:
        if col in allowed or df[col].dtype == "object":
            try:
                df[col] = df[col].astype("string")
            except (TypeError, ValueError):
                df[col] = df[col].astype(str).astype("string")
    return df


def _coerce_merged_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure all columns have Arrow-serializable dtypes after load."""
    for col in _MERGED_FLOAT_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col in _MERGED_INT_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return _coerce_string_cols(df, _MERGED_STRING_COLS)


_MERGED_DB_TO_DF = {
    "invoice_number": "invoice number",
    "material_number": "material number",
    "hs_code": "hs code",
    "customs_value": "customs value",
    "cv_currency": "cv currency",
    "duty_paid": "duty paid",
    "dp_currency": "dp currency",
    "hs_alternative": "hs alternative",
    "calc_name": "calcName",
    "inco_calc_basis": "incoCalcBasis",
    "min_duty_program": "Min Duty Program",
    "min_duty_rate": "Min Duty Rate",
    "min_duty_program_description": "Min Duty Program Description",
    "minimum_duties": "Minimum Duties",
    "currency_min_duties": "Currency Min Duties",
    "default_duty_program": "Default Duty Program",
    "default_duty_rate": "Default Duty Rate",
    "default_duty_program_description": "Default Duty Program Description",
    "default_duties": "Default Duties",
    "currency_default_duties": "Currency Default Duties",
    "input_date": "Input Date",
}


# ---------------------------------------------------------------------------
# Type-coercion helpers
# ---------------------------------------------------------------------------

def _str(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return None if s in ("", "nan", "None") else s


def _float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Initiatives
# ---------------------------------------------------------------------------

_INITIATIVES_EDITABLE = frozenset({
    "status", "savings_realized", "reimbursements",
    "implementation_date", "start_date", "comments", "potential_reimbursements",
    "min_duty_program",
})

_INITIATIVES_STATUS_OPTIONS = ["Identified", "Validated", "Discarded", "Completed"]


def save_initiatives(rows: list) -> int:
    """Insert new initiative rows. Returns number inserted."""
    if not rows:
        return 0
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.executemany(
            """INSERT INTO initiatives
               (coo, coi, hs_code, customs_value, duty_paid, default_duties,
                min_duties, potential_savings, annual_savings_est,
                savings_realized, reimbursements, status,
                product, program_description, created_at,
                material_number, start_date, comments, potential_reimbursements,
                min_duty_rate, min_duty_program)
               VALUES
               (:coo, :coi, :hs_code, :customs_value, :duty_paid, :default_duties,
                :min_duties, :potential_savings, :annual_savings_est,
                :savings_realized, :reimbursements, :status,
                :product, :program_description, :created_at,
                :material_number, :start_date, :comments, :potential_reimbursements,
                :min_duty_rate, :min_duty_program)""",
            [
                {
                    "product": "",
                    "annual_savings_est": 0.0,
                    "material_number": "",
                    "start_date": now[:10],
                    "comments": "",
                    "potential_reimbursements": 0.0,
                    "min_duty_rate": 0.0,
                    "min_duty_program": "",
                    **r,
                    "created_at": now,
                }
                for r in rows
            ],
        )
    st.cache_data.clear()
    return len(rows)


@st.cache_data(ttl=60, show_spinner=False)
def load_initiatives() -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        df = pd.read_sql_query("SELECT * FROM initiatives ORDER BY id DESC", conn)
    for col in ("customs_value", "duty_paid", "default_duties", "min_duties",
                "potential_savings", "annual_savings_est", "savings_realized",
                "reimbursements", "potential_reimbursements", "min_duty_rate"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col in ("id", "group_id"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    _str_cols = frozenset({
        "coo", "coi", "hs_code", "material_number",
        "min_duty_program", "program_description",
        "status", "comments", "group_name",
        "start_date", "implementation_date", "created_at",
    })
    return _coerce_string_cols(df, _str_cols)


def update_initiatives(changes: list) -> int:
    """Update editable fields on existing initiatives by id."""
    if not changes:
        return 0
    init_db()
    count = 0
    with _connect() as conn:
        for entry in changes:
            row_id = entry.get("id")
            if row_id is None:
                continue
            safe = {k: v for k, v in entry.items()
                    if k != "id" and k in _INITIATIVES_EDITABLE}
            if not safe:
                continue
            set_clause = ", ".join(f"{col} = ?" for col in safe)
            conn.execute(
                f"UPDATE initiatives SET {set_clause} WHERE id = ?",
                list(safe.values()) + [int(row_id)],
            )
            count += 1
    st.cache_data.clear()
    return count


def delete_initiatives(ids: list) -> int:
    if not ids:
        return 0
    init_db()
    placeholders = ", ".join("?" * len(ids))
    with _connect() as conn:
        cur = conn.execute(
            f"DELETE FROM initiatives WHERE id IN ({placeholders})",
            [int(i) for i in ids],
        )
    st.cache_data.clear()
    return cur.rowcount


def save_group_name(group_id: int, name: str) -> None:
    """Store a display name for a group on the parent initiative row."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE initiatives SET group_name = ? WHERE id = ?",
            (name.strip() or None, int(group_id)),
        )
    st.cache_data.clear()


def group_initiatives(ids: list) -> int:
    """Assign a shared group_id (min id) to all given initiative ids."""
    if len(ids) < 2:
        return 0
    init_db()
    group_id = int(min(ids))
    placeholders = ", ".join("?" * len(ids))
    with _connect() as conn:
        conn.execute(
            f"UPDATE initiatives SET group_id = ? WHERE id IN ({placeholders})",
            [group_id] + [int(i) for i in ids],
        )
    st.cache_data.clear()
    return len(ids)


def ungroup_initiatives(ids: list) -> int:
    """Remove group_id from the given initiative ids."""
    if not ids:
        return 0
    init_db()
    placeholders = ", ".join("?" * len(ids))
    with _connect() as conn:
        conn.execute(
            f"UPDATE initiatives SET group_id = NULL WHERE id IN ({placeholders})",
            [int(i) for i in ids],
        )
    st.cache_data.clear()
    return len(ids)


# ---------------------------------------------------------------------------
# Backup & Restore
# ---------------------------------------------------------------------------

def backup_db() -> bytes:
    """Return a consistent binary snapshot of the live database."""
    db_path = get_db_path()
    if not db_path.exists():
        raise FileNotFoundError("Database not found — run an analysis first.")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with sqlite3.connect(str(db_path)) as src:
            with sqlite3.connect(str(tmp_path)) as dst:
                src.backup(dst)
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


_REQUIRED_TABLES = frozenset({"merged_results", "runs"})


def restore_db(data: bytes) -> None:
    """
    Replace the live database with the supplied backup bytes.
    Validates the file before overwriting; auto-saves the current db first.
    Raises ValueError if the uploaded file is not a valid backup.
    """
    db_path = get_db_path()

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        # Validate: must be a readable SQLite file with the expected tables
        try:
            conn = sqlite3.connect(str(tmp_path))
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            conn.close()
        except Exception as exc:
            raise ValueError(f"Not a valid SQLite file: {exc}") from exc

        missing = _REQUIRED_TABLES - tables
        if missing:
            raise ValueError(f"Backup is missing required tables: {', '.join(sorted(missing))}")

        # Auto-save the current db before overwriting
        if db_path.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            auto_bk = db_path.with_name(f"duty_cockpit_pre_restore_{stamp}.db")
            shutil.copy2(db_path, auto_bk)

        shutil.copy2(tmp_path, db_path)
        # Reset the init flag so migrations re-run against the restored DB
        global _DB_READY
        _DB_READY = False
        init_db()
        st.cache_data.clear()
    finally:
        tmp_path.unlink(missing_ok=True)
