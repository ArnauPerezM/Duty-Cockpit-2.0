from __future__ import annotations

import re
import time
from typing import Callable, Optional, Tuple, List, Dict, Any

import pandas as pd
from E2Open import E2OpenSession


# -----------------------------
# FX rates (Frankfurter → ECB fallback)
# -----------------------------

# Module-level cache so we only fetch once per Python process / Streamlit session
_FX_CACHE: dict | None = None

# Currencies not covered by ECB/Frankfurter (~30 major only).
# open.er-api.com is free, no API key, covers 160+ currencies including TWD, COP, etc.
_FX_SOURCES = [
    ("open.er-api.com", "https://open.er-api.com/v6/latest/EUR",
     lambda d: {k.upper(): 1.0 / v for k, v in d["rates"].items() if v}),
    ("Frankfurter",     "https://api.frankfurter.app/latest?base=EUR",
     lambda d: {k.upper(): 1.0 / v for k, v in d["rates"].items() if v}),
]


def _fetch_fx_rates_eur() -> dict:
    """
    Fetch latest FX rates with EUR as base.
    Tries multiple sources in order until one succeeds.
    Returns {currency_code: rate_to_eur} — EUR per 1 unit of that currency.
    EUR itself is always 1.0.
    No business data is sent to any endpoint.
    Result is cached in-process AND persisted to SQLite (TTL 4 h) so it
    survives process restarts without a network call.
    """
    global _FX_CACHE
    if _FX_CACHE is not None:
        return _FX_CACHE

    # Check SQLite cache before hitting the network
    try:
        from src.db import load_fx_rates, save_fx_rates as _save_fx
        _db_rates = load_fx_rates()
        if _db_rates is not None:
            _FX_CACHE = _db_rates
            return _FX_CACHE
    except Exception:
        _save_fx = None  # DB unavailable — proceed to network fetch

    import urllib.request
    import json

    last_err = None
    for name, url, parser in _FX_SOURCES:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            rates = parser(data)
            rates["EUR"] = 1.0
            _FX_CACHE = rates
            try:
                if _save_fx is not None:
                    _save_fx(rates)
            except Exception:
                pass  # DB write failure must not abort the run
            return _FX_CACHE
        except Exception as e:
            last_err = f"{name}: {e}"

    raise RuntimeError(f"All FX sources failed. Last error: {last_err}")


# -----------------------------
# Cleaning / normalisation helpers
# -----------------------------

def _to_lower_columns(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2.columns = [str(c).strip().lower() for c in df2.columns]
    return df2

def _clean_hs(x: Any) -> str:
    if pd.isna(x):
        return ""

    if isinstance(x, int):
        return str(x).strip()

    if isinstance(x, float):
        if pd.isna(x):
            return ""
        if x.is_integer():
            return str(int(x))
        # Non-integer float: strip decimals without scientific notation
        return re.sub(r"\D", "", f"{x:.0f}").strip()

    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return ""

    # Scientific notation: e.g. "8.518302E+09"
    if re.fullmatch(r"[+-]?\d+(\.\d+)?[eE][+-]?\d+", s):
        try:
            return str(int(float(s)))
        except Exception:
            pass

    # Numeric string with trailing .0: e.g. "8518302000.0"
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]

    return re.sub(r"\D", "", s).strip()

def _clean_country(x: Any) -> str:
    if pd.isna(x) or str(x).strip() == "" or str(x).strip().lower() == "nan":
        return ""
    return re.sub(r"[^a-zA-Z]+", "", str(x)).strip().upper()

def _clean_weight(x: Any) -> float:
    if pd.isna(x) or x == 0:
        return 1.0
    s = re.sub(r"[^\d.]", "", str(x))
    try:
        v = float(s) if s != "" else 1.0
        return 1.0 if v == 0 else v
    except Exception:
        return 1.0

def _clean_customs_value(x: Any) -> float:
    v = pd.to_numeric(x, errors="coerce")
    if pd.isna(v):
        return 0.0
    return float(v)

def _find_column(df_lower: pd.DataFrame, desired_lower: str) -> Optional[str]:
    # handles spaces and other minor variations
    cols = list(df_lower.columns)
    if desired_lower in cols:
        return desired_lower
    # fallback: normalise multiple spaces
    norm = {re.sub(r"\s+", " ", c.strip().lower()): c for c in cols}
    key = re.sub(r"\s+", " ", desired_lower.strip().lower())
    return norm.get(key)

# -----------------------------
# Excel loading (cached indirectly via st.cache_data in app.py)
# -----------------------------

_REQUIRED_COLUMNS = [
    "coo", "coi", "hs code", "customs value", "duty paid",
    "material number", "cv currency", "dp currency",
]
# "weight" is optional — defaults to 1.0 if absent


def load_transactions_excel(uploaded_file, sheet_name: str = "Transactions") -> pd.DataFrame:
    try:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
    except Exception as exc:
        msg = str(exc)
        if "Worksheet" in msg or "sheet" in msg.lower():
            raise ValueError(
                f"Sheet '{sheet_name}' not found in the uploaded file. "
                f"Check the sheet name and try again."
            ) from exc
        raise

    df_lower = _to_lower_columns(df)
    missing = [c for c in _REQUIRED_COLUMNS if _find_column(df_lower, c) is None]
    if missing:
        found = list(df_lower.columns)
        raise ValueError(
            f"Missing required columns in sheet '{sheet_name}': {missing}.\n"
            f"Expected: {_REQUIRED_COLUMNS}.\n"
            f"Found: {found}"
        )
    return df

# -----------------------------
# Currency standardisation + validation + cleanup
# -----------------------------

def _convert_customs_value_to_eur(df: pd.DataFrame) -> Tuple[pd.DataFrame, list]:
    """
    Convert df['customs value'] from df['cv currency'] to EUR using Frankfurter API.
    Does NOT change business logic elsewhere; it only standardizes values/currency.

    Adds:
      - customs value original
      - cv currency original
    """
    out = df.copy()

    if "customs value" not in out.columns or "cv currency" not in out.columns:
        raise ValueError("Cannot convert to EUR: missing 'customs value' and/or 'cv currency' columns.")

    out["cv currency"] = out["cv currency"].astype(str).str.strip().str.upper()

    # Preserve originals for audit/debugging
    out["customs value original"] = out["customs value"]
    out["cv currency original"] = out["cv currency"]

    try:
        fx_map = _fetch_fx_rates_eur()
    except Exception:
        fx_map = {}

    rates = out["cv currency"].map(fx_map)
    missing = rates.isna()
    missing_ccy: list[str] = []
    if missing.any():
        missing_ccy = sorted(out.loc[missing, "cv currency"].dropna().unique().tolist())
        rates = rates.fillna(1.0)  # pass-through: no conversion, value kept as-is

    out["customs value"] = (pd.to_numeric(out["customs value"], errors="coerce").fillna(0.0) * rates).round(2)
    # If conversion succeeded, the value is now EUR.
    # If no FX rate was found, keep original currency and original amount.
    out["cv currency"] = "EUR"
    out.loc[missing, "cv currency"] = out.loc[missing, "cv currency original"]
    return out, missing_ccy

def validate_and_clean_transactions(
    df_original: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    - Filtra Analyzed == False (si existe)
    - Limpia: coo/coi/hs code/customs value/weight
    - Separa df_missing (faltantes) para "skip"
    - Calcula warnings ratios (HS>=6, COO/COI ISO2)
    """
    df = _to_lower_columns(df_original)
    df = df.copy()
    df["_tx_id"] = df.index.astype(str)

    analyzed_col = _find_column(df, "analyzed")
    if analyzed_col is not None:
        df = df[df[analyzed_col] == False]  # noqa: E712

    if df.empty:
        return df, pd.DataFrame(), {
            "hs_ratio": 1.0,
            "hs_ratio_ok": True,
            "iso_ratio": 1.0,
            "iso_ratio_ok": True,
            "warnings": [],
        }

    # Asegurar columnas clave
    missing_required = [c for c in _REQUIRED_COLUMNS if _find_column(df, c) is None]
    if missing_required:
        raise ValueError(
            f"Missing required columns in sheet: {missing_required}. "
            f"Expected: {_REQUIRED_COLUMNS}."
        )

    # Normalise expected column names (handles minor variations)
    colmap = {}
    for c in _REQUIRED_COLUMNS:
        colmap[_find_column(df, c)] = c
    df = df.rename(columns=colmap)

    # Weight is optional — defaults to 1.0 if the column is absent
    _weight_col = _find_column(df, "weight")
    if _weight_col is not None:
        if _weight_col != "weight":
            df = df.rename(columns={_weight_col: "weight"})
        df["weight"] = df["weight"].apply(_clean_weight)
    else:
        df["weight"] = 1.0

    # Base cleanup
    df["customs value"] = df["customs value"].apply(_clean_customs_value)
    df["hs code"] = df["hs code"].apply(_clean_hs)
    df["coo"] = df["coo"].apply(_clean_country)
    df["coi"] = df["coi"].apply(_clean_country)
    df["cv currency"] = df["cv currency"].astype(str).str.strip().str.upper()

    # Standardize all transactions to EUR (using local FX file)
    df, _fx_missing = _convert_customs_value_to_eur(df)

    # df_missing: rows with empty COO/COI/HS or zero customs value
    df_missing = df[
        (df["coo"].astype(str).str.strip() == "")
        | (df["coi"].astype(str).str.strip() == "")
        | (df["hs code"].astype(str).str.strip() == "")
        | (df["customs value"].isna())
        | (df["customs value"] == 0.0)
    ].copy()

    # clean df ready to process
    df_ok = df[
        (df["coo"].astype(str).str.strip() != "")
        & (df["coi"].astype(str).str.strip() != "")
        & (df["hs code"].astype(str).str.strip() != "")
        & (df["customs value"] != 0.0)
    ].copy()

    # drop duplicates — exclude _tx_id so business deduplication is unchanged
    _dup_subset = [c for c in df_ok.columns if c != "_tx_id"]
    df_ok = df_ok.drop_duplicates(subset=_dup_subset)

    # Warnings ratios
    hs_ratio = 1.0
    iso_ratio = 1.0
    warnings = []

    if len(df_ok) > 0:
        hs_ratio = round((df_ok["hs code"].str.len() >= 6).mean(), 3)
        iso_ratio = round(((df_ok["coi"].str.len() == 2) & (df_ok["coo"].str.len() == 2)).mean(), 3)

        if hs_ratio < 0.95:
            warnings.append(
                f"Warning: only {hs_ratio*100:.1f}% of HS Codes have >=6 digits (threshold: 95%)."
            )
        if iso_ratio < 0.95:
            warnings.append(
                f"Warning: only {iso_ratio*100:.1f}% of COO/COI values are ISO-2 compliant (threshold: 95%)."
            )

    if _fx_missing:
        warnings.append(
            f"FX rate not found for: {', '.join(_fx_missing)}. Values kept in original currency (no EUR conversion)."
        )

    warnings_info = {
        "hs_ratio": hs_ratio,
        "hs_ratio_ok": hs_ratio >= 0.95,
        "iso_ratio": iso_ratio,
        "iso_ratio_ok": iso_ratio >= 0.95,
        "warnings": warnings,
        "rows_candidates": int(len(df_ok)),
        "rows_missing": int(len(df_missing)),
    }

    return _arrow_safe(df_ok), _arrow_safe(df_missing), warnings_info


def _arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Cast object columns to pandas 'string' dtype for safe Arrow serialization."""
    if df is None or df.empty:
        return df
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                df[col] = df[col].astype("string")
            except (TypeError, ValueError):
                df[col] = df[col].astype(str).astype("string")
    return df

# -----------------------------
# API loop + logs
# -----------------------------

def run_api_loop(
    df_in: pd.DataFrame,
    ref_date: str,
    credentials: Dict[str, str],
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
    max_retries: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict[str, Any]]]:
    """
    Ejecuta sesión e2open y pide getImportCost por fila.
    - Sin input() de retry: reintenta hasta max_retries, luego falla fila y continúa.
    - Devuelve: failed_df (mismas cols clave), ok_df (lanes procesadas), logs (eventos)
    """
    logs: List[Dict[str, Any]] = []

    def log(event: str, **kwargs):
        logs.append({"ts": time.time(), "event": event, **kwargs})

    session = E2OpenSession(
        credentials["username"],
        credentials["password"],
        credentials["tenant"],
        credentials.get("environment", "UAT"),
    )
    log("session_started")

    failed_rows = []
    ok_rows = []

    total = len(df_in)
    idx_list = list(df_in.index)

    for i, ridx in enumerate(idx_list, start=1):
        if should_cancel and should_cancel():
            log("cancel_requested", processed=i - 1, total=total)
            break

        row = df_in.loc[ridx]
        coo = row["coo"]
        coi = row["coi"]
        hs = row["hs code"]
        cust_val = row["customs value"]
        cur = row["cv currency"]
        qnty = row["weight"]
        tx_id = str(row["_tx_id"]) if "_tx_id" in df_in.columns else str(ridx)

        attempt = 0
        success = False
        last_err = None
        last_status = None
        last_comment = ""

        while attempt < max_retries and not success:
            attempt += 1
            try:
                coo2, coi2, hs2, cust_val2, cur2, qnty2, status, comment = session.getImportCost(
                    coo, coi, hs, cust_val, cur, qnty, ref_date, tx_id=tx_id
                )
                last_status = status
                last_comment = comment

                try:
                    status_int = int(status)
                except Exception:
                    status_int = None

                if status_int == 200:
                    ok_rows.append(
                        {
                            "_tx_id": tx_id,
                            "coo": coo2,
                            "coi": coi2,
                            "hs code": hs2,
                            "customs value": cust_val2,
                            "cv currency": cur2,
                            "weight": qnty2,
                            "status": status,
                            "comment": comment,
                        }
                    )
                    log(
                        "row_ok",
                        row=i,
                        total=total,
                        tx_id=tx_id,
                        coo=coo2,
                        coi=coi2,
                        hs=hs2,
                        status=status,
                        comment=comment,
                    )
                    success = True
                    if progress_cb:
                        progress_cb(i, total, f"{i}/{total} | {hs} | {coo}→{coi} | {status} | {comment}")
                else:
                    last_err = f"E2Open returned status {status}: {comment}"
                    log(
                        "row_api_error",
                        row=i,
                        total=total,
                        tx_id=tx_id,
                        coo=coo,
                        coi=coi,
                        hs=hs,
                        status=status,
                        comment=comment,
                        attempt=attempt,
                    )

            except Exception as e:
                last_err = str(e)
                log(
                    "row_retry",
                    row=i,
                    total=total,
                    tx_id=tx_id,
                    coo=coo,
                    coi=coi,
                    hs=hs,
                    attempt=attempt,
                    error=last_err,
                )

        if not success:
            failed_rows.append(
                {
                    "_tx_id": tx_id,
                    "coo": coo,
                    "coi": coi,
                    "hs code": hs,
                    "customs value": cust_val,
                    "cv currency": cur,
                    "weight": qnty,
                    "status": str(last_status) if last_status is not None else "",
                    "comment": last_comment,
                    "error": last_err or "Unknown error",
                }
            )
            log(
                "row_failed",
                row=i,
                total=total,
                tx_id=tx_id,
                coo=coo,
                coi=coi,
                hs=hs,
                error=last_err or "Unknown error",
            )
            if progress_cb:
                progress_cb(i, total, f"{i}/{total} | {hs} | {coo}→{coi} | FAILED | {last_err}")

    failed_df = pd.DataFrame(failed_rows)
    ok_df = pd.DataFrame(ok_rows)

    # Guardamos la salida raw del session dentro de logs para que postprocess pueda acceder sin globales
    log("session_output_ready", output_len=len(getattr(session, "output", {}) or {}))
    # Adjuntamos el objeto output serializable en logs (referencia directa dict)
    logs.append({"ts": time.time(), "event": "session_output", "payload": session.output})

    return failed_df, ok_df, logs

# -----------------------------
# Postproceso helpers
# -----------------------------

def _extract_session_output(logs: List[Dict[str, Any]]) -> dict:
    for item in reversed(logs):
        if item.get("event") == "session_output":
            return item.get("payload") or {}
    return {}


def _build_combined_failed(
    failed_df: Optional[pd.DataFrame],
    df_missing: Optional[pd.DataFrame],
) -> pd.DataFrame:
    _ALL_COLS = ["_tx_id", "COO", "COI", "HS Code", "Customs Value", "CV Currency", "Weight"]
    _RENAME = {
        "coo": "COO", "coi": "COI", "hs code": "HS Code",
        "customs value": "Customs Value", "cv currency": "CV Currency", "weight": "Weight",
    }
    frames = []

    for src_df in (failed_df, df_missing):
        if src_df is None or src_df.empty:
            continue
        f = src_df.copy()
        f = f.rename(columns={k: v for k, v in _RENAME.items() if k in f.columns})
        for col in ["COO", "COI"]:
            if col in f.columns:
                f[col] = f[col].apply(_clean_country)
        if "HS Code" in f.columns:
            f["HS Code"] = f["HS Code"].apply(_clean_hs)
        if "Customs Value" in f.columns:
            f["Customs Value"] = pd.to_numeric(f["Customs Value"], errors="coerce").round(2)
        if "CV Currency" in f.columns:
            f["CV Currency"] = f["CV Currency"].astype(str).str.strip().str.upper()
        if "Weight" in f.columns:
            f["Weight"] = pd.to_numeric(f["Weight"], errors="coerce")
        keep = [c for c in _ALL_COLS if c in f.columns]
        frames.append(f[keep])

    if not frames:
        return pd.DataFrame(columns=_ALL_COLS)

    return pd.concat(frames, ignore_index=True).dropna(how="all")


def _filter_failed_from_inputs(
    df_in: pd.DataFrame,
    df_raw: pd.DataFrame,
    combined_failed: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if combined_failed.empty:
        return df_in, df_raw

    # ── Priority: precise _tx_id filter ──────────────────────────────────────
    has_tx_in = "_tx_id" in df_in.columns
    has_tx_failed = (
        "_tx_id" in combined_failed.columns
        and combined_failed["_tx_id"].notna().any()
    )
    if has_tx_in and has_tx_failed:
        fail_ids = set(combined_failed["_tx_id"].dropna().astype(str).tolist())
        df_in = df_in[~df_in["_tx_id"].astype(str).isin(fail_ids)].copy()
        if not df_raw.empty and "_tx_id" in df_raw.columns:
            df_raw = df_raw[~df_raw["_tx_id"].astype(str).isin(fail_ids)].copy()
        return df_in, df_raw

    # ── Fallback: full trade-key filter (most specific available) ─────────────
    # df_in columns: coo, coi, hs code, customs value, cv currency, weight
    _IN_KEY_MAP = {
        "COO": "coo", "COI": "coi", "HS Code": "hs code",
        "Customs Value": "customs value", "CV Currency": "cv currency", "Weight": "weight",
    }
    left_on, right_on = [], []
    for right_col, left_col in _IN_KEY_MAP.items():
        if right_col in combined_failed.columns and left_col in df_in.columns:
            left_on.append(left_col)
            right_on.append(right_col)

    if left_on:
        fail_keys = combined_failed[right_on].drop_duplicates()
        merged_in = df_in.merge(fail_keys, left_on=left_on, right_on=right_on,
                                how="left", indicator=True)
        drop_cols = ["_merge"] + [c for c in right_on if c not in df_in.columns]
        df_in = merged_in[merged_in["_merge"] == "left_only"].drop(
            columns=drop_cols, errors="ignore"
        )

    # df_raw columns: coo, coi, hs, custUnitP, cur, qnty
    if not df_raw.empty:
        _RAW_KEY_MAP = {
            "COO": "coo", "COI": "coi", "HS Code": "hs",
            "Customs Value": "custUnitP", "CV Currency": "cur", "Weight": "qnty",
        }
        raw_left_on, raw_right_on = [], []
        for right_col, raw_col in _RAW_KEY_MAP.items():
            if right_col in combined_failed.columns and raw_col in df_raw.columns:
                raw_left_on.append(raw_col)
                raw_right_on.append(right_col)
        if raw_left_on:
            fail_keys_raw = combined_failed[raw_right_on].drop_duplicates()
            merged_raw = df_raw.merge(fail_keys_raw, left_on=raw_left_on, right_on=raw_right_on,
                                      how="left", indicator=True)
            drop_raw = ["_merge"] + [c for c in raw_right_on if c not in df_raw.columns]
            df_raw = merged_raw[merged_raw["_merge"] == "left_only"].drop(
                columns=drop_raw, errors="ignore"
            )

    return df_in, df_raw


def _compute_min_duties(df_raw: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Process raw API session output into a per-lane minimum-duty DataFrame."""
    _DATA_TYPES: Dict[str, str] = {
        "_tx_id": "object",
        "coo": "object", "coi": "object", "hs": "object",
        "custUnitP": "float64", "cur": "object", "qnty": "float64",
        "status": "object", "comment": "object", "hsNum": "object",
        "calcName": "object", "incoCalcBasis": "object", "Program": "object",
        "ratePct": "float64", "rateDesc": "object",
        "calcVal": "float64", "calcValCur": "object",
    }

    df = df_raw.copy()
    if "Program" in df.columns:
        df = df[~df["Program"].isna()].copy()

    df = df[[c for c in _DATA_TYPES if c in df.columns]].copy()
    for col, dtype in _DATA_TYPES.items():
        if col in df.columns:
            try:
                df[col] = df[col].astype(dtype)
            except Exception:
                pass

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].fillna("").infer_objects(copy=False)

    df = df.rename(columns={"hsNum": "hs alternative", "hs": "hs code"})

    if "calcName" not in df.columns:
        return None
    df_duty = df[df["calcName"] == "DUTY"].copy()
    if df_duty.empty:
        return None

    group_cols = ["coo", "coi", "hs code", "custUnitP", "cur", "qnty"]
    if "_tx_id" in df_duty.columns:
        group_cols = ["_tx_id"] + group_cols
    df_min = df_duty.loc[df_duty.groupby(group_cols)["calcVal"].idxmin()].copy()
    df_min = df_min.rename(columns={
        "custUnitP": "customs value", "cur": "cv currency", "qnty": "weight",
        "Program": "Min Duty Program", "ratePct": "Min Duty Rate",
        "rateDesc": "Min Duty Program Description",
        "calcVal": "Minimum Duties", "calcValCur": "Currency Min Duties",
    })

    df_default_mfn = df_duty[
        df_duty["Program"].astype(str).str.upper().isin(["DEFAULT", "MOST FAVOURED NATION (MFN)"])
    ].copy()
    if not df_default_mfn.empty:
        df_default_mfn = df_default_mfn.rename(columns={
            "custUnitP": "customs value", "cur": "cv currency", "qnty": "weight"
        })
        merge_cols = ["coo", "coi", "hs code", "customs value", "cv currency", "weight"]
        if "_tx_id" in df_default_mfn.columns and "_tx_id" in df_min.columns:
            merge_cols = ["_tx_id"] + merge_cols
        df_def_min = df_default_mfn.loc[
            df_default_mfn.groupby(merge_cols)["calcVal"].idxmin()
        ].copy()
        df_def_min = df_def_min.rename(columns={
            "ratePct": "Default Duty Rate",
            "rateDesc": "Default Duty Program Description",
            "calcVal": "Default Duties",
            "calcValCur": "Currency Default Duties",
        })
        df_def_min["Default Duty Program"] = df_def_min["Program"]
        df_min = df_min.merge(
            df_def_min[merge_cols + [
                "Default Duty Program", "Default Duty Rate",
                "Default Duty Program Description", "Default Duties", "Currency Default Duties",
            ]],
            on=merge_cols,
            how="left",
        )

    return df_min


def _assemble_merged(
    df_in: pd.DataFrame,
    df_min: pd.DataFrame,
    ref_date: str,
) -> pd.DataFrame:
    df_min = df_min.copy()
    df_min["Input Date"] = ref_date

    merge_cols = ["coo", "coi", "hs code", "customs value", "cv currency", "weight"]
    if "_tx_id" in df_in.columns and "_tx_id" in df_min.columns:
        merge_cols = ["_tx_id"] + merge_cols

    df_merged = pd.merge(df_in, df_min, on=merge_cols, how="left")

    col_order = [
        "date", "invoice number", "material number",
        "coo", "coi", "hs code", "customs value", "cv currency", "weight",
        "duty paid", "dp currency", "status", "comment", "hs alternative",
        "calcName", "incoCalcBasis",
        "Min Duty Program", "Min Duty Rate", "Min Duty Program Description",
        "Minimum Duties", "Currency Min Duties",
        "Default Duty Program", "Default Duty Rate", "Default Duty Program Description",
        "Default Duties", "Currency Default Duties",
        "Input Date",
        # Required for duplicate detection — must survive to DB save
        "customs value original", "cv currency original",
    ]
    df_merged = df_merged[[c for c in col_order if c in df_merged.columns]]

    if "customs value" in df_merged.columns:
        df_merged["customs value"] = pd.to_numeric(df_merged["customs value"], errors="coerce")
    if "weight" in df_merged.columns:
        df_merged["weight"] = pd.to_numeric(df_merged["weight"], errors="coerce")

    return df_merged


def _convert_result_currencies(
    df_merged: pd.DataFrame,
    logs: List[Dict[str, Any]],
) -> pd.DataFrame:
    try:
        fx_map = _fetch_fx_rates_eur()
        df_merged = df_merged.copy()
        for val_col, ccy_col in [
            ("duty paid", "dp currency"),
            ("Minimum Duties", "Currency Min Duties"),
            ("Default Duties", "Currency Default Duties"),
        ]:
            if val_col not in df_merged.columns or ccy_col not in df_merged.columns:
                continue
            ccy = df_merged[ccy_col].astype(str).str.strip().str.upper()
            rate = ccy.map(fx_map)
            val = pd.to_numeric(df_merged[val_col], errors="coerce")
            no_rate = rate.isna()
            missing_ccy = sorted(
                ccy[no_rate & ccy.notna() & (ccy != "NAN") & (ccy != "")].unique().tolist()
            )
            if missing_ccy:
                logs.append({"event": "fx_missing_currency", "col": val_col, "currencies": missing_ccy})
            df_merged[val_col] = val.where(no_rate, (val * rate).round(2))
            df_merged[ccy_col] = ccy.where(no_rate, "EUR")
    except Exception as _fx_err:
        logs.append({
            "event": "fx_conversion_warning",
            "ts": time.time(),
            "error": str(_fx_err),
        })
    return df_merged


# -----------------------------
# Postproceso (orchestrator)
# -----------------------------

def postprocess_results(
    ok_input_df: pd.DataFrame,
    ok_df: pd.DataFrame,
    failed_df: pd.DataFrame,
    df_missing: pd.DataFrame,
    ref_date: str,
    logs: List[Dict[str, Any]],
) -> pd.DataFrame:
    session_output = _extract_session_output(logs)
    df_raw = pd.DataFrame.from_dict(session_output).T if session_output else pd.DataFrame()

    combined_failed = _build_combined_failed(failed_df, df_missing)
    df_in, df_raw = _filter_failed_from_inputs(ok_input_df.copy(), df_raw, combined_failed)

    if df_raw.empty:
        return df_in.copy()

    df_min = _compute_min_duties(df_raw)
    if df_min is None:
        return df_in.copy()

    df_merged = _assemble_merged(df_in, df_min, ref_date)
    df_merged = _convert_result_currencies(df_merged, logs)

    return df_merged


# Max rows shown in the HTML report's results table; a notice is appended when truncated.
REPORT_ROW_CAP = 500

# -----------------------------
# HTML Report generator
# -----------------------------

def build_report_html(
    df_merged: pd.DataFrame,
    df_failed: Optional[pd.DataFrame],
    df_missing: Optional[pd.DataFrame],
    run_summary: Optional[Dict[str, Any]],
    ref_date: str,
    account_label: str = "",
    environment: str = "",
    df_initiatives: Optional[pd.DataFrame] = None,
) -> bytes:
    """
    Build a self-contained HTML report summarising API run results and initiative portfolio.
    Returns UTF-8-encoded bytes ready for st.download_button.
    """
    import datetime
    import html as _html

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── KPIs ─────────────────────────────────────────────────────────────────
    df = df_merged.copy() if df_merged is not None and not df_merged.empty else pd.DataFrame()

    customs_val = pd.to_numeric(df["customs value"]  if "customs value"  in df.columns else pd.Series(dtype=float), errors="coerce").fillna(0)
    min_duties  = pd.to_numeric(df["Minimum Duties"] if "Minimum Duties" in df.columns else pd.Series(dtype=float), errors="coerce").fillna(0)
    def_duties  = pd.to_numeric(df["Default Duties"] if "Default Duties" in df.columns else pd.Series(dtype=float), errors="coerce").fillna(0)
    duty_paid   = pd.to_numeric(df["duty paid"]      if "duty paid"      in df.columns else pd.Series(dtype=float), errors="coerce").fillna(0)

    customs_sum  = float(customs_val.sum())
    min_sum      = float(min_duties.sum())
    def_sum      = float(def_duties.sum())
    paid_sum     = float(duty_paid.sum())
    overpaid_sum = float((duty_paid - min_duties).clip(lower=0).sum())

    # Lane count always from the data (report may cover multiple runs)
    ok_n      = len(df)
    failed_n  = int(run_summary.get("failed",  0)) if run_summary else (len(df_failed)  if df_failed  is not None else 0)
    missing_n = int(run_summary.get("missing", 0)) if run_summary else (len(df_missing) if df_missing is not None else 0)

    # ── Formatting helpers ────────────────────────────────────────────────────
    def _eur(v):
        if v is None:
            return "N/A"
        v = float(v)
        sign = "-" if v < 0 else ""
        av = abs(v)
        return f"{sign}€{int(round(av)):,}"

    def _int(v):
        try:
            return f"{int(v):,}"
        except Exception:
            return "0"

    def _pct(v):
        return f"{float(v):.2f}%" if v is not None else "N/A"

    def _e(s):
        return _html.escape(str(s) if s is not None else "")

    # ── Top findings ──────────────────────────────────────────────────────────
    top_coi_overpaid = pd.DataFrame()
    top_coi_paid     = pd.DataFrame()
    top_hs           = pd.DataFrame()

    if not df.empty:
        if {"coi", "duty paid", "Minimum Duties"}.issubset(df.columns):
            tmp = df.copy()
            tmp["_op"] = (
                pd.to_numeric(tmp["duty paid"],      errors="coerce").fillna(0)
                - pd.to_numeric(tmp["Minimum Duties"], errors="coerce").fillna(0)
            ).clip(lower=0)
            top_coi_overpaid = (
                tmp.groupby("coi")["_op"].sum()
                .sort_values(ascending=False).head(5)
                .reset_index()
                .rename(columns={"coi": "COI", "_op": "Overpaid Duties (EUR)"})
            )

        if {"coi", "duty paid"}.issubset(df.columns):
            tmp = df.copy()
            tmp["duty paid"] = pd.to_numeric(tmp["duty paid"], errors="coerce").fillna(0)
            top_coi_paid = (
                tmp.groupby("coi")["duty paid"].sum()
                .sort_values(ascending=False).head(5)
                .reset_index()
                .rename(columns={"coi": "COI", "duty paid": "Duty Paid (EUR)"})
            )

        if {"hs code", "customs value"}.issubset(df.columns):
            tmp = df.copy()
            tmp["customs value"] = pd.to_numeric(tmp["customs value"], errors="coerce").fillna(0)
            top_hs = (
                tmp.groupby("hs code")["customs value"].sum()
                .sort_values(ascending=False).head(5)
                .reset_index()
                .rename(columns={"hs code": "HS Code", "customs value": "Customs Value (EUR)"})
            )

    # ── Monthly trend data (for chart) ───────────────────────────────────────
    chart_labels:    List[str]   = []
    chart_duty_paid: List[float] = []
    chart_min_duties: List[float] = []
    chart_overpaid:  List[float] = []

    if not df.empty:
        _date_col = next((c for c in ["Input Date", "input_date", "date", "ref_date"] if c in df.columns), None)
        if _date_col and "duty paid" in df.columns:
            _tmp = df.copy()
            _tmp["_dt"] = pd.to_datetime(_tmp[_date_col], errors="coerce")
            _tmp = _tmp.dropna(subset=["_dt"])
            if not _tmp.empty:
                _tmp["_month"]   = _tmp["_dt"].dt.to_period("M")
                _tmp["_dp"]      = pd.to_numeric(_tmp["duty paid"],      errors="coerce").fillna(0)
                _tmp["_md"]      = pd.to_numeric(_tmp.get("Minimum Duties", pd.Series([0.0]*len(_tmp), index=_tmp.index)), errors="coerce").fillna(0) if "Minimum Duties" in _tmp.columns else 0.0
                _tmp["_op"]      = (_tmp["_dp"] - _tmp["_md"]).clip(lower=0)
                _monthly = (
                    _tmp.groupby("_month")
                    .agg(_dp=("_dp", "sum"), _md=("_md", "sum"), _op=("_op", "sum"))
                    .reset_index()
                    .sort_values("_month")
                )
                chart_labels     = [str(p) for p in _monthly["_month"]]
                chart_duty_paid  = _monthly["_dp"].round(2).tolist()
                chart_min_duties = _monthly["_md"].round(2).tolist()
                chart_overpaid   = _monthly["_op"].round(2).tolist()

    # ── Table helpers ─────────────────────────────────────────────────────────
    def _table(df_t, money_cols=None):
        if df_t is None or df_t.empty:
            return "<p class='no-data'>No data available.</p>"
        money_cols = set(money_cols or [])
        headers = "".join(f"<th>{_e(c)}</th>" for c in df_t.columns)
        rows = ""
        for _, row in df_t.iterrows():
            cells = ""
            for col in df_t.columns:
                val = row[col]
                if col in money_cols:
                    cells += f"<td class='num'>{_eur(val)}</td>"
                else:
                    cells += f"<td>{_e(val)}</td>"
            rows += f"<tr>{cells}</tr>"
        return (
            f"<table><thead><tr>{headers}</tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    # ── Results table (key columns, capped at 500 rows) ───────────────────────
    KEY_COLS = [
        "date", "invoice number", "material number",
        "coo", "coi", "hs code",
        "customs value", "cv currency",
        "duty paid", "dp currency",
        "Min Duty Program", "Min Duty Rate", "Minimum Duties", "Currency Min Duties",
        "Default Duty Program", "Default Duty Rate", "Default Duties", "Currency Default Duties",
        "status", "comment",
    ]
    display_cols = [c for c in KEY_COLS if c in df.columns]
    df_disp = df[display_cols].head(REPORT_ROW_CAP) if display_cols else df.head(REPORT_ROW_CAP)
    truncated = len(df) > REPORT_ROW_CAP

    res_headers = "".join(f"<th>{_e(c)}</th>" for c in df_disp.columns)
    MONEY_RESULT_COLS = {"customs value", "duty paid", "Minimum Duties", "Default Duties"}
    res_rows = ""
    for _, row in df_disp.iterrows():
        cells = ""
        for col in df_disp.columns:
            val = row[col]
            s = "" if pd.isna(val) else str(val)
            cells += f"<td class='num'>{_eur(val)}</td>" if col in MONEY_RESULT_COLS else f"<td>{_e(s)}</td>"
        res_rows += f"<tr>{cells}</tr>"

    trunc_badge = (
        f"<span class='badge warn'>First {REPORT_ROW_CAP} of {_int(len(df))} rows</span>"
        if truncated else ""
    )

    # ── Initiative portfolio metrics ──────────────────────────────────────────
    _ini = df_initiatives.copy() if (df_initiatives is not None and not df_initiatives.empty) else pd.DataFrame()
    if not _ini.empty:
        for _ic in ["duty_paid", "min_duties", "savings_realized", "reimbursements", "potential_reimbursements"]:
            if _ic in _ini.columns:
                _ini[_ic] = pd.to_numeric(_ini[_ic], errors="coerce").fillna(0.0)
        _ini["_pre_op"] = (_ini["duty_paid"] - _ini["min_duties"]).clip(lower=0) if "duty_paid" in _ini.columns else 0.0
        _sr = _ini["savings_realized"] if "savings_realized" in _ini.columns else pd.Series([0.0]*len(_ini), index=_ini.index)
        _rb = _ini["reimbursements"] if "reimbursements" in _ini.columns else pd.Series([0.0]*len(_ini), index=_ini.index)
        _ini["_realized"] = _sr.fillna(0.0) + _rb.fillna(0.0)
        _ini_status = _ini["status"] if "status" in _ini.columns else pd.Series([""] * len(_ini), index=_ini.index)
        ini_n           = len(_ini)
        ini_identified  = int((_ini_status == "Identified").sum())
        ini_validated   = int((_ini_status == "Validated").sum())
        ini_completed   = int((_ini_status == "Completed").sum())
        ini_discarded   = int((_ini_status == "Discarded").sum())
        ini_pre_total   = float(_ini["_pre_op"].sum())
        ini_real_total  = float(_ini["_realized"].sum())
        ini_reimb_total = float(_rb.fillna(0.0).sum())
        ini_capture     = (ini_real_total / ini_pre_total * 100) if ini_pre_total > 0 else None

        # Status breakdown table
        _st_rows = ""
        for _st in ["Identified", "Validated", "Completed", "Discarded"]:
            _sm = _ini[_ini_status == _st] if "status" in _ini.columns else pd.DataFrame()
            if _sm.empty:
                continue
            _n  = len(_sm)
            _pr = float(_sm["_pre_op"].sum())
            _re = float(_sm["_realized"].sum())
            _pct_re = f"{_re/_pr*100:.0f}%" if _pr > 0 else "—"
            _color = {"Identified": "#7500C0", "Validated": "#A100FF", "Completed": "#1a7a40", "Discarded": "#888"}.get(_st, "#333")
            _st_rows += (
                f"<tr><td><span style='background:{_color};color:#fff;padding:2px 10px;"
                f"border-radius:999px;font-size:11px;font-weight:700;'>{_e(_st)}</span></td>"
                f"<td class='num'>{_int(_n)}</td>"
                f"<td class='num'>{_eur(_pr)}</td>"
                f"<td class='num'>{_eur(_re)}</td>"
                f"<td class='num'>{_pct_re}</td></tr>"
            )
        ini_status_table = (
            f"<table><thead><tr>"
            f"<th>Status</th><th>Initiatives</th>"
            f"<th>Overpaid PRE (€)</th><th>Savings Realized (€)</th><th>Realization Rate</th>"
            f"</tr></thead><tbody>{_st_rows}</tbody></table>"
            if _st_rows else "<p class='no-data'>No initiative data available.</p>"
        )

        # Top initiatives table (top 15 by PRE overpaid)
        _top_ini = _ini.nlargest(15, "_pre_op") if not _ini.empty else pd.DataFrame()
        _top_rows = ""
        for _, _tr in _top_ini.iterrows():
            _tst = str(_tr.get("status", ""))
            _tcolor = {"Identified": "#7500C0", "Validated": "#A100FF", "Completed": "#1a7a40", "Discarded": "#888"}.get(_tst, "#333")
            _top_rows += (
                f"<tr>"
                f"<td>{_e(str(_tr.get('coo','') or ''))}</td>"
                f"<td>{_e(str(_tr.get('coi','') or ''))}</td>"
                f"<td>{_e(str(_tr.get('hs_code','') or ''))}</td>"
                f"<td>{_e(str(_tr.get('min_duty_program','') or ''))}</td>"
                f"<td><span style='background:{_tcolor};color:#fff;padding:2px 8px;"
                f"border-radius:999px;font-size:11px;font-weight:700;'>{_e(_tst)}</span></td>"
                f"<td class='num'>{_eur(_tr['_pre_op'])}</td>"
                f"<td class='num'>{_eur(_tr['_realized'])}</td>"
                f"</tr>"
            )
        ini_top_table = (
            f"<table><thead><tr>"
            f"<th>COO</th><th>COI</th><th>HS Code</th><th>Min Duty Program</th><th>Status</th>"
            f"<th>Overpaid PRE (€)</th><th>Savings Realized (€)</th>"
            f"</tr></thead><tbody>{_top_rows}</tbody></table>"
            if _top_rows else "<p class='no-data'>No initiatives to display.</p>"
        )

        ini_narrative = (
            f"The initiative portfolio comprises <strong>{_int(ini_n)} initiative(s)</strong>: "
            f"{_int(ini_identified)} Identified, {_int(ini_validated)} Validated, "
            f"{_int(ini_completed)} Completed and {_int(ini_discarded)} Discarded. "
            f"Total overpaid duties identified across all initiatives amount to "
            f"<strong>{_eur(ini_pre_total)}</strong>. Savings realized to date total "
            f"<strong>{_eur(ini_real_total)}</strong>"
            + (f", representing a <strong>Savings Capture Rate of {_pct(ini_capture)}</strong>" if ini_capture is not None else "")
            + f". Reimbursements collected total <strong>{_eur(ini_reimb_total)}</strong>."
        )
    else:
        ini_n = ini_identified = ini_validated = ini_completed = ini_discarded = 0
        ini_pre_total = ini_real_total = ini_reimb_total = 0.0
        ini_capture = None
        ini_status_table = "<p class='no-data'>No initiative data available for this report.</p>"
        ini_top_table    = "<p class='no-data'>No initiatives to display.</p>"
        ini_narrative    = "No initiative data is available for this reporting period."

    # ── Narrative paragraph ───────────────────────────────────────────────────
    capture_rate = (ini_real_total / overpaid_sum * 100) if overpaid_sum > 0 else None
    fail_txt = (
        f", with <strong>{_int(failed_n)} failure(s)</strong>"
        f" and <strong>{_int(missing_n)} row(s) skipped</strong> due to missing input data"
        if (failed_n or missing_n) else ""
    )
    narrative = (
        f"This report covers the e2open import duty analysis for reference date "
        f"<strong>{_e(ref_date)}</strong>, encompassing <strong>{_int(ok_n)} trade lane(s)</strong>"
        f"{fail_txt}. "
        f"Total customs value under review amounts to <strong>{_eur(customs_sum)}</strong>, "
        f"with duties paid of <strong>{_eur(paid_sum)}</strong>. "
        f"Overpaid duties (Duty Paid − Minimum Duties) total <strong>{_eur(overpaid_sum)}</strong>. "
        + (f"The initiative portfolio tracks <strong>{_int(ini_n)} initiative(s)</strong> "
           f"with <strong>{_eur(ini_real_total)}</strong> in confirmed savings realised"
           + (f" (Savings Capture Rate: <strong>{_pct(capture_rate)}</strong>)" if capture_rate is not None else "")
           + "."
           if ini_n > 0 else "")
    )

    # ── Inline CSS ────────────────────────────────────────────────────────────
    css = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f2f8; color: #1a1a2e; font-size: 14px; }

.report-header {
  background: linear-gradient(135deg, #460073 0%, #A100FF 60%, #7500C0 100%);
  color: white; padding: 32px 44px 28px 44px;
}
.report-header h1 { font-size: 28px; font-weight: 900; margin-bottom: 6px; }
.report-header .meta { font-size: 12.5px; opacity: 0.85; margin-top: 6px; }
.report-header .meta span { margin-right: 22px; }

.section {
  background: white; margin: 20px 44px; border-radius: 12px;
  padding: 26px 30px; box-shadow: 0 2px 14px rgba(0,0,0,0.07);
}
.section h2 {
  font-size: 16px; font-weight: 700; color: #460073;
  border-bottom: 2px solid #A100FF; padding-bottom: 8px; margin-bottom: 18px;
}
.section h3 { font-size: 13.5px; font-weight: 600; color: #7500C0; margin: 16px 0 10px; }

.kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.kpi-card {
  background: #faf5ff; border: 1px solid #e6dcff;
  border-radius: 10px; padding: 14px 16px; border-top: 3px solid #A100FF;
}
.kpi-label { font-size: 10.5px; color: #7500C0; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
.kpi-value { font-size: 22px; font-weight: 800; color: #1a1a2e; }
.kpi-value.good { color: #1a7a40; }
.kpi-value.bad  { color: #c0392b; }
.kpi-sub { font-size: 11px; color: #999; margin-top: 3px; }

.three-col { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }

.chart-wrap {
  margin-top: 28px;
  background: white;
  border-radius: 10px;
  padding: 24px 20px 16px 20px;
  border: 1px solid #e6dcff;
}
.chart-wrap h3 {
  color: #460073 !important;
  margin-bottom: 16px !important;
  margin-top: 0 !important;
}

table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead tr { background: #460073; color: white; }
th { padding: 9px 12px; text-align: left; font-weight: 600; font-size: 12px; }
tbody tr:nth-child(even) { background: #faf5ff; }
tbody tr:hover { background: #f0e8ff; }
td { padding: 7px 12px; border-bottom: 1px solid #f0e8ff; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }

.results-wrap {
  overflow-x: auto;
  overflow-y: auto;
  max-height: 480px;
  border: 1px solid #e6dcff;
  border-radius: 8px;
}
.results-wrap thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #460073;
}
.no-data { color: #aaa; font-style: italic; font-size: 13px; }
.narrative { color: #444; line-height: 1.8; font-size: 13.5px; }

.badge {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 600; margin-left: 8px; vertical-align: middle;
}
.badge.warn { background: #fff3cd; color: #856404; border: 1px solid #ffe083; }

.footer { text-align: center; color: #aaa; font-size: 11px; padding: 22px 44px 28px; }

.ini-kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 22px; }
.ini-kpi { background: #faf5ff; border: 1px solid #e6dcff; border-radius: 10px; padding: 12px 14px; border-top: 3px solid #7500C0; }
.ini-kpi .kpi-label { color: #460073; }
.ini-kpi .kpi-value { font-size: 20px; }

@media print {
  body { background: white; }
  .section { margin: 10px 0; box-shadow: none; page-break-inside: avoid; }
  .report-header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""

    # ── Serialise chart data ──────────────────────────────────────────────────
    import json as _json
    _chart_json = _json.dumps({
        "labels":     chart_labels,
        "dutyPaid":   chart_duty_paid,
        "minDuties":  chart_min_duties,
        "overpaid":   chart_overpaid,
    }).replace("</", "<\\/")  # prevent </script> injection when embedded in HTML

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    account_meta = f"<span>&#128100; Account: <strong>{_e(account_label)}</strong></span>" if account_label else ""
    env_meta     = f"<span>&#127758; Environment: <strong>{_e(environment)}</strong></span>" if environment else ""

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Duty Optimizer Report &mdash; {_e(ref_date)}</title>
<style>{css}</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>

<div class="report-header">
  <h1>Duty Analysis Report</h1>
  <div class="meta">
    <span>&#128197; Reference date: <strong>{_e(ref_date)}</strong></span>
    <span>&#9201; Generated: <strong>{_e(generated_at)}</strong></span>
    {account_meta}
    {env_meta}
  </div>
</div>

<div class="section">
  <h2>Executive Summary</h2>
  <p class="narrative">{narrative}</p>
  <br>
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Lanes processed</div>
      <div class="kpi-value">{_int(ok_n)}</div>
      <div class="kpi-sub">Successful API responses</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Customs Value</div>
      <div class="kpi-value">{_eur(customs_sum)}</div>
      <div class="kpi-sub">EUR equivalent</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Duties Paid</div>
      <div class="kpi-value">{_eur(paid_sum)}</div>
      <div class="kpi-sub">EUR equivalent</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Minimum Duties</div>
      <div class="kpi-value">{_eur(min_sum)}</div>
      <div class="kpi-sub">Best available program</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Overpaid Duties</div>
      <div class="kpi-value {'bad' if overpaid_sum > 0 else 'good'}">{_eur(overpaid_sum)}</div>
      <div class="kpi-sub">Duty Paid &minus; Minimum Duties</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Savings Realized</div>
      <div class="kpi-value good">{_eur(ini_real_total)}</div>
      <div class="kpi-sub">FTA savings + reimbursements</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Savings Capture Rate</div>
      <div class="kpi-value {'good' if (capture_rate or 0) >= 50 else ''}">{_pct(capture_rate)}</div>
      <div class="kpi-sub">Savings Realized &divide; Overpaid Duties</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Failed</div>
      <div class="kpi-value {'bad' if failed_n > 0 else 'good'}">{_int(failed_n)}</div>
      <div class="kpi-sub">API failures after retries</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Missing / Skipped</div>
      <div class="kpi-value">{_int(missing_n)}</div>
      <div class="kpi-sub">Rows with incomplete data</div>
    </div>
  </div>
</div>

<div class="section">
  <h2>Key Findings</h2>
  <div class="three-col">
    <div>
      <h3>Top 5 COI — Overpaid Duties</h3>
      {_table(top_coi_overpaid, money_cols=["Overpaid Duties (EUR)"])}
    </div>
    <div>
      <h3>Top 5 COI — Duties Paid</h3>
      {_table(top_coi_paid, money_cols=["Duty Paid (EUR)"])}
    </div>
    <div>
      <h3>Top 5 HS Codes — Customs Value</h3>
      {_table(top_hs, money_cols=["Customs Value (EUR)"])}
    </div>
  </div>
  <div class="chart-wrap">
    <h3>Monthly Duty Paid vs Minimum Duties (amber area = Overpaid)</h3>
    <canvas id="trendChart" height="90"></canvas>
  </div>
</div>

<div class="section">
  <h2>Initiative Portfolio</h2>
  <p class="narrative">{ini_narrative}</p>
  <br>
  <div class="ini-kpi-grid">
    <div class="ini-kpi">
      <div class="kpi-label">Total Initiatives</div>
      <div class="kpi-value">{_int(ini_n)}</div>
      <div class="kpi-sub">{_int(ini_identified)} Identified · {_int(ini_validated)} Validated · {_int(ini_completed)} Completed</div>
    </div>
    <div class="ini-kpi">
      <div class="kpi-label">Overpaid Duties</div>
      <div class="kpi-value">{_eur(ini_pre_total)}</div>
      <div class="kpi-sub">Identified savings opportunity</div>
    </div>
    <div class="ini-kpi">
      <div class="kpi-label">Savings Realized</div>
      <div class="kpi-value good">{_eur(ini_real_total)}</div>
      <div class="kpi-sub">FTA savings + reimbursements</div>
    </div>
    <div class="ini-kpi">
      <div class="kpi-label">Savings Capture Rate</div>
      <div class="kpi-value {'good' if (ini_capture or 0) >= 50 else ''}">{_pct(ini_capture)}</div>
      <div class="kpi-sub">Realized &divide; Overpaid Duties</div>
    </div>
  </div>
  <h3>Savings by Initiative Status</h3>
  {ini_status_table}
  <br>
  <h3>Top Initiatives by Identified Potential</h3>
  {ini_top_table}
</div>

<div class="section">
  <h2>Detailed Results {trunc_badge}</h2>
  <div class="results-wrap">
    <table>
      <thead><tr>{res_headers}</tr></thead>
      <tbody>{res_rows}</tbody>
    </table>
  </div>
</div>

<div class="footer">
  Generated by Duty Optimizer 2.0 &mdash; {_e(generated_at)}
</div>

<script>
(function() {{
  const d = {_chart_json};
  if (!d.labels || d.labels.length === 0) return;

  function fmtEur(v) {{
    var a = Math.abs(v);
    if (a >= 1e6) return '\u20ac' + (v/1e6).toFixed(1) + 'M';
    if (a >= 1e3) return '\u20ac' + (v/1e3).toFixed(0) + 'k';
    return '\u20ac' + v.toFixed(0);
  }}

  new Chart(document.getElementById('trendChart'), {{
    type: 'line',
    data: {{
      labels: d.labels,
      datasets: [
        {{
          label: 'Minimum Duties',
          data: d.minDuties,
          borderColor: '#7500C0',
          borderWidth: 2,
          borderDash: [5, 4],
          backgroundColor: 'rgba(117,0,192,0.15)',
          pointRadius: 3,
          pointBackgroundColor: '#7500C0',
          fill: 'origin',
          tension: 0.3,
          order: 2,
        }},
        {{
          label: 'Duty Paid',
          data: d.dutyPaid,
          borderColor: '#A100FF',
          borderWidth: 2.5,
          backgroundColor: 'rgba(161,0,255,0.28)',
          pointRadius: 4,
          pointBackgroundColor: '#A100FF',
          pointBorderColor: '#fff',
          pointBorderWidth: 1.5,
          fill: '-1',
          tension: 0.3,
          order: 1,
        }}
      ]
    }},
    options: {{
      responsive: true,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ labels: {{ color: '#333', font: {{ size: 12 }} }} }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{ return ' ' + ctx.dataset.label + ': ' + fmtEur(ctx.parsed.y); }},
            afterBody: function(items) {{
              var dp = items.find(function(i) {{ return i.datasetIndex === 1; }});
              var md = items.find(function(i) {{ return i.datasetIndex === 0; }});
              if (dp && md) {{
                var op = Math.max(0, dp.parsed.y - md.parsed.y);
                return ['', 'Overpaid: ' + fmtEur(op)];
              }}
              return [];
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: '#555', font: {{ size: 11 }} }}, grid: {{ color: 'rgba(0,0,0,0.06)' }} }},
        y: {{
          ticks: {{ color: '#333', font: {{ size: 11 }}, callback: fmtEur }},
          grid:  {{ color: 'rgba(0,0,0,0.07)' }}
        }}
      }}
    }}
  }});
}})();
</script>

</body>
</html>"""

    return html_doc.encode("utf-8")


# -----------------------------
# DB corrections: export / parse / diff
# -----------------------------

# Columns included in the export (display names, in order)
_EXPORT_EDITABLE_COLS = [
    "invoice number", "material number", "date",
    "coo", "coi", "hs code",
    "customs value", "cv currency", "weight",
    "duty paid", "dp currency",
    "hs alternative", "comment",
]
_EXPORT_INFO_COLS = [
    "ref_date", "status",
    "Min Duty Program", "Min Duty Rate", "Minimum Duties",
    "Default Duty Program", "Default Duty Rate", "Default Duties",
    "Input Date",
]


def export_merged_to_excel(df: pd.DataFrame) -> bytes:
    """
    Export a merged_results DataFrame to Excel bytes for the corrections workflow.

    Prepends two control columns:
      _db_id  — DB primary key (do NOT modify or delete this column)
      _delete — set to TRUE to delete this row on reimport

    Returns bytes ready for st.download_button.
    """
    import io

    out = df.copy()

    if "id" in out.columns:
        out.insert(0, "_db_id", out["id"])
    else:
        out.insert(0, "_db_id", None)
    out.insert(1, "_delete", False)

    # Drop columns that are internal and shouldn't clutter the sheet
    for col in ["id", "run_id", "saved_at"]:
        if col in out.columns:
            out = out.drop(columns=[col])

    # Reorder: control → editable → info → rest
    ordered = ["_db_id", "_delete"]
    for col in _EXPORT_EDITABLE_COLS:
        if col in out.columns:
            ordered.append(col)
    for col in _EXPORT_INFO_COLS:
        if col in out.columns:
            ordered.append(col)
    for col in out.columns:
        if col not in ordered:
            ordered.append(col)

    out = out[[c for c in ordered if c in out.columns]]

    buf = io.BytesIO()
    out.to_excel(buf, index=False, sheet_name="Corrections")
    return buf.getvalue()


def _corr_vals_equal(a, b) -> bool:
    """Return True if two values are considered equal (NaN-safe, float-rounded)."""
    import math
    # Both None / NaN
    try:
        a_nan = a is None or (isinstance(a, float) and math.isnan(a)) or pd.isna(a)
        b_nan = b is None or (isinstance(b, float) and math.isnan(b)) or pd.isna(b)
    except (TypeError, ValueError):
        a_nan = b_nan = False
    if a_nan and b_nan:
        return True
    if a_nan or b_nan:
        return False
    # Numeric: round to 2dp
    try:
        return round(float(a), 2) == round(float(b), 2)
    except (TypeError, ValueError):
        pass
    return str(a).strip() == str(b).strip()


def _coerce_correction(val, db_col: str):
    """Coerce an imported Excel value to the right Python type for the DB column."""
    _numeric = {"customs_value", "weight", "duty_paid",
                "min_duty_rate", "default_duty_rate", "minimum_duties", "default_duties"}
    if db_col in _numeric:
        try:
            return float(val)
        except (TypeError, ValueError):
            return None
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return s if s else None


def parse_corrections_excel(
    uploaded_file,
    df_current: pd.DataFrame,
) -> tuple:
    """
    Parse a corrections Excel file (produced by export_merged_to_excel) and
    compute the diff against the current DB state.

    Parameters
    ----------
    uploaded_file : file-like object from st.file_uploader
    df_current    : current merged_results DataFrame (must contain 'id' column)

    Returns
    -------
    (diff, errors)
      diff   : dict with keys "updates", "deletes", "update_preview", "delete_preview"
               or None if parsing failed.
      errors : list[str] — non-fatal warnings if non-empty; may coexist with a valid diff.
    """
    from src.db import EDITABLE_COL_DF_TO_DB

    errors: list = []

    try:
        df_corr = pd.read_excel(uploaded_file, sheet_name="Corrections")
    except Exception as exc:
        return None, [f"Could not read Excel file: {exc}"]

    if "_db_id" not in df_corr.columns:
        return None, [
            "The file does not contain the '_db_id' column. "
            "Only use files exported from Duty Optimizer."
        ]

    # Normalise _db_id to int
    df_corr["_db_id"] = pd.to_numeric(df_corr["_db_id"], errors="coerce")
    n_bad = int(df_corr["_db_id"].isna().sum())
    if n_bad:
        errors.append(f"{n_bad} row(s) with invalid _db_id ignored.")
    df_corr = df_corr[df_corr["_db_id"].notna()].copy()
    df_corr["_db_id"] = df_corr["_db_id"].astype(int)

    # Validate ids exist in the current dataset
    if "id" in df_current.columns:
        valid_ids = set(df_current["id"].dropna().astype(int).tolist())
        unknown = set(df_corr["_db_id"].tolist()) - valid_ids
        if unknown:
            sample = sorted(unknown)[:5]
            suffix = "..." if len(unknown) > 5 else ""
            errors.append(
                f"{len(unknown)} _db_id(s) not found in DB: "
                f"{sample}{suffix}. They will be ignored."
            )
            df_corr = df_corr[df_corr["_db_id"].isin(valid_ids)]

    if df_corr.empty:
        return None, errors + ["No valid rows remaining to process."]

    # Split deletes from updates
    if "_delete" in df_corr.columns:
        del_mask = (
            df_corr["_delete"]
            .astype(str).str.strip().str.upper()
            .isin(["TRUE", "1", "YES", "SI", "SÍ", "VERDADERO"])
        )
        delete_ids = df_corr.loc[del_mask, "_db_id"].astype(int).tolist()
        df_updates = df_corr[~del_mask].copy()
    else:
        delete_ids = []
        df_updates = df_corr.copy()

    # Index current df by id for fast lookup
    current_by_id = (
        df_current.set_index("id") if "id" in df_current.columns else pd.DataFrame()
    )

    updates: list = []
    preview_rows: list = []

    for _, row in df_updates.iterrows():
        rid = int(row["_db_id"])
        if rid not in current_by_id.index:
            continue

        current = current_by_id.loc[rid]
        row_changes: dict = {"id": rid}
        preview: dict = {"id": rid}

        for df_col, db_col in EDITABLE_COL_DF_TO_DB.items():
            if df_col not in row.index:
                continue
            new_val = row[df_col]
            old_val = current.get(df_col) if df_col in current.index else None

            if not _corr_vals_equal(old_val, new_val):
                row_changes[db_col] = _coerce_correction(new_val, db_col)
                preview[df_col] = f"{old_val}  →  {new_val}"

        if len(row_changes) > 1:  # has actual changes beyond just "id"
            updates.append(row_changes)
            preview_rows.append(preview)

    update_preview = pd.DataFrame(preview_rows) if preview_rows else pd.DataFrame()

    if delete_ids and "id" in df_current.columns:
        id_cols = [c for c in ["id", "invoice number", "material number", "coo", "coi", "hs code"]
                   if c in df_current.columns]
        delete_preview = df_current[df_current["id"].isin(delete_ids)][id_cols].copy()
    else:
        delete_preview = pd.DataFrame()

    diff = {
        "updates": updates,
        "deletes": delete_ids,
        "update_preview": update_preview,
        "delete_preview": delete_preview,
    }
    return diff, errors
