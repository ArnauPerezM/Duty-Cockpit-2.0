# Duty Analyzer — User Guide

## Overview

Duty Analyzer is a desktop application built to automate customs duty analysis through the E2Open API. It ingests transaction data from Excel, queries E2Open for applicable duty programs and rates, identifies overpayment opportunities, tracks duty optimization initiatives, and produces executive-level reports.

The app stores all results locally in a SQLite database. No data is sent to any cloud service outside of E2Open API calls during analysis runs.

---

## Navigation

The app has six sections accessible via the tab bar below the header:

| Tab | Purpose |
|---|---|
| **Process** | Upload transactions, connect to E2Open, run analysis |
| **Results** | View and edit transaction-level analysis output |
| **Opportunities** | Identify duty overpayment opportunities and create initiatives |
| **Initiatives** | Track duty optimization initiatives (PRE/POST analysis) |
| **Logs** | View execution logs and run history |
| **Reporting** | Executive dashboard and downloadable HTML report |

The **? Help** button (top-right of the header) opens this assistant at any time.

---

## Getting Started — First Run

### Step 1: Prepare the Excel file

The input file must contain a sheet named **Transactions** (the sheet name is configurable in the Process tab). Required columns:

| Column | Description |
|---|---|
| **Invoice Number** | Unique identifier for the invoice |
| **Material Number** | Product or part identifier |
| **COO** | Country of Origin — 2-letter ISO code (e.g. `CN`, `DE`, `US`) |
| **COI** | Country of Import — 2-letter ISO code (e.g. `ES`, `US`, `FR`) |
| **HS Code** | Harmonized System tariff code (minimum 6 digits recommended) |
| **Customs Value** | Declared customs value of the goods |
| **Duty Paid** | Duties already paid (can be 0) |

Optional columns: `Weight`, `CV Currency`, `DP Currency`, `Status`, `Comment`.

If a column named `Analyzed` is present, rows where `Analyzed = True` are automatically skipped.

### Step 2: Connect to E2Open

In the Process tab, click the **Connect to E2Open** form and enter:
- **Environment** — `UAT` (testing) or `PRO` (production)
- **User ID** — your E2Open user UUID
- **Password** — your E2Open password
- **Tenant ID** — your organization's tenant UUID
- **Account Name** — a short label shown in the header (saved for future sessions)

Credentials are stored only in the active session and never written to disk.

### Step 3: Upload and configure

- Upload the Excel file using the file uploader
- Confirm the sheet name (default: `Transactions`)
- Set the **Reference Date** — the date used when querying E2Open duty rates

### Step 4: Run the analysis

Click **▶ Run**. The app will:
1. Validate and clean the input data
2. Open an E2Open session
3. Query duty rates for each transaction row
4. Save results to the local database
5. Navigate automatically to the Results tab

---

## Process Tab

### Pre-run summary

After uploading a file, the app shows two KPI cards:
- **Candidate rows** — number of rows that will be sent to E2Open
- **Data quality** — percentage of rows with valid HS codes (≥6 digits) and ISO-2 country codes

Rows with blank COO, COI, HS Code, or zero Customs Value are separated into **Missing rows** (shown in a collapsible expander). These rows are excluded from the API run but are counted in the final summary.

**Data quality warnings** appear if less than 95% of rows have valid HS codes or valid ISO-2 country codes.

### Duplicate detection

Before starting, the app checks whether any transactions in the uploaded file were already sent to E2Open with the same reference date. If duplicates are found:

- **Skip duplicates** — sends only new rows (recommended)
- **Reprocess all** — re-sends all rows including duplicates
- **Cancel** — aborts without sending anything

### Running and cancellation

During execution, a progress bar and status log track each row. Click **✕ Cancel** to stop the run after the current row completes. Results up to the cancellation point are saved to the database.

### Post-run summary

After completion, four KPI cards show:
- **Processed OK** — rows successfully returned by E2Open
- **Failed** — rows that returned an error from E2Open
- **Missing** — rows skipped due to incomplete data
- **Total** — all rows from the original file

### Geographic map

A choropleth world map visualizes transaction data with four selectable views:
- **Customs Value (EUR)** — total customs value by Country of Import
- **Duties Paid (EUR)** — total duties paid by Country of Import
- **Potential Savings (EUR)** — overpaid duties by Country of Import
- **% Failed/Missing** — data quality by Country of Import

The **Top 10 Countries** table below the map ranks countries by the selected metric.

---

## Results Tab

Displays all transactions returned from E2Open, merged with the original input data.

### KPI cards

| KPI | Description |
|---|---|
| Transactions | Total rows in the database (after filters) |
| Countries of Import | Unique COI values |
| Countries of Origin | Unique COO values |
| Customs Value | Total declared customs value (EUR) |
| Duty Exposure | Total default duties (what would be paid without optimisation) |
| Duty Paid | Total duties actually paid |

### Charts

- **Customs Value by COI** — pie chart of top 8 countries of import by customs value
- **Duty Exposure gauge** — semicircle showing Duties Paid vs. Duty Exposure scope, with a line marking the Minimum Duties threshold
- **Duties Paid by COI** — pie chart of top 8 countries of import by duties paid

### Results table

The table shows all transaction fields. Key columns:

| Column | Description |
|---|---|
| COO / COI | Country of Origin / Import |
| HS Code | Tariff classification code |
| Min Duty Program | Best applicable duty program from E2Open |
| Min Duty Rate | Rate under the minimum duty program (%) |
| Minimum Duties | What should be paid under the best program (EUR) |
| Default Duty Program | Standard MFN duty program |
| Default Duty Rate | Standard MFN rate (%) |

### Editing results — Inline mode

Click **Edit (inline)** to open the data editor. Editable fields are: `COO`, `COI`, `HS Code`, `Customs Value`, `Weight`, `Duty Paid`, and `Comment`. Check the `_delete` column to mark rows for deletion.

Click **Review changes** to see a diff summary, then **Apply changes** to save to the database.

### Editing results — Excel mode

Click **Edit via Excel** to:
1. Download the editable Excel file (with `_db_id` and `_delete` control columns)
2. Edit offline
3. Re-upload the file
4. Review the diff preview
5. Apply changes

The `_db_id` column links each row to the database record — do not modify it.

### Drill-down from Opportunities

Clicking **Show Details** in the Opportunities tab opens the Results tab filtered to the selected trade lanes (COO + COI + HS Code). A **Clear** button resets to the full dataset.

---

## Opportunities Tab

Identifies trade lanes where duties paid exceed the minimum applicable duties, indicating potential overpayments.

### KPI cards

| KPI | Description |
|---|---|
| Transactions | Rows included in opportunity analysis |
| Opportunities | Distinct trade lanes with overpayments |
| Customs Value | Total customs value of affected transactions |
| Duty Exposure | Total default duties (MFN baseline) |
| Duty Paid | Total duties actually paid |
| Overpaid Duties | Duty Paid minus Minimum Duties (potential savings) |

### Charts

Four horizontal bar charts visualize overpayments:
1. **By Product** — top 10 material numbers by overpaid amount
2. **By COI** — top countries of import, optionally stacked by duty program
3. **By Trade Lane** — COO→COI pairs ranked by overpaid amount
4. **By Duty Program** — which programs have the most overpayment

### Opportunities table

Rows are grouped by **COO · COI · HS Code · Material Number**. Key columns:

| Column | Description |
|---|---|
| Overpaid Duties | Sum of (Duty Paid − Min Duties) for this group |
| Applied Rate | Effective rate paid (%) |
| Min Duty Rate | Optimal rate available (%) |
| FTA Applied Previously | Whether FTA was used before the overpayment period |
| FTA Applied Afterwards | Whether FTA was used after the overpayment period |
| First / Last FTA Rate Paid | Dates of first/last FTA usage |

Boolean columns (`True`/`False`) highlight rows where FTA was not consistently applied.

Rows with existing initiatives are **hidden by default**. Check **Show rows with existing initiatives** to display them.

### Creating initiatives

1. Select one or more rows using the checkboxes
2. Click **Create Initiative**
3. The selected trade lanes are saved as new initiatives in the Initiatives tab

If some selected rows already have initiatives, the app warns before creating duplicates.

### Show Details (drill-down)

Select rows and click **Show Details** to navigate to the Results tab filtered to those specific trade lanes.

---

## Initiatives Tab

Tracks duty reduction initiatives through their lifecycle: Identified → Validated → Completed (or Discarded).

### KPI cards

| KPI | Description |
|---|---|
| Est. Annual Savings | Estimated yearly duty savings (auto-computed from transaction data) |
| Potential Reimbursements | Manual estimate of recoverable past overpayments |
| Total Potential Savings | Annual Savings + Potential Reimbursements |
| FTA Savings Realized | Actual duty savings confirmed post-implementation |
| Reimbursements Realized | Actual reimbursements received |
| Total Savings Realized | FTA Savings + Reimbursements Realized |

### Charts

- **Initiative Portfolio by Status** — donut chart showing count of initiatives by status (Identified, Validated, Completed, Discarded) with total count in the centre
- **Top 10 Open Initiatives by Country of Import** — horizontal bar chart of COIs with the most open (Identified or Validated) initiatives, sorted by count

### Status values

| Status | Meaning |
|---|---|
| **Identified** | Opportunity found, not yet validated |
| **Validated** | Confirmed by the team, ready to act |
| **Completed** | FTA or optimization implemented |
| **Discarded** | Not actionable, removed from active tracking |

### Initiatives table

Shows all initiatives with key columns:

| Column | Description |
|---|---|
| COO / COI / HS Code | Trade lane identifiers |
| Material Number | Product identifier (if specified) |
| Min Duty Program | Applicable preferential program |
| Status | Current lifecycle stage |
| Comments | Free-text notes |
| Duties Overpaid | Initial overpayment estimate |
| Potential Reimbursements | Manually entered recovery estimate |
| Reimbursements Realized | Actual reimbursements received |
| Total Savings Realized | Confirmed total savings |

### PRE / POST comparison table

Selecting an initiative expands its detail panel, showing a side-by-side comparison table:

| Row | PRE — Before | POST — After |
|---|---|---|
| Customs Value | At inception | Post-implementation (12-month window) |
| Duty Paid | At inception | Post-implementation |
| Effective Rate | As-is rate (%) | Realized avg. rate (%) |
| Duty To-Be Paid | Under optimal program | — |
| To-Be Rate | Optimal rate (%) | — |
| Est. Annual CV | Annualised customs value | — |
| Annual Savings | Estimated | Realized |
| Overpaid | Initial | Final (after reimbursements) |
| Reimbursements | Potential | Realized |
| **Total Savings** | **Potential** | **Realized** (highlighted) |

POST metrics are automatically populated from transactions in the **365 days after the Implementation Date**. For POST to populate, the initiative must have status **Completed** and a set Implementation Date.

### Dates

- **Start Date** — when the initiative was identified (editable)
- **Implementation Date** — when the optimization was put in place (editable)
- **End Date** — auto-calculated as Implementation Date + 365 days, but can be overridden manually. The label shows *(auto)* when no manual value is set.

Click **Save Dates** to persist any date changes.

### Editing initiatives

Select one or more rows and the detail panel expands below. Editable fields:
- Status (dropdown)
- Start Date, Implementation Date, and End Date
- Potential Reimbursements
- Reimbursements Realized
- Comments

Click **Save changes** to persist edits to the database.

### Grouping initiatives

Select two or more initiatives and click **Group Initiatives** to merge them into a group. The parent row shows aggregated metrics; child rows are collapsed by default. Assign a custom name to the group using the text field in the group expander.

Click **Ungroup Selected** on a group's child rows to remove them from the group.

### Deleting initiatives

Select rows and click **Delete selected**. This is permanent and cannot be undone.

---

## Logs Tab

### Date filter

Filter the run history by date range (From / To). The date inputs default to the full range of available runs.

### KPI cards

| KPI | Description |
|---|---|
| Total Lanes Processed | Sum of all candidate rows across filtered runs |
| Total Runs | Number of analysis runs in the filtered period |
| Success Rate | OK rows ÷ (OK + Failed + Missing) across all filtered runs |

### Run History table

Each row represents one analysis run:

| Column | Description |
|---|---|
| ref_date | Reference date used for the API query |
| started_at | Timestamp when the run started |
| total_candidates | Rows submitted to E2Open |
| total_ok | Rows returned successfully |
| total_failed | Rows that returned API errors |
| total_missing | Rows skipped (incomplete data) |
| cancelled | Whether the run was stopped manually |
| account_label | Account name used for the run |
| environment | UAT or PRO |

### Execution log

The current session's event log shows row-by-row API results (last 200 events). Raw API response payloads (`session_output` events) are excluded for readability.

---

## Reporting Tab

### KPI cards

| KPI | Description |
|---|---|
| Total Customs Value | Cumulative declared value (EUR) |
| Total Duty Paid | Total duties paid (EUR) |
| Overpaid Duties | Duty Paid − Minimum Duties across all transactions |
| Savings Realized | FTA savings + reimbursements from initiatives |
| Savings Capture Rate | Savings Realized ÷ Overpaid Duties (%) |

### Dashboard charts

| Chart | Description |
|---|---|
| World Map | Selectable metric by Country of Import: Customs Value / Duty Paid / Overpaid Duties |
| Top 10 Import Countries — Duties Paid | Countries of Import with highest duties paid |
| Top 10 Import Countries — Overpaid Duties | Countries of Import with highest overpayments |
| Heat Map | COO × COI intensity matrix with selectable metric (Customs Value / Duty Paid / Savings Realized). Cells show abbreviated values with contrast-aware text colour |
| Monthly Trend | Area chart: Duty Paid (purple) vs. Minimum Duties (dotted), with the area between them (Overpaid Duties) highlighted in purple |
| Est. Annual Savings vs Savings Realized | Grouped horizontal bar by COI comparing estimated annual savings (PRE) vs. savings realized (POST) |
| Initiative Portfolio by Status | Donut chart by status with total initiative count in the centre |
| Top Trade Lanes | Table: COO→COI with transactions, duties, and effective rate |

All charts and KPIs reflect the **sidebar filters** currently applied.

### Downloading the report

Click **Download Report** to get a self-contained HTML file. The report includes:
- Account and environment metadata
- Executive narrative with Savings Capture Rate
- 9 KPI cards (Customs Value, Duty Paid, Minimum Duties, Overpaid Duties, Savings Realized, Savings Capture Rate, Failed, Missing/Skipped, Lanes Processed)
- Key findings: Top 5 COI by Overpaid Duties, Top 5 COI by Duty Paid, Top 5 HS Codes by Customs Value
- Monthly trend chart (Chart.js) — Duty Paid vs Minimum Duties with Overpaid area
- Initiative portfolio with Savings Capture Rate
- Detailed results table (first 500 rows)

The HTML file is self-contained and can be opened in any browser or emailed without dependencies.

---

## Sidebar

The sidebar is always visible and contains global controls.

### Filters

Sidebar filters apply simultaneously to the **Results**, **Opportunities**, **Initiatives**, and **Reporting** tabs:

| Filter | Description |
|---|---|
| Time (From / To) | Date range of transactions |
| Origin Country (COO) | Filter by country of origin |
| Import Country (COI) | Filter by country of import |
| HS Code | Filter by tariff code |
| Material Number | Filter by specific product |

Click **Reset Filter** to clear all filters and return to the full dataset.

### Backup & Restore

At the bottom of the sidebar:

- **Download backup** — exports the entire local SQLite database as a `.db` file. Use this to back up all analysis results, initiatives, and run history.
- **Restore** — upload a previously downloaded `.db` file to replace the current database. **A backup of the current database is saved automatically before any restore.**

### Logout

Click **Logout** at the bottom of the sidebar to disconnect your E2Open session. All analysis data in the database is preserved — only the active session credentials are cleared.

---

## Key Concepts

### COO — Country of Origin
The 2-letter ISO code of the country where goods were **manufactured or substantially transformed** (e.g. `CN` = China, `DE` = Germany, `US` = United States). COO determines which preferential trade agreements and duty programs may apply.

### COI — Country of Import
The 2-letter ISO code of the **destination country** where goods are being imported (e.g. `ES` = Spain, `FR` = France, `GB` = United Kingdom). Combined with COO and HS Code to determine the applicable duty rate.

### HS Code — Harmonized System
A standardized international code used to classify traded goods (e.g. `8471.30` for laptops). The code determines which tariff schedule applies for a given COO→COI pair. Codes with fewer than 6 digits may produce inaccurate duty lookups — 6 or more digits are recommended.

### Reference Date
The date passed to E2Open when querying duty rates. Tariff schedules change over time, so different reference dates may return different rates. Always set the reference date to the period you are analyzing.

### Min Duty Program
The duty program identified by E2Open that results in the **lowest applicable duty rate** for a given COO→COI→HS combination. This is the program your company should be using. Overpayment occurs when the rate actually paid exceeds this minimum.

### Default Duty Program (MFN)
The **Most Favored Nation** rate — the standard tariff applied when no preferential trade agreement is in force. This is the baseline rate before any FTA or special program is considered.

### FTA — Free Trade Agreement
A preferential trade agreement between countries that reduces or eliminates duty rates. The Opportunities tab identifies trade lanes where an FTA program exists (`Min Duty Rate < Default Duty Rate`) but was not applied, or was not consistently applied.

### Overpaid Duties
The difference between duties actually paid and the minimum applicable duties: `Duty Paid − Minimum Duties`. Positive values indicate overpayments that may be recoverable through duty drawback or future rate corrections.

### Savings Capture Rate
`Savings Realized ÷ Overpaid Duties × 100`. Measures what percentage of the identified savings opportunity has been captured through initiatives. A higher rate means the programme is delivering results effectively.

### Trade Lane
A unique combination of **COO + COI + HS Code** (optionally + Material Number). Trade lanes are the unit of analysis for opportunities and initiatives.

### E2Open Environment
- **UAT** — User Acceptance Testing environment. Safe for testing and development; does not affect production data.
- **PRO** — Production environment. Use for live analysis with real transaction data.

---

## FX Currency Handling

All monetary values are converted to **EUR** for analysis and reporting. The app uses live exchange rates fetched from multiple sources (open.er-api.com → Frankfurter → ECB fallback) and caches them for 4 hours.

Original currency values are preserved in the database (`customs_value_original`, `cv_currency_original`) so that source data integrity is maintained.

---

## Data Quality

Before running the analysis, the app validates:
- **COO/COI format** — must be 2-letter ISO codes. Accepted aliases: `UK` → `GB`, `EL` → `GR`.
- **HS Code format** — digits only; 6+ digits recommended for accurate lookups.
- **Customs Value** — must be a positive number. Zero or blank values cause rows to be excluded.
- **Missing rows** — rows with any blank key field (COO, COI, HS Code) are separated and not sent to E2Open.

A warning is shown if fewer than 95% of rows pass the HS Code or ISO format checks.

---

## Troubleshooting

### "Authentication failed"
Check that User ID, Password, and Tenant ID are correct for the selected environment (UAT or PRO). UUID format is `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.

### "No candidate rows to process"
All rows in the Excel file either have `Analyzed = True` or are missing required fields. Check that the sheet name matches the configured value and that COO, COI, HS Code, and Customs Value columns are populated.

### Rows appear in Missing rows
Missing rows have at least one blank key field (COO, COI, HS Code) or a zero/blank Customs Value. Review the source data for those rows.

### Results show high Failed count
E2Open returned errors for those rows. Common causes: invalid COO/COI code, HS code not found in E2Open's tariff database, or API rate limits. Check the Logs tab for specific error messages.

### Charts or KPIs show no data
Sidebar filters may be excluding all data. Click **Reset Filter** in the sidebar to clear all active filters.

### "Restore" fails
The uploaded file must be a valid `.db` file created by the Duty Analyzer backup function. Files from other SQLite databases are rejected.

### Map shows no countries
COO/COI codes must be 2-letter ISO format. The map converts them to ISO-3 internally. Unrecognized codes are silently excluded from the map. Check the Results tab for rows with unusual country codes.

### POST metrics show 0 for a Completed initiative
POST metrics are only computed when the initiative has status **Completed** and a set **Implementation Date**. Transactions are matched by COO + COI + HS Code within the 365-day window after that date.
