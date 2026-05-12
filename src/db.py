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


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_DDL)
        conn.executescript(_INITIATIVES_DDL)
        _migrate_runs(conn)
        _migrate_merged(conn)


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
    return cur.rowcount


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def find_duplicate_transactions(df: pd.DataFrame, ref_date: str) -> pd.DataFrame:  # noqa: ARG001
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
    } for _, r in df.iterrows()]


def _normalise_failed(df, run_id, ref_date, saved_at):
    return [{
        "run_id": run_id, "ref_date": ref_date,
        "coo": _str(r.get("coo")), "coi": _str(r.get("coi")),
        "hs_code": _str(r.get("hs code")),
        "customs_value": _float(r.get("customs value")),
        "cv_currency": _str(r.get("cv currency")),
        "weight": _float(r.get("weight")),
        "error": _str(r.get("error")), "saved_at": saved_at,
    } for _, r in df.iterrows()]


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
    } for _, r in df.iterrows()]


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def load_ok_results(ref_date: Optional[str] = None) -> pd.DataFrame:
    init_db()
    q = "SELECT * FROM ok_results" + (" WHERE ref_date = ?" if ref_date else "") + " ORDER BY id"
    with _connect() as conn:
        return pd.read_sql_query(q, conn, params=(ref_date,) if ref_date else ())


def load_failed_results(ref_date: Optional[str] = None) -> pd.DataFrame:
    init_db()
    q = "SELECT * FROM failed_results" + (" WHERE ref_date = ?" if ref_date else "") + " ORDER BY id"
    with _connect() as conn:
        return pd.read_sql_query(q, conn, params=(ref_date,) if ref_date else ())


def load_merged_results(ref_date: Optional[str] = None) -> pd.DataFrame:
    init_db()
    q = "SELECT * FROM merged_results" + (" WHERE ref_date = ?" if ref_date else "") + " ORDER BY id"
    with _connect() as conn:
        df = pd.read_sql_query(q, conn, params=(ref_date,) if ref_date else ())
    return df.rename(columns=_MERGED_DB_TO_DF)


def get_run_history() -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        return pd.read_sql_query("SELECT * FROM runs ORDER BY id DESC", conn)


# ---------------------------------------------------------------------------
# Combine helpers
# ---------------------------------------------------------------------------

def load_combined_ok_results(current_ok_df: pd.DataFrame) -> pd.DataFrame:
    historical = load_ok_results()
    if not historical.empty:
        historical = historical.rename(columns={"hs_code": "hs code", "customs_value": "customs value", "cv_currency": "cv currency"})
        keep = ["coo", "coi", "hs code", "customs value", "cv currency", "weight", "status", "comment"]
        historical = historical[[c for c in keep if c in historical.columns]]
    frames = [f for f in [historical, current_ok_df] if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["coo", "coi", "hs code", "customs value", "cv currency", "weight"]
    )


def load_combined_failed_results(current_failed_df: pd.DataFrame) -> pd.DataFrame:
    historical = load_failed_results()
    if not historical.empty:
        historical = historical.rename(columns={"hs_code": "hs code", "customs_value": "customs value", "cv_currency": "cv currency"})
        keep = ["coo", "coi", "hs code", "customs value", "cv currency", "weight", "error"]
        historical = historical[[c for c in keep if c in historical.columns]]
    frames = [f for f in [historical, current_failed_df] if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=["coo", "coi", "hs code", "customs value", "cv currency", "weight"]
    )


def load_combined_merged_results(current_merged_df: pd.DataFrame) -> pd.DataFrame:
    historical = load_merged_results()
    frames = [f for f in [historical, current_merged_df] if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    dedup = ["invoice number", "material number", "coo", "coi", "hs code", "Input Date"]
    available = [c for c in dedup if c in combined.columns] or ["coo", "coi", "hs code", "customs value", "cv currency", "weight"]
    return combined.drop_duplicates(subset=available)


# ---------------------------------------------------------------------------
# Column mapping: DB → DataFrame
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


# ---------------------------------------------------------------------------
# Initiatives
# ---------------------------------------------------------------------------

_INITIATIVES_EDITABLE = frozenset({
    "status", "annual_savings_est", "savings_realized", "reimbursements",
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
                product, program_description, created_at)
               VALUES
               (:coo, :coi, :hs_code, :customs_value, :duty_paid, :default_duties,
                :min_duties, :potential_savings, :annual_savings_est,
                :savings_realized, :reimbursements, :status,
                :product, :program_description, :created_at)""",
            [{**r, "created_at": now} for r in rows],
        )
    return len(rows)


def load_initiatives() -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        return pd.read_sql_query(
            "SELECT * FROM initiatives ORDER BY id DESC", conn
        )


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
    return cur.rowcount
