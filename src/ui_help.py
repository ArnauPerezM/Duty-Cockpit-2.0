from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Knowledge base: (keywords, section_key) pairs pointing to answer blocks.
# Answers are defined separately so they can be long and readable.
# First match wins — order from specific to general.
# ---------------------------------------------------------------------------

_ANSWERS: dict[str, str] = {

    # ── Getting started ─────────────────────────────────────────────────────
    "start": (
        "**Getting Started — First Run**\n\n"
        "1. **Prepare the Excel file** — sheet named *Transactions* with columns: "
        "Invoice Number, Material Number, COO, COI, HS Code, Customs Value, Duty Paid.\n"
        "2. **Connect to e2open** — click *Connect to e2open* in the Process tab and enter "
        "your User ID, Password, Tenant ID, Environment (UAT/PRO), and an Account Name.\n"
        "3. **Upload the file** — drag or browse to your Excel file in the Process tab.\n"
        "4. **Set the Reference Date** — the date used to query e2open duty rates.\n"
        "5. **Click ▶ Run** — the app queries e2open row by row, saves results to the "
        "local database, and navigates to the Results tab automatically."
    ),

    # ── Excel input format ──────────────────────────────────────────────────
    "excel": (
        "**Excel Input Format**\n\n"
        "The file must contain a sheet named *Transactions* (configurable). "
        "Required columns:\n\n"
        "| Column | Description |\n"
        "|---|---|\n"
        "| Invoice Number | Unique invoice ID |\n"
        "| Material Number | Product or part identifier |\n"
        "| COO | Country of Origin — 2-letter ISO (e.g. `CN`, `DE`) |\n"
        "| COI | Country of Import — 2-letter ISO (e.g. `ES`, `US`) |\n"
        "| HS Code | Harmonized System code — 6+ digits recommended |\n"
        "| Customs Value | Declared value of goods |\n"
        "| Duty Paid | Duties already paid (can be 0) |\n\n"
        "Optional: `Weight`, `CV Currency`, `DP Currency`, `Status`, `Comment`.\n\n"
        "If an `Analyzed` column exists, rows where `Analyzed = True` are automatically skipped."
    ),

    # ── e2open credentials ───────────────────────────────────────────────────
    "credentials": (
        "**e2open Credentials**\n\n"
        "Fill in the *Connect to e2open* form in the Process tab:\n\n"
        "- **Environment** — `UAT` for testing, `PRO` for production\n"
        "- **User ID** — your e2open user UUID (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)\n"
        "- **Password** — your e2open password\n"
        "- **Tenant ID** — your organization's tenant UUID\n"
        "- **Account Name** — a short label shown in the header; saved for future sessions\n\n"
        "Credentials are stored only in the active session and **never written to disk**."
    ),

    # ── Environment UAT / PRO ────────────────────────────────────────────────
    "environment": (
        "**UAT vs. PRO Environment**\n\n"
        "- **UAT** (User Acceptance Testing) — safe sandbox for testing. "
        "Use this when validating a new file format or testing the workflow.\n"
        "- **PRO** (Production) — live environment with real tariff data. "
        "Use for official duty analysis on production transactions.\n\n"
        "Switch environment in the *Connect to e2open* form. "
        "The active environment is shown as a chip below the account name in the header."
    ),

    # ── Reference date ───────────────────────────────────────────────────────
    "refdate": (
        "**Reference Date**\n\n"
        "The date sent to e2open when querying duty rates. "
        "Tariff schedules change over time — different dates may return different rates.\n\n"
        "Always set the reference date to **the period you are analyzing** "
        "(e.g. the invoice date or the end of the period under review). "
        "The default is today's date."
    ),

    # ── Process tab ─────────────────────────────────────────────────────────
    "process": (
        "**Process Tab**\n\n"
        "The Process tab is the starting point for every analysis:\n\n"
        "1. Upload your Excel file → the app shows **Candidate rows** (valid) and "
        "**Missing rows** (incomplete data, skipped)\n"
        "2. Data quality KPIs warn if fewer than 95% of rows have valid HS codes "
        "or ISO-2 country codes\n"
        "3. Connect to e2open and click **▶ Run**\n"
        "4. A progress bar and live status log track each row\n"
        "5. After completion: 4 KPI cards show OK / Failed / Missing / Total counts\n\n"
        "**Map view** (post-run): a choropleth map with 4 selectable metrics — "
        "Customs Value, Duties Paid, Potential Savings, % Failed/Missing — "
        "plus a Top 10 Countries table."
    ),

    # ── Duplicate detection ──────────────────────────────────────────────────
    "duplicate": (
        "**Duplicate Transaction Detection**\n\n"
        "Before running, the app checks if any rows were already sent to e2open "
        "with the same reference date. If duplicates are found, you choose:\n\n"
        "- **Skip duplicates** — sends only the new rows (recommended)\n"
        "- **Reprocess all** — re-sends all rows including duplicates\n"
        "- **Cancel** — aborts without sending anything\n\n"
        "Matching is based on (Invoice Number + Material Number) or "
        "(COO + COI + HS Code + Customs Value + Weight)."
    ),

    # ── Cancel run ──────────────────────────────────────────────────────────
    "cancel": (
        "**Cancelling a Run**\n\n"
        "Click **✕ Cancel** at any time during an active run. "
        "The current row finishes processing, then the run stops. "
        "Results up to the cancellation point are saved to the database and visible in the Results tab."
    ),

    # ── Missing rows ─────────────────────────────────────────────────────────
    "missing": (
        "**Missing Rows**\n\n"
        "Rows are classified as *missing* (and excluded from the API run) if they have:\n"
        "- Blank COO, COI, or HS Code\n"
        "- Zero or blank Customs Value\n\n"
        "Missing rows are shown in a collapsible expander before the run. "
        "They are counted in the post-run summary but not sent to e2open. "
        "Fix the source data and re-run to include them."
    ),

    # ── Results tab ─────────────────────────────────────────────────────────
    "results": (
        "**Results Tab**\n\n"
        "Shows all transactions returned from e2open, merged with the original input. "
        "KPI cards: Transactions, Countries of Import, Countries of Origin, "
        "Customs Value, Duty Exposure, Duty Paid.\n\n"
        "**Charts:**\n"
        "- *Customs Value by COI* — pie of top 8 countries of import\n"
        "- *Duty Exposure gauge* — Duties Paid vs. Exposure scope, with a line at the Minimum Duties threshold\n"
        "- *Duties Paid by COI* — pie of top 8 countries of import\n\n"
        "Key columns in the results table:\n"
        "- **Min Duty Program** — best applicable duty program\n"
        "- **Min Duty Rate** — optimal rate (%)\n"
        "- **Minimum Duties** — what should be paid (EUR)\n"
        "- **Default Duty Rate** — standard MFN rate (%)\n\n"
        "Use sidebar filters (COO, COI, HS Code, Material, date range) to narrow results. "
        "Click **Reset Filter** to clear."
    ),

    # ── Editing results ──────────────────────────────────────────────────────
    "edit": (
        "**Editing Results**\n\n"
        "Two editing modes are available:\n\n"
        "**Inline mode** — click *Edit (inline)*:\n"
        "- Editable fields: COO, COI, HS Code, Customs Value, Weight, Duty Paid, Comment\n"
        "- Check `_delete` to mark rows for deletion\n"
        "- Click *Review changes* → review the diff → *Apply changes*\n\n"
        "**Excel mode** — click *Edit via Excel*:\n"
        "1. Download the editable Excel file (`_db_id` + `_delete` control columns)\n"
        "2. Edit offline\n"
        "3. Re-upload the file\n"
        "4. Review the diff preview\n"
        "5. Apply changes\n\n"
        "**Do not modify the `_db_id` column** — it links each row to the database record."
    ),

    # ── Opportunities tab ────────────────────────────────────────────────────
    "opportunities": (
        "**Opportunities Tab**\n\n"
        "Identifies trade lanes where **Duty Paid > Minimum Duties**, indicating overpayments.\n\n"
        "Rows are grouped by **COO · COI · HS Code · Material Number**. Key columns:\n"
        "- **Overpaid Duties** — Duty Paid minus Minimum Duties\n"
        "- **Applied Rate** — effective rate currently paid (%)\n"
        "- **Min Duty Rate** — optimal rate available (%)\n"
        "- **FTA Applied Previously / Afterwards** — whether FTA was used before/after the overpayment period\n\n"
        "Four bar charts show overpayments by Product, by COI, by Trade Lane, and by Duty Program.\n\n"
        "**Actions:**\n"
        "- Select rows → **Create Initiative** to track the opportunity\n"
        "- Select rows → individual transactions for that trade lane expand inline below the table\n\n"
        "Rows with existing initiatives are hidden by default. "
        "Enable *Show rows with existing initiatives* to display them."
    ),

    # ── Create initiative ────────────────────────────────────────────────────
    "create_initiative": (
        "**Creating an Initiative from Opportunities**\n\n"
        "1. In the **Opportunities** tab, select one or more rows using the checkboxes\n"
        "2. Click **Create Initiative**\n"
        "3. The selected trade lanes are saved as new initiatives with:\n"
        "   - PRE metrics computed from transaction data\n"
        "   - Status set to *Identified*\n"
        "   - Estimated annual savings pre-calculated\n"
        "4. Switch to the **Initiatives** tab to track and update them\n\n"
        "If some selected rows already have initiatives, the app warns before proceeding."
    ),

    # ── Initiatives tab ──────────────────────────────────────────────────────
    "initiatives": (
        "**Initiatives Tab**\n\n"
        "Tracks duty optimization initiatives from identification to completion.\n\n"
        "**Status lifecycle:** Identified → Validated → Completed (or Discarded)\n\n"
        "**Charts:**\n"
        "- *Initiative Portfolio by Status* — donut with count in centre\n"
        "- *Top 10 Open Initiatives by Country of Import* — bar chart of COIs with most open initiatives\n\n"
        "**Initiatives table** shows: COO, COI, HS Code, Material Number, Min Duty Program, "
        "Status, Comments, Duties Overpaid, Potential Reimbursements, Reimbursements Realized, "
        "Total Savings Realized.\n\n"
        "**PRE vs. POST comparison table** (in the detail panel):\n"
        "Side-by-side view with PRE (planned) on the left and POST (realized) on the right. "
        "Rows align comparable metrics: Customs Value, Duty Paid, Rate, Annual Savings, "
        "Overpaid, Reimbursements, Total Savings (highlighted). "
        "POST is populated from transactions in the 365 days after Implementation Date.\n\n"
        "**Dates:**\n"
        "- Start Date — when identified (editable)\n"
        "- Implementation Date — when optimization was applied (editable)\n"
        "- End Date — auto-calculated as Implementation Date + 365 days, but can be overridden manually "
        "(shows *(auto)* label when not set)\n\n"
        "Select a row to expand the detail panel and edit status, dates, reimbursements, and comments."
    ),

    # ── Initiative status ────────────────────────────────────────────────────
    "initiative_status": (
        "**Initiative Status Values**\n\n"
        "| Status | Meaning |\n"
        "|---|---|\n"
        "| **Identified** | Opportunity found, not yet validated |\n"
        "| **Validated** | Confirmed by the team, ready to act |\n"
        "| **Completed** | FTA or optimization implemented |\n"
        "| **Discarded** | Not actionable, removed from active tracking |\n\n"
        "Change status by selecting the initiative and editing the status dropdown in the detail panel, "
        "then clicking **Save changes**."
    ),

    # ── Grouping initiatives ─────────────────────────────────────────────────
    "group": (
        "**Grouping Initiatives**\n\n"
        "Select 2 or more initiatives and click **Group Initiatives** to merge them.\n\n"
        "- A **parent row** shows aggregated metrics (sums of all members)\n"
        "- **Child rows** are collapsed inside a group expander\n"
        "- Assign a custom group name using the text field in the group expander\n\n"
        "To ungroup: open the group expander, select child rows, click **Ungroup Selected**.\n\n"
        "Grouping is useful when multiple trade lanes belong to the same supply chain improvement project."
    ),

    # ── PRE / POST metrics ───────────────────────────────────────────────────
    "pre_post": (
        "**PRE vs. POST Metrics**\n\n"
        "Shown as a side-by-side comparison table inside each initiative's detail panel.\n\n"
        "**PRE (planned):** Calculated from transaction data at the time the initiative was created. "
        "Shows the baseline (as-is) situation and the potential if the optimal duty program is applied. "
        "Includes: Customs Value, Duty Paid, As-is Rate, Duty To-Be Paid, To-Be Rate, "
        "Est. Annual CV, Est. Annual Savings, Initial Overpaid, Potential Reimbursements, "
        "Total Potential Savings.\n\n"
        "**POST (realized):** Automatically computed from transactions recorded in the "
        "365 days **after the Implementation Date**. Shows actual achieved savings vs. the baseline. "
        "Includes: Customs Value (POST), Duty Paid (POST), Realized Avg. Rate, "
        "Duty Savings Realized, Final Overpaid, Reimbursements Realized, Total Savings Realized.\n\n"
        "**Total Savings Realized** is highlighted in the table for quick reference.\n\n"
        "For POST to populate, the initiative must have a **Completed** status and a set "
        "**Implementation Date**. Transactions are matched by COO + COI + HS Code."
    ),

    # ── Logs tab ─────────────────────────────────────────────────────────────
    "logs": (
        "**Logs Tab**\n\n"
        "Two sections:\n\n"
        "**Run History** — one row per analysis run with:\n"
        "ref_date, started_at, total_candidates, total_ok, total_failed, "
        "total_missing, cancelled, account_label, environment\n\n"
        "Filter by date range (From/To) to narrow history. "
        "KPI cards show: Total Lanes Processed, Total Runs, Success Rate.\n\n"
        "**Execution Log** — row-by-row API results from the current session's last run "
        "(last 200 events). Raw API response payloads are excluded for readability."
    ),

    # ── Reporting tab ────────────────────────────────────────────────────────
    "reporting": (
        "**Reporting Tab**\n\n"
        "Executive dashboard with charts and a downloadable HTML report.\n\n"
        "**KPI cards:** Total Customs Value, Total Duty Paid, Overpaid Duties, "
        "Savings Realized, Savings Capture Rate (Realized ÷ Overpaid).\n\n"
        "**Dashboard charts:**\n"
        "- *World Map* — selectable metric: Customs Value / Duty Paid / Overpaid Duties by COI\n"
        "- *Top 10 Import Countries — Duties Paid* — left bar chart\n"
        "- *Top 10 Import Countries — Overpaid Duties* — right bar chart\n"
        "- *Heat Map* — COO × COI matrix with selectable metric and per-cell value labels\n"
        "- *Monthly Trend* — Duty Paid vs. Minimum Duties area chart; the gap between them = Overpaid Duties (highlighted)\n"
        "- *Est. Annual Savings vs Savings Realized by COI* — grouped bar comparing PRE expected vs. POST realized\n"
        "- *Initiative Portfolio by Status* — donut with initiative count in centre\n"
        "- *Top Trade Lanes* — table with transactions, duties, and effective rate\n\n"
        "All charts reflect the **sidebar filters** currently applied.\n\n"
        "**Download Report** generates a self-contained HTML file with:\n"
        "- Executive narrative with Savings Capture Rate\n"
        "- 9 KPI cards (Customs Value, Duty Paid, Minimum Duties, Overpaid Duties, "
        "Savings Realized, Savings Capture Rate, Failed, Missing/Skipped, Lanes)\n"
        "- Key findings: Top 5 COI by Overpaid / Duty Paid, Top 5 HS by Customs Value\n"
        "- Monthly trend chart (Duty Paid vs Minimum Duties with Overpaid area)\n"
        "- Initiative portfolio with Savings Capture Rate\n"
        "- Detailed results table (first 500 rows)\n\n"
        "The HTML file can be opened in any browser or emailed without dependencies."
    ),

    # ── Sidebar filters ──────────────────────────────────────────────────────
    "filters": (
        "**Sidebar Filters**\n\n"
        "Sidebar filters apply simultaneously to **Results**, **Opportunities**, "
        "**Initiatives**, and **Reporting**:\n\n"
        "| Filter | Description |\n"
        "|---|---|\n"
        "| Time (From/To) | Date range of transactions |\n"
        "| Origin Country (COO) | Filter by country of origin |\n"
        "| Import Country (COI) | Filter by country of import |\n"
        "| HS Code | Filter by tariff code |\n"
        "| Material Number | Filter by product |\n\n"
        "Click **Reset Filter** at the bottom of the sidebar to clear all filters."
    ),

    # ── Backup & restore ─────────────────────────────────────────────────────
    "backup": (
        "**Backup & Restore**\n\n"
        "Found at the bottom of the sidebar:\n\n"
        "- **Download backup** — exports the full local SQLite database as a `.db` file. "
        "Includes all analysis results, initiatives, run history, and FX rate cache.\n"
        "- **Restore** — upload a previously downloaded `.db` file to replace the current database.\n\n"
        "**A backup of the current database is saved automatically before any restore** "
        "so you can recover if the restore file is incorrect.\n\n"
        "Only `.db` files created by Duty Optimizer are accepted."
    ),

    # ── Logout ───────────────────────────────────────────────────────────────
    "logout": (
        "**Logout**\n\n"
        "Click **Logout** at the bottom of the sidebar to disconnect from e2open. "
        "Your analysis data in the database is fully preserved — "
        "only the active session credentials (User ID, Password, Tenant ID) are cleared. "
        "The account name chip disappears from the header until you reconnect."
    ),

    # ── COO ──────────────────────────────────────────────────────────────────
    "coo": (
        "**COO — Country of Origin**\n\n"
        "The 2-letter ISO code of the country where goods were **manufactured or "
        "substantially transformed** (e.g. `CN` = China, `DE` = Germany, `US` = United States).\n\n"
        "COO determines which preferential trade agreements (FTAs) and duty programs may apply "
        "for a given import destination. Must be a valid ISO-2 code — "
        "accepted aliases: `UK` → `GB` (United Kingdom), `EL` → `GR` (Greece)."
    ),

    # ── COI ──────────────────────────────────────────────────────────────────
    "coi": (
        "**COI — Country of Import**\n\n"
        "The 2-letter ISO code of the **destination country** where goods are being imported "
        "(e.g. `ES` = Spain, `FR` = France, `GB` = United Kingdom).\n\n"
        "Combined with COO and HS Code, COI determines the applicable duty rate in e2open's "
        "tariff database. Must be a valid ISO-2 code."
    ),

    # ── HS Code ──────────────────────────────────────────────────────────────
    "hscode": (
        "**HS Code — Harmonized System**\n\n"
        "A standardized international code used to classify traded goods (e.g. `8471.30` for laptops). "
        "The code determines which tariff schedule and duty rate applies for a given COO→COI pair.\n\n"
        "- Minimum **6 digits** recommended for accurate e2open lookups\n"
        "- Shorter codes may return inaccurate or no rates\n"
        "- The app warns if fewer than 95% of rows have 6+ digit HS codes\n"
        "- Only digits are kept (dots and spaces are stripped automatically)"
    ),

    # ── Overpaid duties ───────────────────────────────────────────────────────
    "overpaid": (
        "**Overpaid Duties**\n\n"
        "`Overpaid Duties = Duty Paid − Minimum Duties`\n\n"
        "A positive value means the company paid more than the lowest applicable rate. "
        "This can happen when:\n"
        "- A preferential FTA program was not claimed\n"
        "- The HS code classification resulted in a higher rate than necessary\n"
        "- The COO was not optimized for available trade agreements\n\n"
        "Overpaid duties are visible in the **Opportunities** and **Reporting** tabs. "
        "Past overpayments may be recoverable through duty drawback claims."
    ),

    # ── Min / Default duty programs ───────────────────────────────────────────
    "programs": (
        "**Duty Programs**\n\n"
        "**Min Duty Program** — the program identified by e2open with the **lowest applicable rate** "
        "for a given trade lane. This is what your company should be using.\n\n"
        "**Default Duty Program (MFN)** — the Most Favored Nation rate, the standard tariff "
        "applied when no preferential trade agreement is in force. "
        "This is the baseline rate before any FTA or special program.\n\n"
        "When Min Duty Rate < Default Duty Rate, a preferential program (usually an FTA) "
        "is available but may not have been applied."
    ),

    # ── FTA ───────────────────────────────────────────────────────────────────
    "fta": (
        "**FTA — Free Trade Agreement**\n\n"
        "A preferential trade agreement between countries that reduces or eliminates duty rates. "
        "The **Opportunities** tab flags trade lanes where an FTA exists but was not applied:\n\n"
        "- **FTA Applied Previously** — FTA was used before the overpayment period\n"
        "- **FTA Applied Afterwards** — FTA was used after the overpayment period\n\n"
        "If FTA was applied inconsistently, there is evidence the program is available "
        "and the overpayment is recoverable. "
        "First/Last FTA Rate Paid columns show when the program was last used correctly."
    ),

    # ── Trade lane ────────────────────────────────────────────────────────────
    "lane": (
        "**Trade Lane**\n\n"
        "A trade lane is a unique combination of **COO + COI + HS Code** "
        "(optionally + Material Number). "
        "It is the core unit of analysis in the Opportunities and Initiatives tabs.\n\n"
        "Each trade lane has one minimum duty rate from e2open. "
        "Multiple invoices on the same lane are aggregated to measure total overpayment."
    ),

    # ── FX / currencies ───────────────────────────────────────────────────────
    "currency": (
        "**Currency & FX Conversion**\n\n"
        "All monetary values are converted to **EUR** for analysis. "
        "Exchange rates are fetched from:\n"
        "1. open.er-api.com (primary)\n"
        "2. Frankfurter API (fallback)\n"
        "3. ECB (secondary fallback)\n\n"
        "Rates are cached for **4 hours**. "
        "Original currency values are preserved in the database "
        "(`customs_value_original`, `cv_currency_original`) "
        "so source data integrity is maintained."
    ),

    # ── Data quality ──────────────────────────────────────────────────────────
    "quality": (
        "**Data Quality**\n\n"
        "The app validates input data before running:\n\n"
        "- **COO/COI** — must be 2-letter ISO codes. Aliases: `UK`→`GB`, `EL`→`GR`\n"
        "- **HS Code** — digits only; 6+ digits recommended\n"
        "- **Customs Value** — must be a positive number\n"
        "- **Missing rows** — blank COO, COI, HS Code, or zero Customs Value → excluded\n\n"
        "A warning appears if fewer than 95% of rows pass HS or ISO format checks. "
        "Fix the source data and re-run to include problematic rows."
    ),

    # ── Tabs navigation ───────────────────────────────────────────────────────
    "tabs": (
        "**App Navigation**\n\n"
        "Use the section bar below the header to switch between tabs:\n\n"
        "| Tab | Purpose |\n"
        "|---|---|\n"
        "| **Process** | Upload Excel & run new analyses |\n"
        "| **Results** | View and edit transaction-level output |\n"
        "| **Opportunities** | Detected duty overpayments |\n"
        "| **Initiatives** | Track duty reduction projects (PRE/POST) |\n"
        "| **Logs** | Execution history and run details |\n"
        "| **Reporting** | Executive dashboard and HTML report export |"
    ),

    # ── Troubleshooting ───────────────────────────────────────────────────────
    "troubleshoot": (
        "**Troubleshooting**\n\n"
        "**Authentication failed** — Check User ID, Password, and Tenant ID for the selected "
        "environment. UUID format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.\n\n"
        "**No candidate rows** — All rows have `Analyzed = True` or missing required fields. "
        "Check sheet name and that COO, COI, HS Code, Customs Value are populated.\n\n"
        "**High Failed count** — e2open returned errors. Check the Logs tab for details. "
        "Common causes: invalid country code, HS code not in e2open's tariff database.\n\n"
        "**Charts show no data** — Sidebar filters may exclude everything. "
        "Click **Reset Filter**.\n\n"
        "**Restore fails** — Only `.db` files created by Duty Optimizer are accepted.\n\n"
        "**Map shows no countries** — COO/COI codes must be valid ISO-2 format."
    ),

    # ── Applied Rate ──────────────────────────────────────────────────────────
    "applied_rate": (
        "**Applied Rate**\n\n"
        "A calculated column in the Results tab:\n\n"
        "`Applied Rate = Duty Paid ÷ Customs Value × 100`\n\n"
        "This is the **effective duty rate** your company actually paid on each transaction. "
        "Compare this to **Min Duty Rate** — a large gap indicates overpayment. "
        "Compare to **Default Duty Rate** to see if you are above or below the MFN baseline."
    ),

    # ── Savings Capture Rate ──────────────────────────────────────────────────
    "capture_rate": (
        "**Savings Capture Rate**\n\n"
        "`Savings Capture Rate = Savings Realized ÷ Overpaid Duties × 100`\n\n"
        "Measures what percentage of the identified savings opportunity has been captured "
        "through initiatives. Visible in the **Reporting** KPI cards and the HTML report.\n\n"
        "- **High rate** — the programme is executing well; most opportunities are being realized\n"
        "- **Low rate** — large untapped potential; prioritise converting Identified/Validated "
        "initiatives into Completed ones\n\n"
        "Overpaid Duties is the denominator (the total identified opportunity across all transactions). "
        "Savings Realized comes from FTA savings + reimbursements across all initiatives."
    ),
}


# ---------------------------------------------------------------------------
# Keyword routing table: keyword → answer key
# ---------------------------------------------------------------------------
_ROUTES: list[tuple[list[str], str]] = [
    (["start", "begin", "first run", "first time", "how to use", "get started", "how do i", "how to run"], "start"),
    (["excel", "file format", "upload", "sheet", "transactions", "input file", "columns", "required column", "spreadsheet"], "excel"),
    (["credential", "login", "connect", "authenticate", "user id", "password", "tenant", "uuid", "sign in", "log in"], "credentials"),
    (["uat", "pro environment", "production", "environment", "sandbox", "testing env"], "environment"),
    (["ref date", "reference date", "which date", "date to use", "analysis date"], "refdate"),
    (["process tab", "process section", "run analysis", "running", "analyze", "execute", "map view"], "process"),
    (["duplicate", "already sent", "reprocess", "sent before", "duplicate check"], "duplicate"),
    (["cancel", "stop", "abort", "interrupt", "pause run"], "cancel"),
    (["missing row", "missing data", "blank field", "skipped row", "excluded row"], "missing"),
    (["result", "results tab", "output table", "merged result", "transaction table", "duty exposure"], "results"),
    (["edit", "inline edit", "excel edit", "modify", "update row", "correct", "db edit", "delete row", "_delete", "correction"], "edit"),
    (["opportunit", "overpayment", "saving", "optimiz", "by product", "by trade lane", "by program", "by coi chart"], "opportunities"),
    (["create initiative", "promote", "new initiative", "add initiative"], "create_initiative"),
    (["initiativ", "pre metric", "post metric", "savings realized", "reimburs", "annual savings", "potential savings", "portfolio", "initiative tab"], "initiatives"),
    (["status", "identified", "validated", "completed", "discarded", "initiative status", "lifecycle"], "initiative_status"),
    (["group", "ungroup", "merge initiative", "group initiative"], "group"),
    (["pre vs post", "pre post", "implementation date", "365 day", "post window", "realized vs planned"], "pre_post"),
    (["log", "run history", "execution log", "history", "past run", "query count", "success rate", "logs tab"], "logs"),
    (["report", "reporting", "dashboard", "export report", "download report", "html report", "chart report"], "reporting"),
    (["filter", "sidebar", "reset filter", "global filter", "filter panel"], "filters"),
    (["backup", "restore", "database backup", "db backup", ".db file", "save database", "export database"], "backup"),
    (["logout", "disconnect", "sign out", "session", "clear session"], "logout"),
    (["coo", "country of origin", "origin country", "manufacturing country"], "coo"),
    (["coi", "country of import", "import country", "destination country", "receiving country"], "coi"),
    (["hs code", "hs", "harmonized", "tariff code", "hs number", "tariff class"], "hscode"),
    (["overpaid", "overpayment", "duty overpaid", "paid too much", "excess duty"], "overpaid"),
    (["program", "duty program", "mfn", "min duty", "default duty", "minimum duties", "program description"], "programs"),
    (["fta", "free trade", "trade agreement", "preferential", "fta applied", "fta previously", "fta afterwards"], "fta"),
    (["trade lane", "lane", "coo coi hs", "trade corridor"], "lane"),
    (["currency", "fx", "exchange rate", "eur", "conversion", "usd", "gbp", "frankfurter"], "currency"),
    (["data quality", "quality", "validation", "iso format", "hs ratio", "95%", "warning", "data check"], "quality"),
    (["tab", "section", "navigation", "nav", "menu", "switch tab"], "tabs"),
    (["error", "troubleshoot", "problem", "issue", "not working", "failed", "authentication failed", "no data", "blank", "fix"], "troubleshoot"),
    (["applied rate", "effective rate", "rate paid", "rate calculation"], "applied_rate"),
    (["capture rate", "savings capture", "realization rate", "realized vs overpaid", "capture percentage"], "capture_rate"),
]


_FALLBACK = (
    "I'm not sure about that. Try asking about:\n\n"
    "- *Getting started / first run*\n"
    "- *Excel file format and required columns*\n"
    "- *e2open credentials (User ID, Password, Tenant)*\n"
    "- *COO, COI, HS Code, or FTA concepts*\n"
    "- *Overpaid duties and opportunities*\n"
    "- *Initiatives (PRE/POST comparison table, status, groups, End Date)*\n"
    "- *Savings Capture Rate*\n"
    "- *Filters, backup/restore, or logout*\n"
    "- *Reporting (World Map, Heat Map, Monthly Trend, HTML export)*\n"
    "- *Troubleshooting errors*"
)

_WELCOME = (
    "Hi! I can answer questions about how **Duty Optimizer** works.\n\n"
    "Ask me about: *getting started, Excel format, e2open credentials, "
    "COO/COI/HS Code, FTA, overpaid duties, opportunities, initiatives, "
    "PRE/POST comparison, Savings Capture Rate, End Date, "
    "Reporting charts (World Map, Heat Map, Monthly Trend), "
    "filters, backup/restore,* or *troubleshooting*."
)


def _match(question: str) -> str:
    q = question.lower()
    for keywords, key in _ROUTES:
        if any(kw in q for kw in keywords):
            return _ANSWERS[key]
    return _FALLBACK


@st.dialog("Duty Optimizer — Help", width="large")
def render_help_dialog() -> None:
    if "help_chat" not in st.session_state:
        st.session_state.help_chat = [{"role": "assistant", "content": _WELCOME}]

    for msg in st.session_state.help_chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    col_input, col_clear = st.columns([8, 1], vertical_alignment="bottom")
    with col_input:
        prompt = st.chat_input("Ask a question about Duty Optimizer…")
    with col_clear:
        if st.button("Clear", key="help_clear_chat", width="stretch"):
            st.session_state.help_chat = [{"role": "assistant", "content": _WELCOME}]
            st.rerun(scope="fragment")
    if prompt:
        st.session_state.help_chat.append({"role": "user", "content": prompt})
        st.session_state.help_chat.append({"role": "assistant", "content": _match(prompt)})
        st.rerun(scope="fragment")
