# Pending Features — Duty Cockpit 2.0

## Feature: DB Management + Inline Editing

### Objetivo
Permitir al usuario gestionar la base de datos SQLite (`data/duty_cockpit.db`) y editar
valores ya almacenados directamente desde la app, sin tener que volver a ejecutar el flujo
completo de API.

---

## Archivos a modificar

### 1. `src/db.py`

Añadir las siguientes funciones al final del archivo, **antes** del bloque
`# Type-coercion helpers`:

#### `get_db_stats() -> dict`
Devuelve estadísticas básicas de la DB.
```python
{
    "run_count":   int,   # total de runs almacenados
    "merged_rows": int,   # total de filas en merged_results
    "db_size_mb":  float, # tamaño del fichero .db en MB
    "oldest_run":  str,   # fecha ISO del run más antiguo (primeros 10 chars)
    "newest_run":  str,   # fecha ISO del run más reciente
}
```

#### `delete_run(run_id: int) -> None`
Borra un run y todas sus filas asociadas en cascada:
```sql
DELETE FROM merged_results  WHERE run_id = ?
DELETE FROM ok_results      WHERE run_id = ?
DELETE FROM failed_results  WHERE run_id = ?
DELETE FROM runs            WHERE id = ?
```

#### `delete_runs_before(before_date: str) -> int`
Borra todos los runs cuyo `started_at` sea anterior a `before_date` (string ISO, e.g. `"2025-01-01"`).
Devuelve el número de runs eliminados.
Misma lógica en cascada que `delete_run`, pero para múltiples IDs.

#### `purge_db() -> None`
Vacía todas las tablas (mantiene el schema):
```sql
DELETE FROM merged_results
DELETE FROM ok_results
DELETE FROM failed_results
DELETE FROM runs
DELETE FROM account_labels
```

#### `update_merged_rows(changes: list[dict]) -> int`
Actualiza campos editables en `merged_results`. Devuelve el número de filas actualizadas.

- Cada dict en `changes` debe contener `"id"` (int) más los campos a actualizar.
- **Campos permitidos** (DB column names, con underscore):
  `duty_paid`, `dp_currency`, `status`, `comment`, `hs_alternative`
- Ignorar cualquier otro campo que llegue en el dict.
- Implementación: `UPDATE merged_results SET campo=? WHERE id=?` por cada fila.

---

### 2. `src/ui.py` — función `render_tab_resultados`

**Reemplazar** la última línea de la función:
```python
# ANTES:
st.markdown("### Results table (filtered)")
st.dataframe(_make_arrow_safe(df), width="stretch")
```

**Por:**
```python
st.markdown("### Results table (filtered)")

# Columnas que el usuario puede editar
_EDITABLE = ["duty paid", "dp currency", "status", "comment", "hs alternative"]
_present_editable = [c for c in _EDITABLE if c in df.columns]

# Todas las demás columnas quedan en read-only (disabled)
# La columna "id" se oculta con column_config pero se mantiene en los datos
# (es necesaria para saber qué fila actualizar en la DB)
_disabled = [c for c in df.columns if c not in _present_editable and c != "id"]

col_cfg = {}
if "id" in df.columns:
    col_cfg["id"] = None  # ocultar columna id de la vista

edited = st.data_editor(
    df,
    column_config=col_cfg,
    disabled=_disabled,
    use_container_width=True,
    key="results_editor",
    hide_index=True,
)

save_col, msg_col = st.columns([2, 8])
with save_col:
    save_clicked = st.button("💾 Save changes", key="save_results_btn")

if save_clicked and _present_editable and "id" in df.columns:
    from src.db import update_merged_rows as _update_rows

    # Mapeado de nombre columna df → nombre columna DB
    _col_to_db = {
        "duty paid":     "duty_paid",
        "dp currency":   "dp_currency",
        "status":        "status",
        "comment":       "comment",
        "hs alternative":"hs_alternative",
    }

    changes = []
    for _, row in edited.iterrows():
        row_id = row.get("id")
        if row_id is None:
            continue
        # Buscar la fila original (df viene de la DB, es el baseline)
        orig_rows = df[df["id"] == row_id]
        if orig_rows.empty:
            continue
        orig_row = orig_rows.iloc[0]
        change = {"id": int(row_id)}
        for col in _present_editable:
            new_val = row[col]
            old_val = orig_row[col]
            try:
                is_changed = (new_val != old_val) and not (
                    pd.isna(new_val) and pd.isna(old_val)
                )
            except Exception:
                is_changed = str(new_val) != str(old_val)
            if is_changed:
                change[_col_to_db[col]] = None if pd.isna(new_val) else new_val
        if len(change) > 1:  # hay algo más que "id"
            changes.append(change)

    if changes:
        updated = _update_rows(changes)
        with msg_col:
            st.success(f"✓ {updated} row(s) saved to database.")
    else:
        with msg_col:
            st.info("No changes detected.")
```

> **Nota:** `df` es el parámetro `df_merged` ya filtrado que se usa en el resto de la función.
> `load_merged_results()` en `app.py` hace `SELECT *` que incluye la columna `id`,
> así que estará disponible en `df` sin cambios adicionales.

---

### 3. `src/ui.py` — función `render_tab_logs`

Añadir la siguiente sección **entre** el bloque `### Run history` y el bloque
`### Current session events` (antes del `if not logs: return`):

```python
# ── Database management ────────────────────────────────────────────────────
st.markdown("### Database management")
with st.expander("⚙️ Manage stored data", expanded=False):
    from src.db import get_db_stats, delete_run, delete_runs_before, purge_db

    stats = get_db_stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Runs stored",  stats["run_count"])
    m2.metric("Merged rows",  stats["merged_rows"])
    m3.metric("DB size",      f"{stats['db_size_mb']} MB")
    m4.metric("First run",    stats["oldest_run"] or "—")

    st.markdown("---")

    # ── Borrar un run específico ───────────────────────────────────────────
    st.markdown("**Delete a specific run**")
    if run_history is not None and not run_history.empty:
        run_opts = {
            f"Run {int(r['id'])} — {str(r.get('started_at',''))[:10]}"
            f" — {int(r.get('total_ok', 0) or 0)} ok rows": int(r["id"])
            for _, r in run_history.iterrows()
        }
        sel_run  = st.selectbox("Select run", options=list(run_opts.keys()), key="mgmt_del_run_sel")
        conf_run = st.checkbox("Confirm deletion of this run", key="mgmt_del_run_confirm")
        if st.button("🗑 Delete run", disabled=not conf_run, key="mgmt_del_run_btn"):
            delete_run(run_opts[sel_run])
            st.success("Run deleted.")
            st.rerun()
    else:
        st.info("No runs in the database.")

    st.markdown("---")

    # ── Borrar runs anteriores a fecha ────────────────────────────────────
    st.markdown("**Delete runs before a date**")
    del_before  = st.date_input("Delete all runs before", key="mgmt_del_before_date")
    conf_before = st.checkbox("Confirm deletion of old runs", key="mgmt_del_before_confirm")
    if st.button("🗑 Delete old runs", disabled=not conf_before, key="mgmt_del_before_btn"):
        n = delete_runs_before(str(del_before))
        st.success(f"{n} run(s) deleted.")
        st.rerun()

    st.markdown("---")

    # ── Purgar todo ───────────────────────────────────────────────────────
    st.markdown("**⚠️ Purge all data**")
    conf_purge = st.checkbox(
        "I understand this will permanently delete ALL stored data",
        key="mgmt_purge_confirm",
    )
    if st.button("💣 Purge database", disabled=not conf_purge,
                 type="primary", key="mgmt_purge_btn"):
        purge_db()
        st.success("Database purged.")
        st.rerun()
```

---

### 4. `app.py` — sin cambios

Todas las operaciones de DB se gestionan con imports locales dentro de las funciones
de `ui.py`. No es necesario modificar `app.py`.

---

## Contexto técnico relevante

- **DB:** SQLite en `data/duty_cockpit.db`. Schema definido en `src/db.py` (`_DDL`).
- **Columna `id`:** `merged_results` tiene `id INTEGER PRIMARY KEY AUTOINCREMENT`.
  `load_merged_results()` hace `SELECT *` por lo que `id` ya está en el DataFrame
  devuelto. El mapeo `_MERGED_DB_TO_DF` no renombra `id`, queda como `"id"`.
- **Conversión a EUR:** `duty paid` ya se convierte a EUR en `postprocess_results()`
  (via `_fetch_fx_rates_eur()`) antes de guardarse. Los valores en DB ya están en EUR.
- **`st.data_editor`:** Requiere Streamlit ≥ 1.19. El proyecto usa 1.52.2. Compatible.
- **Columnas editables en la UI:** `duty paid`, `dp currency`, `status`, `comment`,
  `hs alternative`. El resto son resultados de API o datos de entrada que no deben
  modificarse sin re-ejecutar.
