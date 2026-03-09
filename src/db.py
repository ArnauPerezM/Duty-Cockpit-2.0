from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_db_path() -> Path:
    """Return the path to the SQLite database file (created on first use)."""
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

_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_date            TEXT    NOT NULL,
    started_at          TEXT    NOT NULL,
    total_candidates    INTEGER,
    total_ok            INTEGER,
    total_failed        INTEGER,
    total_missing       INTEGER,
    cancelled           INTEGER DEFAULT 0
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


def init_db() -> None:
    """Create tables if they do not already exist."""
    with _connect() as conn:
        conn.executescript(_DDL)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save_run_results(
    ok_df: pd.DataFrame,
    failed_df: pd.DataFrame,
    df_merged: pd.DataFrame,
    ref_date: str,
    run_summary: dict,
) -> int:
    """
    Persist one run's ok_df, failed_df and df_merged to the database.
    Returns the auto-generated run.id.
    """
    init_db()

    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO runs
                (ref_date, started_at, total_candidates, total_ok, total_failed, total_missing, cancelled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ref_date,
                now,
                run_summary.get("total_candidates"),
                run_summary.get("ok"),
                run_summary.get("failed"),
                run_summary.get("missing"),
                int(bool(run_summary.get("cancelled", False))),
            ),
        )
        run_id = cur.lastrowid

        if ok_df is not None and not ok_df.empty:
            conn.executemany(
                """
                INSERT INTO ok_results
                    (run_id, ref_date, coo, coi, hs_code, customs_value, cv_currency, weight, status, comment, saved_at)
                VALUES (:run_id, :ref_date, :coo, :coi, :hs_code, :customs_value, :cv_currency, :weight, :status, :comment, :saved_at)
                """,
                _normalise_ok(ok_df, run_id, ref_date, now),
            )

        if failed_df is not None and not failed_df.empty:
            conn.executemany(
                """
                INSERT INTO failed_results
                    (run_id, ref_date, coo, coi, hs_code, customs_value, cv_currency, weight, error, saved_at)
                VALUES (:run_id, :ref_date, :coo, :coi, :hs_code, :customs_value, :cv_currency, :weight, :error, :saved_at)
                """,
                _normalise_failed(failed_df, run_id, ref_date, now),
            )

        if df_merged is not None and not df_merged.empty:
            conn.executemany(
                """
                INSERT INTO merged_results (
                    run_id, ref_date, date, invoice_number, material_number,
                    coo, coi, hs_code, customs_value, cv_currency, weight,
                    duty_paid, dp_currency, status, comment, hs_alternative,
                    calc_name, inco_calc_basis,
                    min_duty_program, min_duty_rate, min_duty_program_description,
                    minimum_duties, currency_min_duties,
                    default_duty_program, default_duty_rate, default_duty_program_description,
                    default_duties, currency_default_duties,
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
                    :input_date, :saved_at
                )
                """,
                _normalise_merged(df_merged, run_id, ref_date, now),
            )

    return run_id


# ---------------------------------------------------------------------------
# Row normalisers
# ---------------------------------------------------------------------------

def _normalise_ok(df: pd.DataFrame, run_id: int, ref_date: str, saved_at: str) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "run_id": run_id,
            "ref_date": ref_date,
            "coo": _str(r.get("coo")),
            "coi": _str(r.get("coi")),
            "hs_code": _str(r.get("hs code")),
            "customs_value": _float(r.get("customs value")),
            "cv_currency": _str(r.get("cv currency")),
            "weight": _float(r.get("weight")),
            "status": _str(r.get("status")),
            "comment": _str(r.get("comment")),
            "saved_at": saved_at,
        })
    return rows


def _normalise_failed(df: pd.DataFrame, run_id: int, ref_date: str, saved_at: str) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "run_id": run_id,
            "ref_date": ref_date,
            "coo": _str(r.get("coo")),
            "coi": _str(r.get("coi")),
            "hs_code": _str(r.get("hs code")),
            "customs_value": _float(r.get("customs value")),
            "cv_currency": _str(r.get("cv currency")),
            "weight": _float(r.get("weight")),
            "error": _str(r.get("error")),
            "saved_at": saved_at,
        })
    return rows


def _normalise_merged(df: pd.DataFrame, run_id: int, ref_date: str, saved_at: str) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "run_id": run_id,
            "ref_date": ref_date,
            "date": _str(r.get("date")),
            "invoice_number": _str(r.get("invoice number")),
            "material_number": _str(r.get("material number")),
            "coo": _str(r.get("coo")),
            "coi": _str(r.get("coi")),
            "hs_code": _str(r.get("hs code")),
            "customs_value": _float(r.get("customs value")),
            "cv_currency": _str(r.get("cv currency")),
            "weight": _float(r.get("weight")),
            "duty_paid": _float(r.get("duty paid")),
            "dp_currency": _str(r.get("dp currency")),
            "status": _str(r.get("status")),
            "comment": _str(r.get("comment")),
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
            "input_date": _str(r.get("Input Date")),
            "saved_at": saved_at,
        })
    return rows


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def load_ok_results(ref_date: Optional[str] = None) -> pd.DataFrame:
    """Return all historical ok rows, optionally filtered by ref_date."""
    init_db()
    query = "SELECT * FROM ok_results"
    params: tuple = ()
    if ref_date:
        query += " WHERE ref_date = ?"
        params = (ref_date,)
    query += " ORDER BY id"
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=params)


def load_failed_results(ref_date: Optional[str] = None) -> pd.DataFrame:
    """Return all historical failed rows, optionally filtered by ref_date."""
    init_db()
    query = "SELECT * FROM failed_results"
    params: tuple = ()
    if ref_date:
        query += " WHERE ref_date = ?"
        params = (ref_date,)
    query += " ORDER BY id"
    with _connect() as conn:
        return pd.read_sql_query(query, conn, params=params)


def load_merged_results(ref_date: Optional[str] = None) -> pd.DataFrame:
    """
    Return all historical merged rows, optionally filtered by ref_date.
    Column names are restored to the DataFrame convention used in logic.py.
    """
    init_db()
    query = "SELECT * FROM merged_results"
    params: tuple = ()
    if ref_date:
        query += " WHERE ref_date = ?"
        params = (ref_date,)
    query += " ORDER BY id"
    with _connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)

    # Restore original column names
    return df.rename(columns=_MERGED_DB_TO_DF)


def get_run_history() -> pd.DataFrame:
    """Return the full runs table (one row per past execution), newest first."""
    init_db()
    with _connect() as conn:
        return pd.read_sql_query("SELECT * FROM runs ORDER BY id DESC", conn)


# ---------------------------------------------------------------------------
# Combine helpers  (historical + current run)
# ---------------------------------------------------------------------------

def load_combined_ok_results(current_ok_df: pd.DataFrame) -> pd.DataFrame:
    """Concatenate all stored ok rows with the current run's ok_df, deduped by lane key."""
    historical = load_ok_results()
    if not historical.empty:
        historical = historical.rename(columns={"hs_code": "hs code", "customs_value": "customs value", "cv_currency": "cv currency"})
        keep = ["coo", "coi", "hs code", "customs value", "cv currency", "weight", "status", "comment"]
        historical = historical[[c for c in keep if c in historical.columns]]

    frames = [f for f in [historical, current_ok_df] if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(subset=["coo", "coi", "hs code", "customs value", "cv currency", "weight"])


def load_combined_failed_results(current_failed_df: pd.DataFrame) -> pd.DataFrame:
    """Concatenate all stored failed rows with the current run's failed_df, deduped by lane key."""
    historical = load_failed_results()
    if not historical.empty:
        historical = historical.rename(columns={"hs_code": "hs code", "customs_value": "customs value", "cv_currency": "cv currency"})
        keep = ["coo", "coi", "hs code", "customs value", "cv currency", "weight", "error"]
        historical = historical[[c for c in keep if c in historical.columns]]

    frames = [f for f in [historical, current_failed_df] if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(subset=["coo", "coi", "hs code", "customs value", "cv currency", "weight"])


def load_combined_merged_results(current_merged_df: pd.DataFrame) -> pd.DataFrame:
    """
    Concatenate all stored merged rows with the current run's df_merged, deduped
    by the natural key (invoice_number + material_number + coo + coi + hs_code + input_date).
    Falls back to lane key if invoice/material columns are absent.
    """
    historical = load_merged_results()  # already renamed to DF convention

    frames = [f for f in [historical, current_merged_df] if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)

    dedup_cols = ["invoice number", "material number", "coo", "coi", "hs code", "Input Date"]
    available = [c for c in dedup_cols if c in combined.columns]
    if not available:
        available = ["coo", "coi", "hs code", "customs value", "cv currency", "weight"]
    return combined.drop_duplicates(subset=available)


# ---------------------------------------------------------------------------
# Internal: DB column → DataFrame column mapping for merged_results
# ---------------------------------------------------------------------------

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
