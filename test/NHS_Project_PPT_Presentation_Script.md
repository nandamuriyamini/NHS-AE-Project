# NHS A&E Data Engineering Project — Full Presentation Script

Written as a spoken script for presenting to your senior. Every slide is covered in the order
it appears in the deck. Stage directions are in *(italics)*.

---

## BEFORE YOU BEGIN

*(Arrive early. Have the PowerPoint open on your laptop in Presenter View so you can see your
notes. Have the Power BI dashboards open in a browser tab, ready to switch to for the demo
section. Take a breath before you start — you built this from scratch and you know it better
than anyone in the room.)*

---

## SLIDE 1 — Title

*(Click to the first slide. Pause for 3 seconds before speaking. Let them read the title.)*

"Thank you for making time for this. What I'm going to walk you through today is a data
engineering platform I've built on Azure — end to end — using real NHS England A&E statistics.

The platform covers three years of data, from April 2023 to March 2026. It tracks 215 NHS
hospital trusts across every region in England. And it does two separate things: it processes
historical batch data for trend analysis, and it processes live streaming events for real-time
monitoring.

Everything you're going to see today — the pipelines, the dashboards, the automation, the
alerting — was built from the ground up on Azure. I'll take you through the architecture, the
decisions I made, the problems I hit and how I fixed them, and what the data actually tells us
about A&E performance."

*(Click to slide 2.)*

---

## SLIDE 2 — Contents

*(Don't read the list out loud — they can read. Just briefly orient them.)*

"Here's what we'll cover. I'll start with the business problem — why this project exists. Then
I'll walk through the architecture, both pipelines, the Gold layer, the Azure services, the
engineering challenges, and the dashboards. We'll finish with outcomes.

If at any point you want to stop and ask a question or go deeper on something, please do.
This is your time."

*(Click to slide 3.)*

---

## SLIDE 3 — Business Problem & Solution

*(This is the most important slide in the deck. Slow down here.)*

"Before I show you any architecture, I want to explain why this project exists — because the
technical choices only make sense once you understand the problem.

*(Point to the left panel — red header 'THE PROBLEM'.)*

The NHS has one core promise for A&E: be seen, assessed and treated within 4 hours. The target
is that 95% of patients should meet that standard. That's not a stretch goal — it's the legal
and operational benchmark the whole system is measured against.

*(Pause.)*

The data shows that target has not been met. Not once in three years. Not a single month.
The national average sits around 73 to 77 percent — 17 to 22 percentage points below where
it needs to be.

More than one in four patients — 26.7% — is waiting longer than 4 hours. That's five times
the acceptable level.

And the situation isn't static. While the 4-hour breach rate has stayed flat — which is itself
concerning — the number of patients waiting 12 hours or more is actively getting worse. By
early 2026, nearly 80,000 patients waited 12 hours in a single month. That's not in the
headline statistics. It's hidden inside the data.

*(Point to the right panel — green header 'THE SOLUTION'.)*

So the question this project answers is: how do you take three years of NHS data, across 215
trusts, across every region in England, and turn it into something a senior team can actually
act on?

The answer is: an automated Azure data platform that processes raw NHS files, cleans and
aggregates them, and surfaces the story in two Power BI dashboards — one for historical
analysis, one for live operational monitoring.

That's what I built. And I'll show you how."

*(Click to slide 4.)*

---

## SLIDE 4 — Solution Architecture

*(This is the 'map' slide. Don't go deep yet — just orient them.)*

"This is the overall architecture. Two pipelines, running in parallel, each following the same
fundamental pattern.

*(Trace the top row — batch pipeline.)*

The batch pipeline takes NHS CSV files, moves them through Azure Data Factory into Databricks
for cleaning, and ends up in Synapse where the final aggregated tables live — which Power BI
reads directly.

*(Trace the bottom row — streaming pipeline.)*

The streaming pipeline is different. Instead of files, it ingests live events from Azure Event
Hub — a continuous feed of A&E activity — processes them through Databricks, and feeds a live
dashboard.

*(Point to the supporting services row.)*

Underneath both pipelines sit the shared services: ADLS Gen2 for storage, Key Vault for secrets,
Unity Catalog for data governance, Logic Apps for failure alerting, and the ADF linked services
that wire everything together.

I'll go through each component in detail as we move through the slides."

*(Click to slide 5.)*

---

## SLIDE 5 — Medallion Architecture

*(This slide explains the 'why' behind the three-layer design.)*

"The architecture follows what's called a Medallion pattern — three layers, each with a single
job.

*(Point to Bronze.)*

Bronze is the raw layer. When NHS data arrives, we copy it exactly as-is into Delta format.
Nothing is changed, nothing is cleaned. If something goes wrong downstream, Bronze is always
there as the source of truth — we can rebuild Silver and Gold from it at any time.

The original NHS column headers have spaces, colons, parentheses in them — things SQL doesn't
normally allow. We enabled Delta's column mapping mode so we could store the raw headers
without renaming anything at this stage.

*(Point to Silver.)*

Silver is the clean layer. This is where Databricks does its work: standardising column names
into snake_case, converting text dates into real date types, removing duplicate rows, handling
the NHS suppression markers — the dashes and asterisks NHS uses to hide very small numbers
for patient privacy.

*(Point to Gold.)*

Gold is the business layer. This is what Power BI actually reads. It's where all the real
aggregation happens — SUMs, AVGs, RANKs, LAG window functions. Eight tables, each designed to
answer a specific business question.

The reason we separate these three layers is isolation. If the Gold logic changes, we rebuild
Gold from Silver — we don't touch Bronze. If the Silver cleaning logic changes, we rebuild
Silver from Bronze. Each layer is independently repairable."

*(Click to slide 6.)*

---

## SLIDE 6 — Batch Pipeline

*(Now go into detail. This is where you demonstrate your technical depth.)*

"Let me walk you through the batch pipeline step by step.

*(Point to '1. Source'.)*

The source data is six NHS England datasets — monthly_ae_summary, ae_by_provider,
nel_ytd_growth_rates, ecds_activity, ecds_performance and ecds_supplementary. These are the
real, published NHS statistics. We combined them into clean CSVs from the original Excel
workbooks — important note: NHS publishes these as Excel files and if you open and re-save a
CSV in Excel, Excel silently corrupts the dates. We regenerated the CSVs programmatically from
the original workbooks to avoid that.

*(Point to '2. ADF Triggers'.)*

ADF is the conductor. It doesn't store or process data itself — its only job is to fire the
right things in the right order. It triggers four steps: Bronze ingestion, Silver transformation,
Gold container clearing, and Gold table rebuild.

*(Point to '3. Bronze'.)*

The Bronze notebook reads each CSV and writes it to Delta format in ADLS. All six datasets run
in a loop — one notebook handles all of them. Each table is also registered in Unity Catalog
under the yamini_bronze schema, so it's queryable by name, not just by file path.

*(Point to '4. Silver'.)*

Silver cleans everything up. Column names are standardised. Dates are fixed. Duplicates removed.
All six tables registered in yamini_silver.

*(Point to '5. Gold'.)*

Gold is where Synapse takes over. ADF runs a Script activity that executes eight separate
CREATE EXTERNAL TABLE AS SELECT statements — one per Gold table. Each one reads from Silver,
applies aggregation, and writes Parquet files to ADLS which Synapse then exposes as external
tables for Power BI.

*(Point to the red failure path panel.)*

If anything fails — any step in the pipeline — a failure alert fires automatically. ADF fetches
the Logic App webhook URL from Key Vault, then POSTs the failure details to the Logic App, which
sends an email with the pipeline name, error message and run ID. You'd know within seconds if
something went wrong, not the next morning."

*(Click to slide 7.)*

---

## SLIDE 7 — Streaming Pipeline

*(This slide demonstrates the more advanced, real-time capability.)*

"The streaming pipeline is architecturally different from batch, because the data doesn't exist
yet when the pipeline runs — it has to be created and captured continuously.

*(Point to '1. Producer'.)*

Since we don't have access to a real live hospital feed, I wrote a Python script that simulates
one. It generates realistic synthetic A&E events — random hospital trust, random patient age
band, random attendance type and disposition — weighted to match realistic NHS statistics. It
sends these to Event Hub every few seconds.

*(Point to '2. Event Hub'.)*

Azure Event Hub is the mailbox. It receives messages and holds them briefly until something
reads them. One thing worth flagging here: we're on the Basic pricing tier, which does NOT
support Kafka — the standard protocol Databricks uses to read from Event Hub natively.

*(Point to the 'Why not Kafka?' panel.)*

This was a real wall we hit early. Every attempt to use Kafka failed at the tier level — it's
not a bug you can configure around. The workaround was to use the plain azure-eventhub Python
library directly inside Databricks, listening in short bursts rather than a continuous stream.

*(Point to '3. Bronze'.)*

Bronze runs six 20-second listening cycles — about 2 minutes total — capturing whatever events
arrived, and appending them to a Bronze Delta table.

*(Point to '4. Silver'.)*

Silver uses genuine Spark Structured Streaming — reading Bronze as a real stream, deduplicating
by event_id (because Event Hub can occasionally redeliver the same message), and fixing the
timestamp format.

*(Point to the green 'trigger' panel.)*

The critical design decision here was trigger(availableNow=True). Without this, Spark Structured
Streaming runs forever — it just waits for more data indefinitely. That's fine if you run it
manually once, but a disaster the moment ADF tries to call it on a schedule, because each
trigger would start another never-ending background job stacking up. availableNow=True tells
Spark: process what's currently there, then stop cleanly.

*(Point to '5. Gold + BI'.)*

The Gold table for streaming is a Synapse external table called live_ae_events — it's a frozen
snapshot that has to be manually rebuilt. The streaming dashboard reads from this."

*(Click to slide 8.)*

---

## SLIDE 8 — Gold Layer — 8 Tables

*(This slide is about business value. Lead with the 'why' before the 'what'.)*

"The Gold layer was redesigned partway through this project following your feedback that the
original version — which had 11 tables — mostly just renamed columns without calculating
anything new. You were right. The whole point of a Gold layer is to turn clean data into
numbers a business audience can act on directly.

So I replaced all 11 with 8 tables, each one designed around a specific question.

*(Walk through the left column top to bottom.)*

national_monthly_trend answers: what did the whole NHS look like each month?

national_yearly_trend answers: how has performance changed year on year, and what share of
patients breached the target each year?

trust_performance_ranking answers: who are the best and worst performers right now, and are
they getting better or worse compared to last period? This uses RANK() to order every trust for
every time period, and LAG() to calculate period-over-period change.

regional_summary answers: which parts of England are under the most pressure?

*(Walk through the right column.)*

nel_ytd_growth_rates answers: which trusts are seeing emergency admission growth faster than
their regional average — a leading indicator of future A&E strain.

ecds_demographic_summary consolidates five separate breakdowns — age, gender, ethnicity, chief
complaint and frailty — into one table. Previously these were five separate tables with no
aggregation. Now it's one table with SUM and AVG per category.

ecds_org_summary gives a lifetime performance view per organisation, across all available
reporting periods.

ecds_performance shows the spread of performance per metric — average, minimum and maximum
across all organisations — so you can immediately see the gap between best and worst.

*(Point to the note at the bottom.)*

Every one of these is a CETAS — Create External Table As Select — which means ADF runs the
SQL in a Synapse Script activity, Synapse reads Silver, aggregates, and writes Parquet files
to ADLS. Power BI reads those files directly via DirectQuery."

*(Click to slide 9.)*

---

## SLIDE 9 — Azure Services

*(This is a reference slide. Don't rush it — show you understand each service's specific role.)*

"Seven Azure services, each with exactly one job.

*(Point to each row as you speak.)*

Azure Data Factory is the conductor. It doesn't touch data — it triggers things in the right
order and handles the failure notification chain.

ADLS Gen2 is the filing cabinet. Everything lives here: raw CSVs, Bronze Delta tables, Silver
Delta tables, Gold Parquet files — four separate containers.

Databricks is the processing engine. All the Python and Spark code runs here — Bronze
ingestion, Silver cleaning, and the Gold container clearing notebook.

Synapse Analytics is the SQL reporting layer. Serverless SQL pool, database called gold_db.
This is where the eight CETAS external tables live, queryable directly by Power BI.

Azure Event Hubs is the streaming mailbox. It receives events from the producer script and
holds them until Databricks reads them.

Key Vault is the lockbox. Every credential in this project — the storage account key, the
Event Hub connection string, the Logic App webhook URL — is stored here. Nothing is hardcoded
anywhere in the code or the pipeline.

Logic Apps is the alerting layer. When any pipeline activity fails, ADF posts to a Logic App
which sends an email via SMTP through our Rackspace mail server."

*(Click to slide 10.)*

---

## SLIDE 10 — Engineering Challenges

*(This slide shows maturity — you can talk about what went wrong, not just what went right.
This often impresses seniors more than the successes.)*

"This slide is about the real problems we hit during the build — not theoretical edge cases,
but actual things that broke and had to be fixed.

*(Point to Excel Date Corruption.)*

The first challenge was data corruption we didn't cause. When NHS exports their data to CSV
and someone opens and re-saves the file in Excel, Excel silently reformats date fields. 'October
2025' becomes '10-01-25' — it looks fine on screen but breaks downstream parsing completely.
The fix was to regenerate the CSVs directly from the original Excel workbooks using Python,
never opening the source files in Excel ourselves.

*(Point to NHS Suppression Markers.)*

NHS deliberately inserts a dash or asterisk in cells where the count is too small — to protect
patient privacy. That means a column that should contain numbers also contains text, so the
whole column gets inferred as VARCHAR. Any SQL that tries to SUM or AVG it fails with a type
error. The fix was TRY_CAST in Synapse — try to convert to a number, and if it fails, return
null instead of crashing.

*(Point to ADF Delete Removed Container.)*

This one cost us the most time. ADF has a Delete activity that can recursively delete files.
When we pointed it at the root of the gold container to clear old data before rebuilding, it
deleted the entire container — not just the files inside it. This happened twice before we
identified the root cause. ADLS Gen2's hierarchical namespace treats a recursive delete from
the root as a filesystem delete, not a blob delete. The fix was to replace the Delete activity
with a Databricks notebook that calls dbutils.fs.rm on each named table folder individually —
never touching the root.

*(Point to GO Syntax.)*

ADF's Script activity sends SQL directly to the Synapse engine. GO is a client-tool batch
separator — SSMS uses it, Synapse Studio uses it — but the actual SQL engine doesn't recognise
it. Every GO in the script caused a syntax error. The fix was to split the script into nine
separate query blocks: one for all the DROP statements, and eight individual CREATE EXTERNAL
TABLE blocks.

*(Point to Event Hub Basic / No Kafka.)*

Event Hub Basic tier simply doesn't support Kafka. This is a hard pricing-tier limitation —
there's no setting to enable it. The fix was to use the azure-eventhub Python SDK directly,
polling in manual bursts rather than using a native streaming connector.

*(Point to Two Separate SAS Credentials.)*

Synapse uses database-scoped credentials to access ADLS. We had two: StorageSAS for the Silver
source data, and GoldStorageCredential for writing Gold files. When the SAS token expired —
which happened several times — updating only one credential didn't fix the error. Both had to
be updated separately with a fresh SAS token that included Create and Write permissions, not
just Read."

*(Click to slide 11.)*

---

## SLIDE 11 — Power BI Dashboards

*(If you have Power BI open in a browser, this is the moment to switch to it for a live demo.)*

"The dashboards are where the data engineering investment pays off — this is what the business
audience actually sees.

*(If showing live: switch to Power BI now.)*

There are two dashboards.

*(Point to or open the Batch Dashboard.)*

The batch dashboard covers historical performance across the full three-year period. It has two
pages. Page one is the executive summary: five KPI cards at the top — 33 million attendances,
215 trusts, 26.7% breach rate, average trust improvement, and one million 12-hour waits, that
last one deliberately in red.

Below the cards is a dual-line trend chart. The blue line is the percentage seen within 4 hours.
The red line is the 12-hour wait count. The red dashed line is the 95% target. You can see
immediately that the blue line has never touched the target, and the red 12-hour line is rising.

The Trust Bottom 10 bar chart shows the worst-performing trusts using RAG colours — all red,
all below 70%.

Page two shows the regional picture and the demographic breakdown. Working-age adults, not the
elderly, are the largest group using A&E — that's counterintuitive and directly relevant to
workforce and capacity planning decisions.

There's also a Trust Biggest Improvers chart — trusts that have genuinely moved their
performance period-over-period. These are the case studies for what recovery looks like and
where learning should be shared.

*(If showing live: switch to the Streaming Dashboard.)*

The streaming dashboard shows what's happening right now. The Latest Event Time card proves
the data is live. The disposition breakdown shows in real time how patients are leaving — and
Left Before Treatment is highlighted in red because in an operational setting, that number
rising during a shift is a genuine patient safety signal worth catching immediately."

*(Click to slide 12.)*

---

## SLIDE 12 — Project Outcomes

*(This is your closing argument before the Thank You. Speak confidently — you earned this.)*

"To close on the technical side: here is what was delivered and confirmed working.

Automated Azure Pipeline — both pipelines run end-to-end with one click.

Medallion Architecture — correctly implemented across all six batch datasets and the streaming
source.

Unity Catalog — fourteen managed tables registered across the yamini_bronze and yamini_silver
schemas.

Eight-table Gold layer — every table with genuine aggregation, not just renamed columns.

Failure alert system — Logic App emails on any pipeline failure, tested and working.

Two Power BI dashboards — NHS branded, interactive, DirectQuery connected.

External tables in ADF — the Script activity runs all eight CETAS statements as part of the
orchestrated pipeline.

Key Vault security — zero hardcoded credentials anywhere in the codebase or the pipeline.

*(Pause briefly before the final line.)*

Everything on that list was built, tested and confirmed working — not just documented as
planned."

*(Click to slide 13.)*

---

## SLIDE 13 — Thank You

*(Put the clicker down. Make eye contact. Don't rush this.)*

"Thank you for your time.

I'm happy to answer questions on any part of what you've seen — the architecture decisions,
the engineering challenges, the business findings in the data, or the implementation of any
of the specific requirements.

*(Leave a natural pause — invite questions rather than filling the silence.)*"

---

## COMMON QUESTIONS — AND HOW TO ANSWER THEM

**Q: Why didn't you use Kafka for streaming?**
"The Event Hub namespace is on the Basic pricing tier, which doesn't support Kafka — it's a
hard Azure limitation, not something you can configure around. We used the azure-eventhub
Python SDK as a workaround, polling in short bursts inside Databricks."

**Q: Why Databricks for Bronze and Silver instead of doing it all in ADF?**
"ADF is an orchestrator — it's designed to trigger things, not transform data. Databricks gives
us a full Python and Spark environment for complex transformations: column name standardisation
with hashing for long names, ANSI mode handling, suppression marker logic. ADF's data flows
couldn't handle that level of custom logic cleanly."

**Q: Why Synapse for Gold instead of keeping it in Databricks?**
"Synapse Serverless SQL is the natural connection point for Power BI — DirectQuery from Power
BI to Synapse is well-supported, low-latency, and doesn't require a Databricks cluster to be
running. For read-only reporting, Synapse is the right tool."

**Q: Why external tables instead of views in Synapse?**
"External tables write the result physically to ADLS as Parquet files. Power BI reads those
pre-built files rather than re-running the aggregation SQL on every dashboard load. That's
much faster for users. The trade-off is that they're a snapshot — they only update when the
pipeline reruns. Views would always be fresh but slower."

**Q: Why did you choose managed tables for Unity Catalog instead of external?**
"This training workspace doesn't have a Storage Credential or External Location registered for
the yaminiprojectadls storage account — which Unity Catalog requires before it will register
external tables pointing at arbitrary ADLS paths. Managed tables don't have that requirement,
so they were the practical way to satisfy the Unity Catalog requirement within the environment's
constraints."

**Q: What would you do differently if you were doing this in production?**
"Three things: first, I'd use Event Hub Standard tier to enable native Kafka connectivity —
the polling workaround works but isn't production-grade. Second, I'd put the Gold rebuild on
a scheduled ADF trigger rather than manual execution, with a maintenance window off-hours so
it doesn't briefly break the dashboard for anyone viewing it at that moment. Third, I'd add
Great Expectations or a similar data quality framework between Bronze and Silver to catch
upstream data issues — like the Excel date corruption problem — before they propagate."
