from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, List, Dict, Any

import pandas as pd
from pathlib import Path
from E2Open import E2OpenSession


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
def _load_fx_rates_eur() -> pd.DataFrame:
    """
    Load FX rates (From -> EUR) from:
      src/01_Quick Assessment Input.xlsx  (sheet: Currencies)

    Expected columns (case-insensitive):
      - From
      - To
      - Exchange Rate

    Returns a dataframe with:
      - from_ccy (ISO3)
      - rate_to_eur (float): 1 unit of from_ccy = rate_to_eur EUR
    """
    fx_path = Path(__file__).resolve().parent / "01_Quick Assessment Input.xlsx"
    if not fx_path.exists():
        raise FileNotFoundError(f"FX file not found: {fx_path}")

    fx = pd.read_excel(fx_path, sheet_name="Currencies")
    fx.columns = [str(c).strip().lower() for c in fx.columns]

    required = {"from", "to", "exchange rate"}
    missing = required - set(fx.columns)
    if missing:
        raise ValueError(f"FX sheet is missing required columns: {sorted(missing)}")

    fx = fx.rename(columns={"from": "from_ccy", "to": "to_ccy", "exchange rate": "rate_to_eur"})
    fx["from_ccy"] = fx["from_ccy"].astype(str).str.strip().str.upper()
    fx["to_ccy"] = fx["to_ccy"].astype(str).str.strip().str.upper()

    # Keep only rates to EUR
    fx = fx[fx["to_ccy"] == "EUR"].copy()

    # Handle comma decimals if read as strings (e.g. "0,8435")
    fx["rate_to_eur"] = (
        fx["rate_to_eur"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .str.replace(" ", "", regex=False)
    )
    fx["rate_to_eur"] = pd.to_numeric(fx["rate_to_eur"], errors="coerce")

    fx = fx.dropna(subset=["from_ccy", "rate_to_eur"])
    fx = fx.drop_duplicates(subset=["from_ccy"], keep="last")

    # Ensure EUR->EUR exists
    if "EUR" not in set(fx["from_ccy"].tolist()):
        fx = pd.concat([fx, pd.DataFrame([{"from_ccy": "EUR", "to_ccy": "EUR", "rate_to_eur": 1.0}])], ignore_index=True)

    return fx[["from_ccy", "rate_to_eur"]]


def _convert_customs_value_to_eur(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert df['customs value'] from df['cv currency'] to EUR using local FX file.
    Does NOT change business logic elsewhere; it only standardizes values/currency.

    Adds:
      - customs value original
      - cv currency original
    """
    out = df.copy()

    if "customs value" not in out.columns or "cv currency" not in out.columns:
        # If your data ever changes, fail early with a clear error.
        raise ValueError("Cannot convert to EUR: missing 'customs value' and/or 'cv currency' columns.")

    out["cv currency"] = out["cv currency"].astype(str).str.strip().str.upper()

    # Preserve originals for audit/debugging
    out["customs value original"] = out["customs value"]
    out["cv currency original"] = out["cv currency"]

    fx = _load_fx_rates_eur()

    out = out.merge(
        fx,
        left_on="cv currency",
        right_on="from_ccy",
        how="left",
    )

    missing_rate = out["rate_to_eur"].isna()
    if missing_rate.any():
        missing_ccy = sorted(out.loc[missing_rate, "cv currency"].dropna().unique().tolist())
        raise ValueError(
            "Missing FX rate(s) to EUR for currency codes: "
            f"{missing_ccy}. Please add them to the Currencies sheet."
        )

    out["customs value"] = pd.to_numeric(out["customs value"], errors="coerce").fillna(0.0) * out["rate_to_eur"]
    out["customs value"] = out["customs value"].round(2)

    out["cv currency"] = "EUR"

    out = out.drop(columns=["from_ccy", "rate_to_eur"], errors="ignore")
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

    session = E2OpenSession()
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

    return df_merged
