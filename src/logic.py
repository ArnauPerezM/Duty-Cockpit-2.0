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
    Result is cached in-process to avoid repeated HTTP calls on Streamlit re-renders.
    """
    global _FX_CACHE
    if _FX_CACHE is not None:
        return _FX_CACHE

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
            return _FX_CACHE
        except Exception as e:
            last_err = f"{name}: {e}"

    raise RuntimeError(f"All FX sources failed. Last error: {last_err}")


# -----------------------------
# Helpers de limpieza / normalización
# -----------------------------

def _to_lower_columns(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2.columns = [str(c).strip().lower() for c in df2.columns]
    return df2

def _clean_hs(x: Any) -> str:
    return re.sub(r"\D", "", str(x)).strip()

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
    # por si hay espacios u otras variaciones mínimas
    cols = list(df_lower.columns)
    if desired_lower in cols:
        return desired_lower
    # fallback: normalizar espacios múltiples
    norm = {re.sub(r"\s+", " ", c.strip().lower()): c for c in cols}
    key = re.sub(r"\s+", " ", desired_lower.strip().lower())
    return norm.get(key)

# -----------------------------
# Carga Excel (cacheada en app.py vía st.cache_data indirectamente)
# -----------------------------

def load_transactions_excel(uploaded_file, sheet_name: str = "Transactions") -> pd.DataFrame:
    # uploaded_file: st.uploaded_file (bytes-like)
    df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
    return df

# -----------------------------
# Estandarización Currencies + Validación + limpieza
# -----------------------------

def _convert_customs_value_to_eur(df: pd.DataFrame) -> pd.DataFrame:
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

    fx_map = _fetch_fx_rates_eur()
    rates = out["cv currency"].map(fx_map)
    missing = rates.isna()
    if missing.any():
        missing_ccy = sorted(out.loc[missing, "cv currency"].dropna().unique().tolist())
        raise ValueError(
            f"Missing FX rate(s) for currency codes: {missing_ccy}. "
            "These currencies are not available in the Frankfurter API."
        )

    out["customs value"] = (pd.to_numeric(out["customs value"], errors="coerce").fillna(0.0) * rates).round(2)
    out["cv currency"] = "EUR"
    return out

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

    analyzed_col = _find_column(df, "analyzed")
    if analyzed_col is not None:
        # main2: df[df['Analyzed'] == False]
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
    required = ["coo", "coi", "hs code", "customs value", "cv currency", "weight"]
    missing_required = [c for c in required if _find_column(df, c) is None]
    if missing_required:
        raise ValueError(
            f"Faltan columnas requeridas en la hoja: {missing_required}. "
            "Se esperaban al menos: coo, coi, hs code, customs value, cv currency, weight."
        )

    # Normalizar nombres esperados (en caso de variantes mínimas)
    colmap = {}
    for c in required:
        colmap[_find_column(df, c)] = c
    df = df.rename(columns=colmap)

    # Limpiezas base 
    df["weight"] = df["weight"].apply(_clean_weight)
    df["customs value"] = df["customs value"].apply(_clean_customs_value)
    df["hs code"] = df["hs code"].apply(_clean_hs)
    df["coo"] = df["coo"].apply(_clean_country)
    df["coi"] = df["coi"].apply(_clean_country)
    df["cv currency"] = df["cv currency"].astype(str).str.strip().str.upper()

    # Standardize all transactions to EUR (using local FX file)
    df = _convert_customs_value_to_eur(df)

    # df_missing: COO/COI/HS vacíos o customs value 0
    df_missing = df[
        (df["coo"].astype(str).str.strip() == "")
        | (df["coi"].astype(str).str.strip() == "")
        | (df["hs code"].astype(str).str.strip() == "")
        | (df["customs value"].isna())
        | (df["customs value"] == 0.0)
    ].copy()

    # df limpio para procesar
    df_ok = df[
        (df["coo"].astype(str).str.strip() != "")
        & (df["coi"].astype(str).str.strip() != "")
        & (df["hs code"].astype(str).str.strip() != "")
        & (df["customs value"] != 0.0)
    ].copy()

    # drop duplicates
    df_ok = df_ok.drop_duplicates()

    # Warnings ratios
    hs_ratio = 1.0
    iso_ratio = 1.0
    warnings = []

    if len(df_ok) > 0:
        hs_ratio = round((df_ok["hs code"].str.len() >= 6).mean(), 3)
        iso_ratio = round(((df_ok["coi"].str.len() == 2) & (df_ok["coo"].str.len() == 2)).mean(), 3)

        if hs_ratio < 0.95:
            warnings.append(
                f"Warning: solo {hs_ratio*100:.1f}% de HS Code tienen >=6 dígitos (umbral 95%)."
            )
        if iso_ratio < 0.95:
            warnings.append(
                f"Warning: solo {iso_ratio*100:.1f}% de COO/COI cumplen ISO-2 (umbral 95%)."
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

    return df_ok, df_missing, warnings_info

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
    Ejecuta sesión E2Open y pide getImportCost por fila.
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

        attempt = 0
        success = False
        last_err = None

        while attempt < max_retries and not success:
            attempt += 1
            try:
                coo2, coi2, hs2, cust_val2, cur2, qnty2, status, comment = session.getImportCost(
                    coo, coi, hs, cust_val, cur, qnty, ref_date
                )

                ok_rows.append(
                    {
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
                    coo=coo2,
                    coi=coi2,
                    hs=hs2,
                    status=status,
                    comment=comment,
                )
                success = True

                if progress_cb:
                    progress_cb(i, total, f"{i}/{total} | {hs} | {coo}→{coi} | {status} | {comment}")

            except Exception as e:
                last_err = str(e)
                log(
                    "row_retry",
                    row=i,
                    total=total,
                    coo=coo,
                    coi=coi,
                    hs=hs,
                    attempt=attempt,
                    error=last_err,
                )

        if not success:
            failed_rows.append(
                {
                    "coo": coo,
                    "coi": coi,
                    "hs code": hs,
                    "customs value": cust_val,
                    "cv currency": cur,
                    "weight": qnty,
                    "error": last_err or "Unknown error",
                }
            )
            log(
                "row_failed",
                row=i,
                total=total,
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
# Postproceso (df_min + df_merged) sin guardar archivos
# -----------------------------

def postprocess_results(
    ok_input_df: pd.DataFrame,
    ok_df: pd.DataFrame,
    failed_df: pd.DataFrame,
    df_missing: pd.DataFrame,
    ref_date: str,
    logs: List[Dict[str, Any]],
) -> pd.DataFrame:
    
    # Recuperar session.output desde logs
    session_output = None
    for item in reversed(logs):
        if item.get("event") == "session_output":
            session_output = item.get("payload")
            break

    if session_output is None:
        session_output = {}

    df_raw = pd.DataFrame.from_dict(session_output).T if session_output else pd.DataFrame()

    # Construir failed_df combinado(missing + api_failed)
    # Normalizar llaves de failed para poder filtrar
    def clean_country(x: Any) -> str:
        if pd.isna(x) or str(x).strip() == "":
            return ""
        return str(x).strip().upper()

    def clean_hs(x: Any) -> str:
        return re.sub(r"\D", "", str(x)).strip()

    combined_failed = pd.DataFrame(columns=["COO", "COI", "HS Code", "Customs Value"])

    if failed_df is not None and not failed_df.empty:
        api_failed_df = failed_df.copy()
        # Normalizar columnas
        for col in ["coo", "coi", "hs code", "customs value"]:
            if col not in api_failed_df.columns:
                api_failed_df[col] = ""
        api_failed_df = api_failed_df[["coo", "coi", "hs code", "customs value"]].rename(
            columns={"coo": "COO", "coi": "COI", "hs code": "HS Code", "customs value": "Customs Value"}
        )
        api_failed_df["COO"] = api_failed_df["COO"].apply(clean_country)
        api_failed_df["COI"] = api_failed_df["COI"].apply(clean_country)
        api_failed_df["HS Code"] = api_failed_df["HS Code"].apply(clean_hs)
        api_failed_df["Customs Value"] = pd.to_numeric(api_failed_df["Customs Value"], errors="coerce").round(2)
        combined_failed = pd.concat([combined_failed, api_failed_df], ignore_index=True)

    if df_missing is not None and not df_missing.empty:
        miss = df_missing.copy()
        # asegurar nombres
        if "coo" in miss.columns:
            miss = miss.rename(columns={"coo": "COO"})
        if "coi" in miss.columns:
            miss = miss.rename(columns={"coi": "COI"})
        if "hs code" in miss.columns:
            miss = miss.rename(columns={"hs code": "HS Code"})
        if "customs value" in miss.columns:
            miss = miss.rename(columns={"customs value": "Customs Value"})
        for col in ["COO", "COI", "HS Code", "Customs Value"]:
            if col not in miss.columns:
                miss[col] = ""
        miss = miss[["COO", "COI", "HS Code", "Customs Value"]].copy()

        miss["COO"] = miss["COO"].apply(clean_country)
        miss["COI"] = miss["COI"].apply(clean_country)
        miss["HS Code"] = miss["HS Code"].apply(clean_hs)
        miss["Customs Value"] = pd.to_numeric(miss["Customs Value"], errors="coerce").round(2)
        combined_failed = pd.concat([combined_failed, miss], ignore_index=True)

    combined_failed = combined_failed.dropna(how="all")

    # Excluir fallidas del df_in 
    df_in = ok_input_df.copy()
    if not combined_failed.empty:
        df_fail = df_in.merge(
            combined_failed[["COO", "COI", "HS Code"]],
            left_on=["coo", "coi", "hs code"],
            right_on=["COO", "COI", "HS Code"],
            how="left",
            indicator=True,
        )
        df_in = df_fail[df_fail["_merge"] == "left_only"].drop(columns=["_merge", "COO", "COI", "HS Code"])

        if not df_raw.empty:
            df_fail1 = df_raw.merge(
                combined_failed[["COO", "COI", "HS Code"]].rename(columns={"HS Code": "hs"}),
                left_on=["coo", "coi", "hs"],
                right_on=["COO", "COI", "hs"],
                how="left",
                indicator=True,
            )
            df_raw = df_fail1[df_fail1["_merge"] == "left_only"].drop(columns=["_merge", "COO", "COI"])

    # Preprocesado para df_min
    data_types = {
        "coo": "object",
        "coi": "object",
        "hs": "object",
        "custUnitP": "float64",
        "cur": "object",
        "qnty": "float64",
        "status": "object",
        "comment": "object",
        "hsNum": "object",
        "calcName": "object",
        "incoCalcBasis": "object",
        "Program": "object",
        "ratePct": "float64",
        "rateDesc": "object",
        "calcVal": "float64",
        "calcValCur": "object",
    }

    if df_raw.empty:
        # Si no hubo respuestas, devolver df_in vacío mergeado (sin columnas duty)
        return df_in.copy()

    df = df_raw.copy()
    # Quitar filas sin Program (error/no data)
    if "Program" in df.columns:
        df = df[~df["Program"].isna()].copy()

    # Asegurar columnas requeridas
    df = df[[c for c in data_types.keys() if c in df.columns]].copy()
    for c, t in data_types.items():
        if c in df.columns:
            try:
                df[c] = df[c].astype(t)
            except Exception:
                # si falla casteo, lo dejamos como está
                pass

    # Fill object nans
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = df[c].fillna("")

    df = df.rename(columns={"hsNum": "hs alternative", "hs": "hs code"})

    # Min duty por lane
    df_duty = df[df.get("calcName", "") == "DUTY"].copy()
    if df_duty.empty:
        # Sin DUTY, devolvemos df_in (sin enriquecer)
        return df_in.copy()

    group_cols = ["coo", "coi", "hs code", "custUnitP", "cur", "qnty"]
    df_min = df_duty.loc[df_duty.groupby(group_cols)["calcVal"].idxmin()].copy()

    df_min = df_min.rename(
        columns={
            "custUnitP": "customs value",
            "cur": "cv currency",
            "qnty": "weight",
            "Program": "Min Duty Program",
            "ratePct": "Min Duty Rate",
            "rateDesc": "Min Duty Program Description",
            "calcVal": "Minimum Duties",
            "calcValCur": "Currency Min Duties",
        }
    )

    # Default/MFN best
    df_default_mfn = df_duty[df_duty["Program"].astype(str).str.upper().isin(["DEFAULT", "MOST FAVOURED NATION (MFN)"])].copy()
    if not df_default_mfn.empty:
        df_default_mfn = df_default_mfn.rename(columns={"custUnitP": "customs value", "cur": "cv currency", "qnty": "weight"})
        merge_cols = ["coo", "coi", "hs code", "customs value", "cv currency", "weight"]
        df_def_min = df_default_mfn.loc[df_default_mfn.groupby(merge_cols)["calcVal"].idxmin()].copy()
        df_def_min = df_def_min.rename(
            columns={
                "ratePct": "Default Duty Rate",
                "rateDesc": "Default Duty Program Description",
                "calcVal": "Default Duties",
                "calcValCur": "Currency Default Duties",
            }
        )
        df_def_min["Default Duty Program"] = df_def_min["Program"]

        df_min = df_min.merge(
            df_def_min[merge_cols + [
                "Default Duty Program",
                "Default Duty Rate",
                "Default Duty Program Description",
                "Default Duties",
                "Currency Default Duties",
            ]],
            on=merge_cols,
            how="left",
        )

    # Merge final con input
    df_min["Input Date"] = ref_date

    df_merged = pd.merge(
        df_in,
        df_min,
        on=["coo", "coi", "hs code", "customs value", "cv currency", "weight"],
        how="left",
    )

    col_order = [
        "date",
        "invoice number",
        "material number",
        "coo",
        "coi",
        "hs code",
        "customs value",
        "cv currency",
        "weight",
        "duty paid",
        "dp currency",
        "status",
        "comment",
        "hs alternative",
        "calcName",
        "incoCalcBasis",
        "Min Duty Program",
        "Min Duty Rate",
        "Min Duty Program Description",
        "Minimum Duties",
        "Currency Min Duties",
        "Default Duty Program",
        "Default Duty Rate",
        "Default Duty Program Description",
        "Default Duties",
        "Currency Default Duties",
        "Input Date",
    ]
    df_merged = df_merged[[c for c in col_order if c in df_merged.columns]]

    # tipos numéricos
    if "customs value" in df_merged.columns:
        df_merged["customs value"] = pd.to_numeric(df_merged["customs value"], errors="coerce")
    if "weight" in df_merged.columns:
        df_merged["weight"] = pd.to_numeric(df_merged["weight"], errors="coerce")

    # Convert all remaining monetary columns to EUR via Frankfurter / ECB API
    # Uses Series.where() to avoid .loc chained-assignment issues in pandas 2.x
    try:
        fx_map = _fetch_fx_rates_eur()
        df_merged = df_merged.copy()  # ensure we own this DataFrame before writing
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
            missing_ccy = sorted(ccy[no_rate & ccy.notna() & (ccy != "NAN") & (ccy != "")].unique().tolist())
            if missing_ccy:
                logs.append({"event": "fx_missing_currency", "col": val_col, "currencies": missing_ccy})
            df_merged[val_col] = val.where(no_rate, (val * rate).round(2))
            df_merged[ccy_col] = ccy.where(no_rate, "EUR")
    except Exception as _fx_err:
        logs.append({
            "event": "fx_conversion_warning",
            "ts": __import__("datetime").datetime.utcnow().isoformat(),
            "error": str(_fx_err),
        })

    return df_merged


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
) -> bytes:
    """
    Build a self-contained HTML report summarising API run results.
    Returns UTF-8-encoded bytes ready for st.download_button.
    """
    import datetime
    import html as _html

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── KPIs ─────────────────────────────────────────────────────────────────
    df = df_merged.copy() if df_merged is not None and not df_merged.empty else pd.DataFrame()

    customs_val = pd.to_numeric(df.get("customs value", pd.Series(dtype=float)), errors="coerce").fillna(0)
    min_duties  = pd.to_numeric(df.get("Minimum Duties",  pd.Series(dtype=float)), errors="coerce").fillna(0)
    def_duties  = pd.to_numeric(df.get("Default Duties",  pd.Series(dtype=float)), errors="coerce").fillna(0)

    customs_sum = float(customs_val.sum())
    min_sum     = float(min_duties.sum())
    def_sum     = float(def_duties.sum())
    savings     = def_sum - min_sum
    eff_rate    = (min_sum / customs_sum * 100) if customs_sum > 0 else None

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
        if av >= 1_000_000:
            return f"{sign}€{av/1_000_000:.2f}M"
        if av >= 1_000:
            return f"{sign}€{av/1_000:.1f}k"
        return f"{sign}€{av:,.2f}"

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
    top_coi_savings = pd.DataFrame()
    top_coi_value   = pd.DataFrame()
    top_hs          = pd.DataFrame()

    if not df.empty:
        if {"coi", "Default Duties", "Minimum Duties"}.issubset(df.columns):
            tmp = df.copy()
            tmp["_sav"] = (
                pd.to_numeric(tmp["Default Duties"], errors="coerce").fillna(0)
                - pd.to_numeric(tmp["Minimum Duties"], errors="coerce").fillna(0)
            )
            top_coi_savings = (
                tmp.groupby("coi")["_sav"].sum()
                .sort_values(ascending=False).head(5)
                .reset_index()
                .rename(columns={"coi": "COI", "_sav": "Potential Savings (EUR)"})
            )

        if {"coi", "customs value"}.issubset(df.columns):
            tmp = df.copy()
            tmp["customs value"] = pd.to_numeric(tmp["customs value"], errors="coerce").fillna(0)
            top_coi_value = (
                tmp.groupby("coi")["customs value"].sum()
                .sort_values(ascending=False).head(5)
                .reset_index()
                .rename(columns={"coi": "COI", "customs value": "Customs Value (EUR)"})
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
    chart_labels:   List[str]   = []
    chart_customs:  List[float] = []
    chart_eff_rate: List[float] = []

    if not df.empty:
        _date_col = "date" if "date" in df.columns else None
        if _date_col and {"customs value", "Minimum Duties"}.issubset(df.columns):
            _tmp = df.copy()
            _tmp["_dt"] = pd.to_datetime(_tmp[_date_col], errors="coerce")
            _tmp = _tmp.dropna(subset=["_dt"])
            if not _tmp.empty:
                _tmp["_month"] = _tmp["_dt"].dt.to_period("M")
                _monthly = (
                    _tmp.groupby("_month")
                    .agg(
                        _cv=("customs value",  lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
                        _md=("Minimum Duties", lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()),
                    )
                    .reset_index()
                    .sort_values("_month")
                )
                _monthly["_er"] = _monthly.apply(
                    lambda r: round(r["_md"] / r["_cv"] * 100, 3) if r["_cv"] > 0 else 0.0,
                    axis=1,
                )
                chart_labels   = [str(p) for p in _monthly["_month"]]
                chart_customs  = _monthly["_cv"].round(2).tolist()
                chart_eff_rate = _monthly["_er"].tolist()

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
    df_disp = df[display_cols].head(500) if display_cols else df.head(500)
    truncated = len(df) > 500

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
        f"<span class='badge warn'>First 500 of {_int(len(df))} rows</span>"
        if truncated else ""
    )

    # ── Narrative paragraph ───────────────────────────────────────────────────
    fail_txt = (
        f", with <strong>{_int(failed_n)} failure(s)</strong>"
        f" and <strong>{_int(missing_n)} row(s) skipped</strong> due to missing fields"
        if (failed_n or missing_n) else ""
    )
    narrative = (
        f"This report summarises the results of an E2Open import duty analysis "
        f"for reference date <strong>{_e(ref_date)}</strong>. "
        f"A total of <strong>{_int(ok_n)} lane(s)</strong> are included in this report"
        f"{fail_txt}. "
        f"The total customs value analysed amounts to <strong>{_eur(customs_sum)}</strong>, "
        f"with a potential duty saving of <strong>{_eur(savings)}</strong> by applying "
        f"the most favourable program instead of the default MFN rate "
        f"(effective rate: <strong>{_pct(eff_rate)}</strong>)."
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

.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
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

@media print {
  body { background: white; }
  .section { margin: 10px 0; box-shadow: none; page-break-inside: avoid; }
  .report-header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""

    # ── Serialise chart data ──────────────────────────────────────────────────
    import json as _json
    _chart_json = _json.dumps({
        "labels":   chart_labels,
        "customs":  chart_customs,
        "effRate":  chart_eff_rate,
    })

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    account_meta = f"<span>&#128100; Account: <strong>{_e(account_label)}</strong></span>" if account_label else ""
    env_meta     = f"<span>&#127758; Environment: <strong>{_e(environment)}</strong></span>" if environment else ""

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>E2Open Duty Report &mdash; {_e(ref_date)}</title>
<style>{css}</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>

<div class="report-header">
  <h1>E2Open Duty Analysis Report</h1>
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
      <div class="kpi-label">Default Duties</div>
      <div class="kpi-value">{_eur(def_sum)}</div>
      <div class="kpi-sub">MFN / Default program</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Minimum Duties</div>
      <div class="kpi-value">{_eur(min_sum)}</div>
      <div class="kpi-sub">Best available program</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Potential Savings</div>
      <div class="kpi-value good">{_eur(savings)}</div>
      <div class="kpi-sub">Default &minus; Minimum duties</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Effective Duty Rate</div>
      <div class="kpi-value">{_pct(eff_rate)}</div>
      <div class="kpi-sub">Minimum &divide; Customs value</div>
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
      <h3>Top 5 COI by potential savings</h3>
      {_table(top_coi_savings, money_cols=["Potential Savings (EUR)"])}
    </div>
    <div>
      <h3>Top 5 COI by customs value</h3>
      {_table(top_coi_value, money_cols=["Customs Value (EUR)"])}
    </div>
    <div>
      <h3>Top 5 HS codes by customs value</h3>
      {_table(top_hs, money_cols=["Customs Value (EUR)"])}
    </div>
  </div>
  <div class="chart-wrap">
    <h3>Customs Value &amp; Effective Duty Rate by Month</h3>
    <canvas id="trendChart" height="90"></canvas>
  </div>
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
  Generated by E2Open Duty Cockpit 2.0 &mdash; {_e(generated_at)}
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

  // Inline plugin: draws white-box black-text labels on the Effective Duty Rate line
  const effRateLabelPlugin = {{
    id: 'effRateLabels',
    afterDatasetsDraw(chart) {{
      const meta = chart.getDatasetMeta(1);
      if (!meta || meta.hidden) return;
      const ctx = chart.ctx;
      const values = chart.data.datasets[1].data;
      ctx.save();
      ctx.font = 'bold 9px Segoe UI, Arial, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      meta.data.forEach(function(pt, i) {{
        const val = values[i];
        if (val == null) return;
        const text = val.toFixed(1) + '%';
        const tw = ctx.measureText(text).width;
        const px = 4, py = 3;
        const bw = tw + px * 2, bh = 14 + py * 2;
        const cx = pt.x, cy = pt.y - bh / 2 - 8;
        ctx.fillStyle = 'white';
        ctx.fillRect(cx - bw / 2, cy - bh / 2, bw, bh);
        ctx.strokeStyle = 'rgba(117,0,192,0.25)';
        ctx.lineWidth = 0.8;
        ctx.strokeRect(cx - bw / 2, cy - bh / 2, bw, bh);
        ctx.fillStyle = '#000';
        ctx.fillText(text, cx, cy);
      }});
      ctx.restore();
    }}
  }};
  Chart.register(effRateLabelPlugin);

  new Chart(document.getElementById('trendChart'), {{
    data: {{
      labels: d.labels,
      datasets: [
        {{
          type: 'bar',
          label: 'Customs Value (EUR)',
          data: d.customs,
          backgroundColor: 'rgba(70,0,115,0.82)',
          hoverBackgroundColor: '#7500C0',
          borderColor: 'rgba(70,0,115,0.95)',
          borderWidth: 1,
          borderRadius: 4,
          yAxisID: 'yLeft',
          order: 2,
        }},
        {{
          type: 'line',
          label: 'Effective Duty Rate (%)',
          data: d.effRate,
          borderColor: '#A100FF',
          backgroundColor: 'rgba(161,0,255,0.10)',
          pointBackgroundColor: '#A100FF',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          tension: 0.35,
          fill: false,
          yAxisID: 'yRight',
          order: 1,
        }}
      ]
    }},
    options: {{
      responsive: true,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{
          labels: {{ color: '#333', font: {{ size: 12 }} }}
        }},
        tooltip: {{
          callbacks: {{
            label: function(ctx) {{
              if (ctx.datasetIndex === 0) return ' ' + fmtEur(ctx.parsed.y);
              return ' ' + ctx.parsed.y.toFixed(2) + '%';
            }}
          }}
        }}
      }},
      scales: {{
        x: {{
          ticks: {{ color: '#555', font: {{ size: 11 }} }},
          grid:  {{ color: 'rgba(0,0,0,0.06)' }}
        }},
        yLeft: {{
          type: 'linear',
          position: 'left',
          ticks: {{
            color: '#333',
            font: {{ size: 11 }},
            callback: fmtEur
          }},
          grid: {{ color: 'rgba(0,0,0,0.07)' }}
        }},
        yRight: {{
          type: 'linear',
          position: 'right',
          min: 0,
          ticks: {{
            stepSize: 0.5,
            color: '#7500C0',
            font: {{ size: 11 }},
            callback: function(v) {{ return v.toFixed(1) + '%'; }}
          }},
          grid: {{ drawOnChartArea: false }}
        }}
      }}
    }}
  }});
}})();
</script>

</body>
</html>"""

    return html_doc.encode("utf-8")
