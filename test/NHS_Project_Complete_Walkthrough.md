# NHS A&E Data Platform — Complete Walkthrough (Plain English)

This document explains, in order, everything we built in this project and why — written so you can
re-read it months from now and still follow exactly what happened and why each decision was made.

---

## 1. What this project actually is, in one paragraph

We took real NHS England statistics about A&E (Accident & Emergency) hospital visits, and built a
proper data pipeline around them — the same kind of pipeline a real company would build, using real
Azure tools. We did this in two separate flavours: a **batch** version (processes files that already
exist, like monthly reports) and a **streaming** version (reacts to events as they happen, live). Each
flavour ends in its own Power BI dashboard.

---

## 2. The big picture: two pipelines, same shape

Both pipelines follow the same basic shape, called **medallion architecture** — data moves through
three "layers," each one cleaner than the last:

- **Bronze** = raw, untouched copy of the data, exactly as it arrived. Think of it as a photocopy of
  the original document — nothing is fixed or interpreted yet, it's just stored safely.
- **Silver** = cleaned-up version. Column names made consistent, dates fixed, duplicates removed,
  obviously broken values handled.
- **Gold** = the "ready to present" version — the exact tables the dashboards actually read from.

The difference between batch and streaming is **what feeds Bronze**:
- Batch: NHS files that already exist (CSV/Excel exports).
- Streaming: a live feed of events arriving continuously, one at a time.

---

## 3. Part 1 — Getting and cleaning the NHS data (batch side)

### Where the data came from
NHS England publishes statistics on A&E performance — how many people attended, how many waited
over 4 hours, broken down by hospital trust, by age, by gender, by outcome, and so on. We downloaded
several of these published reports (Excel files) covering roughly three years.

### Combining many files into one clean dataset
NHS publishes a new file every month/quarter, each with the same structure. We wrote a script to
read all of them and combine them into a small number of clean, consistent CSV files — one row per
metric per organisation per time period, rather than dozens of separate spreadsheets.

### The Excel corruption problem (an important lesson)
At one point, two of these combined files (`ECDS_Activity.csv` and `ECDS_Performance.csv`) had been
opened and re-saved in Microsoft Excel. Excel **silently reformats date-like text** when you save a
CSV — it turned dates like "October 2025" into short, locale-specific formats like "10-01-25", which
then failed to parse correctly later on in Synapse. The values looked fine to a human eye in Excel,
but were technically corrupted underneath.

**The fix:** we wrote a Python script to regenerate both files fresh, directly from the *original*
source Excel workbooks — never opening or re-saving them in Excel itself. This produced ~594,000 and
~96,000 clean rows respectively, with zero broken dates.

**Lesson for the future:** never open a CSV that feeds a data pipeline in Excel and save it — even
just opening and closing without obvious edits can corrupt it.

---

## 4. Part 2 — Setting up the Azure building blocks

Think of these as the physical pieces of infrastructure we needed, each with a simple job:

- **Azure Data Lake Storage (ADLS) Gen2** — the "filing cabinet." This is where Bronze and Silver
  data physically lives, organised into folders/containers (`bronze`, `silver`, `gold`).
- **Azure Databricks** — the "cleaning station." This is where we ran Python/Spark code to actually
  transform Bronze data into Silver data.
- **Azure Synapse (Serverless SQL)** — the "reporting counter." This is where the Gold tables live,
  built using SQL, ready for Power BI to query.
- **Azure Key Vault** — the "lockbox." Stores secrets (passwords, connection strings) so they never
  appear directly in code. Databricks and Data Factory both fetch secrets from here at runtime.
- **Azure Data Factory (ADF)** — the "conductor." Doesn't store or process data itself — its only job
  is to trigger the right things in the right order, automatically, on a schedule.
- **Azure Event Hubs** (streaming only) — the "live mailbox." Receives a continuous stream of small
  event messages and holds them briefly until something reads them.

---

## 5. Part 3 — Building the 11 Gold tables in Synapse (batch)

In Synapse, we built 11 separate "Gold" tables, each one shaped for a specific reporting need:
`national_monthly_trend`, `trust_kpis_monthly`, `trust_kpis_quarterly`, `nel_ytd_growth_rates`,
`ecds_performance`, `ecds_org_summary`, `ecds_age_breakdown`, `ecds_gender_breakdown`,
`ecds_ethnicity_breakdown`, `ecds_chief_complaint_breakdown`, `ecds_frailty_breakdown`.

### How a Gold table actually gets built — CETAS, in plain English
We used a SQL command called **CETAS** ("Create External Table As Select"). In simple terms: "run
this SELECT query against the Silver data, and save the result as a brand new table called X." The
underlying engine doesn't copy data into a database in the traditional sense — it reads directly from
the Silver files in storage and writes the result as a new set of files, which then *act like* a table
when you query them. That's why it's called an "external" table — the data physically lives in your
storage account, Synapse just keeps a pointer/description of it.

### The "suppressed number" problem
NHS deliberately hides very small numbers in some columns by writing a dash (`-`) or asterisk (`*`)
instead of a number, to protect patient privacy (a count of "2" patients with something rare could
identify someone). This is a real, intentional NHS convention — but it means a column that's
*supposed* to be numbers also contains some text values, so Power BI reads the **whole column as
text**, and a simple `SUM()` stops working (it just counts rows instead of adding numbers).

**The fix:** instead of trying to force the column into a number type (which turns every suppressed
row into a visible "Error"), we wrote DAX measures that go row-by-row, try to convert each value to a
number, and quietly treat anything that fails (the dashes/asterisks) as zero or blank instead of
crashing:
```
SUMX(table, IFERROR(VALUE(table[col]), 0))
```

---

## 6. Part 4 — The Batch Power BI Dashboard

One single dashboard page, connected live to the 11 Gold tables via **DirectQuery** (meaning: every
time you interact with it, it asks Synapse for the current data — it's not a saved snapshot).

What's on it, and why:
- **Headline KPI cards** — total attendances, % seen within 4 hours, 12+ hour waits, etc.
- **A 3-year trend line** — showing performance has been flat around 70–78%, well under the 95%
  national target the whole time.
- **A trust-by-trust comparison chart, colour-coded Red/Amber/Green (RAG)** — just like real NHS
  performance reporting. We used genuine NHS brand colours (blue `#005EB8`, green `#009639`, red
  `#DA291C`, amber `#FFB81C`) instead of Power BI's defaults, so it reads as an authentic NHS report.
  We also had to filter out tiny minor-injury units that trivially hit 100% (because they only see a
  handful of easy cases a day) — without that filter, the comparison was meaningless.
- **A demographic breakdown** — showing working-age adults (25–64), not the elderly, are actually the
  biggest share of A&E demand.

A recurring small bug worth remembering: dragging a date field onto a chart axis in Power BI
automatically expands it into a Year/Quarter/Month/Day hierarchy. You have to click the field's
dropdown and pick the plain field name instead, or the chart shows the wrong granularity.

---

## 7. Part 5 — Automating the batch pipeline with Data Factory

We built a pipeline called **`Gold_Refresh_Pipeline`** (later shown as `Batch_Pipeline`) so refreshing
all the data is one click instead of manually re-running notebooks and SQL scripts every time:

1. **Run_Bronze_Ingestion** (Databricks notebook activity) — re-reads source files into Bronze.
2. **Run_Silver_Transformation** (Databricks notebook activity) — cleans Bronze into Silver.
3. **Clear_Gold_Container** (Delete activity) — empties the `gold` storage folder, so old data doesn't
   linger if a table's shape changes.

### A real permissions problem we hit and fixed
Data Factory needs its own identity (a "managed identity," basically an automatic robot login Azure
gives it) to be allowed to talk to Synapse. By default, Synapse has no idea who that identity is. We
had to explicitly tell Synapse about it:
```sql
CREATE USER [yamini-project-adf] FROM EXTERNAL PROVIDER;
ALTER ROLE db_owner ADD MEMBER [yamini-project-adf];
```
Run once, inside the `gold_db` database specifically (not `master`) — after that, Data Factory's
"Test connection" to Synapse succeeded.

We chose **not** to add an automatic step that rebuilds the Gold tables on a schedule, because rebuilding
an external table means briefly dropping it and recreating it — which would cause a short error in the
dashboard if someone was actively viewing it at that exact moment. Since NHS data only updates monthly
anyway, this is something to do manually/off-hours rather than automate blindly.

---

## 8. Part 6 — Building the real-time streaming side

### Why streaming is fundamentally different
Batch data already exists in files. Streaming data doesn't exist yet — it has to be generated and sent
continuously, and the pipeline has to be ready to catch it at any moment.

### The fake "hospital" — our event producer
Since we don't have access to a real live hospital feed, we wrote a Python script
(`ae_event_producer.py`) that pretends to be one: every few seconds, it invents a believable fake A&E
event (a random hospital, random age band, random outcome, etc., weighted to look statistically
realistic) and sends it to Event Hub. This runs on your own laptop, in a terminal, and has to be left
running for there to be anything for the rest of the pipeline to process.

### The Kafka dead-end (a real wall we hit)
The "normal" way Databricks reads from Event Hub uses a protocol called **Kafka**. We discovered our
Event Hub was on the cheapest "Basic" pricing tier, which **does not support Kafka at all** — every
attempt failed with the same error no matter what we fixed in the code. There was no setting to
upgrade this within the Basic tier; it's a hard limitation, not a misconfiguration.

**The workaround:** instead of Kafka, we used the plain `azure-eventhub` Python library directly
inside a Databricks notebook — it listens for a short burst (20 seconds × 6 rounds, so about 2
minutes), collects whatever events arrived, and writes them to Bronze. It's not as elegant as a true
continuous stream, but it works reliably within the constraints we had.

### Bronze vs Silver — two different "types" of processing
- **Bronze** (`04_bronze_streaming_ingestion.py`) — runs for ~2 minutes, captures whatever came in,
  then stops. A bounded, one-off job.
- **Silver** (`05_silver_streaming_transformation.py`) — uses genuine **Spark Structured Streaming**
  (a real streaming engine), which cleans timestamps and removes duplicate events (Event Hub can
  occasionally redeliver the same message twice).

  Originally, Silver was written to run **forever** once started — fine for a single manual test, but
  a real problem the moment we wanted Data Factory to trigger it on a schedule, because each scheduled
  run would start *another* never-ending job, stacking up endlessly in the background. We fixed this by
  adding `.trigger(availableNow=True)` plus `.awaitTermination()` — this tells Spark "process whatever
  is currently new, then stop," making it behave like a normal, bounded job that's safe to call
  repeatedly.

### The Gold table for streaming — `live_ae_events`
Built the same way as the batch Gold tables (CETAS), pointing at the Silver streaming data. Important
detail to remember: because this is a CETAS **external table** (per your senior's explicit instruction,
not a view), it is a **frozen snapshot** — it does not automatically update just because new events
flow into Silver. To bring it up to date, you have to manually re-run the `DROP EXTERNAL TABLE` +
`CREATE EXTERNAL TABLE` script again. We also hit a real issue where the table's *metadata* had been
lost but the *old files* from the first creation were still sitting in storage, blocking a fresh
`CREATE` — the fix was deleting the old files in Storage Browser first, then recreating.

---

## 9. Part 7 — The Streaming Power BI Dashboard

A single page, connected to just the one `live_ae_events` table:

- **"Latest Event Time" card** — the most important number on the page; proves the feed is genuinely
  live data, not a stale copy (as long as Gold has actually been refreshed recently).
- **Recent Events table** — raw rows, sorted newest-first.
- **Disposition breakdown, colour-coded** — Discharged (blue), Admitted (green), **Left before
  treatment (red)** — deliberately highlighted because in a real hospital, a rising number of patients
  leaving before being seen is a genuine safety warning sign worth catching immediately, not next
  month.
- **Attendance type breakdown** (pie chart) and **Events over time** (line chart) — visual proof of
  live volume and category mix.
- **Slicers** for `org_name` and `disposition` — let you narrow the whole page down to one hospital or
  one outcome type interactively.

---

## 10. Part 8 — Automating the streaming pipeline with Data Factory

Pipeline name: **`Streaming_Pipeline`**, with two steps:
1. **Run_Streaming_Bronze** — runs the 2-minute capture burst.
2. **Run_Streaming_Silver** — runs the now-bounded Silver cleaning step.

We tested this with **Debug** and it succeeded end-to-end. We also discussed adding a **schedule
trigger** so this runs automatically every 10 minutes without manual clicking — but flagged an honest
trade-off: since you still have to manually run the producer script yourself anyway, a trigger doesn't
remove all the manual work, and it costs real compute money every time it fires (even if it captures
zero events because the producer happened to be stopped). It's the architecturally "correct" pattern
for how this would run in real production with a genuine live feed, but for day-to-day demoing, running
it manually via Debug is equally valid and easier to control.

---

## 11. Part 9 — The presentation materials we created

To go along with the technical build, we created:
1. **`NHS_AE_Dashboard_Presentation.md`** — a spoken script for presenting the batch dashboard, built
   around the rule: *lead with the business finding, not a description of the chart*. Structured as
   Opening hook → 3 Findings (each with an explicit "so what") → Recommendations → a concrete Ask →
   a section on limitations to mention proactively if asked.
2. **`NHS_AE_Streaming_Dashboard_Presentation.md`** — the same structure, adapted to the streaming
   story (the contrast being: this shows *right now*, not *history*).
3. **`NHS_Batch_Dashboard_Slides.pptx`** and **`NHS_Streaming_Dashboard_Slides.pptx`** — the same two
   scripts turned into actual PowerPoint decks, with the talking points placed in each slide's Speaker
   Notes so you can present directly from PowerPoint's Presenter View.
4. **`NHS_Project_Overview_Slides.pptx`** — a separate, broader deck covering the *whole project*
   (architecture, tech stack, engineering challenges solved, automation, roadmap) rather than just the
   dashboard findings — useful for explaining the project itself to someone like a manager or trainer,
   as opposed to presenting dashboard insights to a business audience.

---

## 12. Key lessons worth remembering

- **Never resave a pipeline's source CSV in Excel** — it can silently corrupt date formatting without
  any visible warning.
- **NHS suppression markers (`-`/`*`) turn numeric columns into text** — handle this in DAX measures
  with `IFERROR(VALUE(...), 0)`, don't try to force-convert the column type.
- **CETAS/external tables are snapshots, not live views** — they only update when you manually rerun
  the create script. If you want genuinely always-fresh data with zero rebuild downtime, a SQL `VIEW`
  is the alternative — but views recompute on every query rather than reading pre-built files, so it's
  a real tradeoff between freshness and query speed.
- **Event Hub Basic tier cannot do Kafka** — this is a hard pricing-tier limitation, not a bug to debug
  around.
- **Spark Structured Streaming jobs run forever by default** — if you want Data Factory (or anything
  schedule-based) to trigger one repeatedly, use `trigger(availableNow=True)` so each run is bounded.
- **Data Factory's managed identity needs to be explicitly granted access inside Synapse** — it doesn't
  inherit your own personal permissions automatically.
- **Power BI's date hierarchy auto-expand** is a recurring annoyance — always check the field dropdown
  for the plain field name if you want a single continuous axis.
