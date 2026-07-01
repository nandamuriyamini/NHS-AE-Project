# NHS A&E Dataset — Complete Documentation

Everything you need to know about the datasets used in this project: what they are, where they
came from, what they tell us, what their limitations are, and why they matter for business
decisions.

---

## 1. What is this data about?

This project is built on **NHS England's published A&E (Accident and Emergency) statistics**.
These are the official government figures that measure how well NHS hospitals are performing
against the national promise that 95% of patients will be seen, treated and either admitted or
discharged within 4 hours of arriving at A&E.

Every month, NHS England collects performance data from every hospital in England that runs an
A&E department — 215 organisations in total — and publishes it publicly. This project uses three
years of that data, from April 2023 to March 2026.

The data tells us:
- **How many patients** arrived at each A&E department each month
- **How long they waited** — specifically, how many breached the 4-hour target, and how many
  waited 12 hours or more
- **Who those patients were** — their age group, gender, ethnicity, and what they came in for
- **What happened to them** — whether they were admitted to hospital, discharged, or left before
  being seen
- **Which hospitals** are hitting the target and which are significantly below it
- **Where in England** the demand is highest

---

## 2. The 6 datasets — what each one covers

### 2.1 monthly_ae_summary.csv — National Monthly Totals

**What it is:** The headline A&E statistics for the whole of England, rolled up by month.
No individual hospital detail — this is the national picture.

**What's inside:**
- Total A&E attendances per month, split by department type (Type 1 = major A&E departments,
  Type 2 = single-specialty units, Other = minor injury units and walk-in centres)
- Number of attendances where the patient waited over 4 hours
- Number of patients who waited 4–12 hours from being admitted to getting a bed
- Number of patients who waited over 12 hours from being admitted to getting a bed
- Emergency admissions via A&E (patients who ended up being kept in hospital)

**Used for:** The national trend line in the dashboard, the yearly summary, the headline KPI
cards showing 33M total attendances and 1M 12-hour waits.

---

### 2.2 AE_by_provider.csv — Trust-Level Performance

**What it is:** The same A&E statistics but broken down by individual hospital trust — the
215 organisations that run A&E departments across England. This is where trust comparisons
come from.

**What's inside:**
- Trust name, code, region
- Whether the data period is Monthly or Quarterly
- Total A&E attendances per trust per period
- Number waiting over 4 hours
- Percentage seen within 4 hours (the key performance metric)
- Period-over-period comparison data

**Used for:** The Trust Bottom 10 RAG chart, the Trust Biggest Improvers chart, the Trust
Performance Ranking Gold table, and the Regional Summary.

---

### 2.3 NEL_YTD_growth_rates.csv — Emergency Admission Growth

**What it is:** NEL stands for Non-Elective — in NHS terms, this means emergency admissions
(patients admitted to hospital urgently, not for a pre-planned procedure). This dataset tracks
how much emergency admission activity is growing or shrinking compared to the same period last
year, year-to-date.

**What's inside:**
- Year-to-date emergency activity for each trust
- Year-to-date growth rate (how much has it changed vs last year)
- Proportion of emergency activity with a zero-day length of stay (patients admitted but
  discharged the same day — a measure of efficiency and patient flow)
- Regional breakdown alongside trust-level figures

**Used for:** The NEL YTD Growth Rates Gold table and the "Emergency Admission Pressure vs
Regional Benchmark" analysis — a leading indicator of future A&E pressure.

---

### 2.4 ECDS_Activity.csv — Emergency Care Detail (Oct 2025 onwards)

**What it is:** ECDS stands for Emergency Care Data Set. This is NHS England's newer, more
detailed A&E reporting system that replaced the older method from October 2025 onwards. It
provides much richer demographic and clinical breakdowns.

**What's inside (multiple sheets per workbook):**
- Age breakdown of A&E attendances (0–4 years, 5–14, 15–24, 25–44, 45–64, 65–79, 80+)
- Gender breakdown
- Ethnicity breakdown
- Chief Complaint breakdown (why people came to A&E — chest pain, falls, self-harm, etc.)
- Frailty Score breakdown (relevant for older patients)
- Organisation-level summary

**Used for:** The ECDS Demographic Summary Gold table, ECDS Org Summary, and the demographic
breakdown chart in the Power BI dashboard.

---

### 2.5 ECDS_Supplementary.csv — Emergency Care Detail (Apr 2023 – Sep 2025)

**What it is:** The same ECDS-style demographic breakdowns, but from the earlier reporting
era (April 2023 to September 2025). NHS changed its ECDS reporting format in October 2025,
so the pre- and post-October data come from two different reports with slightly different
column structures, but the same underlying metrics.

**Why two files instead of one:** NHS didn't retroactively reformat the older data into the
new ECDS_Activity format — it stays in the old format. To get a continuous 3-year view, both
files must be combined, with each branch labelled by which source report it came from.

**Used for:** Same as ECDS_Activity — combined together via UNION ALL in the Silver layer to
create a single continuous 3-year demographic view.

---

### 2.6 ECDS_Performance.csv — Emergency Care Performance Metrics

**What it is:** A set of detailed performance metrics captured through the ECDS system —
things like time to initial assessment, time to treatment, and specific admission and discharge
metrics. Published in long format (one row per metric per organisation per period, rather than
one row per organisation with many columns).

**Used for:** The ECDS Performance Gold table, showing average, minimum and maximum values
per metric across all organisations — surfaces which metrics have the biggest spread between
best and worst performers.

---

## 3. How we got the data — downloading from NHS England

**Source:** All data was downloaded directly from the NHS England website, specifically the
"A&E Waiting Times and Activity" section at:
**england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/**

**What NHS publishes:** Each month, NHS England publishes an Excel workbook (or sometimes a
set of Excel workbooks) containing that month's data. The workbooks have multiple tabs — one
tab per breakdown type (e.g., "Summary", "By Provider", "Age Breakdown" etc.).

**What we did:**
1. Downloaded the monthly/quarterly Excel workbooks spanning April 2023 to March 2026 —
   approximately 35+ separate workbooks covering this period.
2. Wrote a Python combining script that opened each workbook, read the relevant tabs, and
   stacked all the time periods together into a single flat CSV file per dataset type.
3. Generated six clean CSV files: monthly_AE_summary.csv, AE_by_provider.csv,
   NEL_YTD_growth_rates.csv, ECDS_Activity.csv, ECDS_Performance.csv, ECDS_Supplementary.csv.
4. Uploaded these six CSVs to the `raw` container in Azure Data Lake Storage.

**Why not connect directly to the NHS website?** NHS doesn't publish a live API for these
statistics. The data is published as Excel file downloads — so the only way to get it is to
download the files manually, combine them, and load the combined result into the pipeline.

---

## 4. Important thing we discovered — NHS suppression markers

NHS deliberately hides very small numbers in some cells by writing a dash (`-`) or asterisk
(`*`) instead of a number. For example, if only 2 patients in a certain age band were admitted
to a small trust in a particular month, NHS writes `-` instead of `2` — to protect patient
privacy (a count of 2 could theoretically be traced back to a specific individual).

**The problem this caused:** When Databricks or Synapse reads a column that mostly contains
numbers but sometimes contains `-` or `*`, it infers the entire column as text (VARCHAR), not
as a number. This meant that any attempt to SUM or AVG those columns failed with a type error.

**The fix:**
- In Synapse SQL: `TRY_CAST(column AS FLOAT)` — this tries to convert each value to a decimal
  number, and silently returns NULL for anything it can't convert (like `-` or `*`). NULL is
  simply ignored by SUM and AVG.
- In Power BI DAX: `IFERROR(VALUE(column), 0)` — same idea, but for DAX measures.

This is a real-world data engineering challenge that appears in almost all government and
healthcare datasets — not just NHS. Handling it correctly is the difference between a pipeline
that crashes on real data and one that processes it cleanly.

---

## 5. The Excel corruption problem

When NHS publishes data as Excel workbooks and someone opens one of those workbooks and saves
it — even without making any obvious changes — Excel can silently reformat date values. A date
stored as "October 2025" might get saved as "10-01-25" or another format depending on the
regional settings of the machine doing the saving.

This happened to two of our CSV files. The dates looked visually correct in Excel but were
technically in the wrong format, which caused Synapse to fail to parse them correctly.

**The fix:** We regenerated both affected CSVs from the original Excel workbooks using Python's
`openpyxl` library — reading the raw cell values before Excel's formatting engine gets a chance
to interfere. Never opening the source files in Excel directly.

**The lesson:** Never open a CSV file that feeds a data pipeline in Excel and save it. Even if
you don't intend to change anything, Excel can corrupt date and number formatting invisibly.

---

## 6. Pros and cons of this dataset

### Pros

**It's real.** This isn't synthetic or sample data — it's the actual statistics NHS England
uses to manage the national health service. Every row represents a real patient, a real
hospital, a real month.

**It's open.** NHS England publishes all of this under the Open Government Licence — free to
use, share, and build on, with no special access required. No data sharing agreements, no
approvals process.

**It's comprehensive.** 215 hospital trusts. Every NHS region. Three years of monthly data.
This is a complete national picture, not a sample of a few hospitals.

**It's consistent.** NHS has collected A&E performance data using the same core methodology
for many years. The 4-hour target, the counting rules, the type classifications — they've been
stable enough that comparisons across time are meaningful.

**It's clinically meaningful.** The fields aren't invented for a technical exercise — they
track things that matter in the real world: wait times, admission decisions, patient
demographics, outcomes. Every column has a genuine operational meaning.

### Cons

**No patient-level data.** Everything is aggregate — monthly totals per trust per metric.
You can't ask "what happened to the 65-year-old male who arrived at Leeds A&E on a Tuesday
night?" The data simply doesn't go to that level.

**Suppression markers** (as described above) mean some small counts are invisible. For very
small trusts or very rare demographic combinations, some cells will always be `-` or `*`.

**Two different ECDS formats.** The demographic data before October 2025 and after October
2025 comes from different report formats with different column names. Combining them requires
explicit mapping logic that accounts for these differences.

**Long, inconsistent column names.** NHS creates column names by combining a group header with
a child header, separated by a space. The resulting names can be 150+ characters long and
contain spaces, colons, parentheses and ampersands — none of which are valid in most SQL
systems without special handling.

**Pre-calculated metrics.** Some fields — like the percentage within 4 hours — are calculated
by NHS before publication. This means we can't independently recalculate them if our
understanding of the numerator or denominator differs. We have to trust NHS's calculation.

**File-based delivery.** There is no live API. Getting new data means downloading new Excel
workbooks from the NHS website every month and re-running the combining script. This process
is currently manual.

---

## 7. What we learned and understood from the data

### Finding 1 — The NHS has been stuck for 3 years

National performance has fluctuated between 70% and 78% within 4 hours across the entire
period. It has never hit the 95% target. Not even close. The trend line is essentially flat —
there is no sustained recovery period, just minor seasonal variation.

**Business meaning:** This is not a temporary dip. This is a structural problem. Any
intervention designed to recover to 95% has to be structural too — not a short-term fix.

### Finding 2 — 12-hour waits are actively getting worse

While the 4-hour breach rate stays flat, the number of patients waiting 12 hours or more is
climbing year on year, with a sharp spike in early 2026. This is hidden inside the data — it
doesn't appear in most headline reporting.

**Business meaning:** The 4-hour figure is a broad measure of strain. The 12-hour figure is
a measure of the most serious cases. A rising 12-hour count alongside a flat 4-hour count
means the severity of breaches is increasing, even if the volume isn't. That's a patient
safety concern, not just a performance metric.

### Finding 3 — Working-age adults, not the elderly, dominate A&E

The most common patient groups attending A&E are adults aged 25–44 and 45–64 — not the 65+
age groups most people assume are the primary drivers of A&E demand.

**Business meaning:** Workforce planning, triage protocols, and community alternative services
should be designed around the actual patient mix — not assumptions. Treating A&E as primarily
an elderly patient problem risks misallocating resources.

### Finding 4 — There is enormous variation between trusts

The difference between the best and worst performing trusts is enormous. The top performers —
mainly smaller, specialist units — achieve 95–100%. The bottom 10 major A&E departments are
achieving 45–55%. That's a 40–50 percentage point gap between the best and worst of the 215
trusts tracked.

**Business meaning:** The average national figure masks this variation. National average of
73% doesn't mean all trusts are at 73% — it means some are at 95% and some are at 50%.
Identifying and understanding what the top performers do differently is one of the most
actionable things this data can drive.

### Finding 5 — Improvement is possible, but rare

The Trust Biggest Improvers chart shows that some trusts — like Wrightington, Wigan and Leigh,
and Kingston and Richmond — have made meaningful period-over-period improvements. This proves
the target isn't impossible, just difficult.

**Business meaning:** A programme of peer learning — where struggling trusts are paired with
recently-improving trusts to understand what changed — is directly evidenced by this data.

### Finding 6 — Regional pressure is uneven

NHS England Midlands and London carry the highest total A&E volume. These regions need
proportionally greater resource and support than regions with lower demand if the system is to
move as a whole.

---

## 8. Business value — what decisions this data can drive

**Performance Management:**
Every month, this data lets NHS England identify which of the 215 trusts are significantly
below the 95% target, how far below, and whether they are improving or declining. Without this
pipeline, that analysis would take a team of analysts days to produce from raw Excel files.
With this pipeline, it's updated automatically and visible in seconds.

**Resource Allocation:**
The regional summary shows where in England A&E demand is highest. Capital investment,
additional staffing, and capacity expansion decisions should be led by this data, not
distributed equally across all regions regardless of need.

**Capacity Planning:**
The NEL Growth Rates table is a leading indicator — it shows which trusts are seeing emergency
admission growth faster than their regional average. Trusts where emergency admissions are
growing fast today are likely to face A&E pressure in the near future. Identifying them early
allows intervention before the problem shows up in the breach statistics.

**Staffing and Workforce Design:**
The demographic finding that working-age adults dominate A&E attendance challenges assumptions
about shift patterns, staffing mix, and community alternative services. If 25–44 year olds
are the biggest group, services that only run 9–5 weekdays won't intercept them before they
go to A&E.

**Patient Safety Monitoring:**
The streaming dashboard surfaces "left before treatment" events in near real-time. In a real
operational setting, if a trust's "left before treatment" rate climbs during an afternoon shift,
that's a safety signal — patients are giving up on waiting, and some of those patients may have
needed urgent care. Catching it in real time means there's still time to act.

**Clinical Pathway Improvement:**
The chief complaint breakdown in ECDS data shows what people are actually coming to A&E for.
If falls, self-harm, or chest pain are disproportionately common in specific trusts or regions,
that points to where community prevention programmes or specialist pathways could reduce
avoidable A&E demand.

---

## 9. Summary — in one paragraph

This project uses six real NHS England datasets covering 3 years of A&E activity across 215
hospital trusts. The data is publicly available from the NHS England website, downloaded as
Excel workbooks and combined into clean CSV files using Python. It tells us who is coming to
A&E, how long they wait, which hospitals are struggling, and where the pressure is greatest
geographically and demographically. The main challenges with the data are NHS suppression
markers (which force text-to-number conversion logic), inconsistent column naming, and the
split between two ECDS reporting eras. The business value is real and actionable: from
identifying the worst-performing trusts and matching them with improvers, to planning resources
around actual patient demographics, to catching patient safety signals live during operational
shifts.
