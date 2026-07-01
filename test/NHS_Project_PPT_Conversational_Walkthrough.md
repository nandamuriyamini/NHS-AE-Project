# NHS A&E Data Engineering Project — Conversational PPT Walkthrough

Written in a natural spoken style — similar to how you'd walk through it slide by slide
when presenting to a client or senior. Not a formal script — more like how you'd actually
explain it in the room.

---

## SLIDE 1 — Title Slide

So, I'm going to present my NHS A&E Data Engineering project, which demonstrates an
end-to-end data engineering pipeline built on Azure. This is built using Azure Data Factory,
Databricks, Synapse Analytics, Power BI, Event Hubs, and Key Vault, and it follows a
Medallion architecture approach — that is Bronze, Silver, Gold — which makes the data ready
for reporting tools like Power BI.

So the objective of this project is, yeah, extracting the real NHS England A&E statistics,
transforming them using Databricks, loading them into Synapse, and orchestrating everything
using Azure Data Factory. And then we have two dashboards in Power BI — one for batch
historical analysis and one for live streaming. I'll walk through the architecture, show
the transformations, the orchestration, and the final data model.

---

## SLIDE 2 — Contents

So here I have the contents of what I'm going to cover. I'll start with the business problem,
then the architecture, then go through each pipeline — batch and streaming — then the Gold
layer tables, the Azure services, the engineering challenges, and finally the dashboards.
So let me start from the beginning.

---

## SLIDE 3 — Business Problem and Solution

So before going into any architecture, let me explain why this project exists and what
problem it is solving.

So the NHS has a target — 95% of patients who walk into an A&E department should be seen,
treated and either admitted or discharged within 4 hours. That's the national standard.

But what the data shows is that this target has not been met. Not once in three years. The
actual national performance is sitting around 73–77%. That's almost 20 percentage points
below where it should be.

And it's not just the 4-hour wait. More than 1 million patients waited over 12 hours in this
3-year period. That number is actually getting worse over time. And this is hidden inside the
data — it doesn't come up in most headline reporting.

So the problem is — NHS England has 215 hospital trusts across the whole country, and they
need a way to compare all of them, see who is struggling, understand why, and take action.
Before this, the only option was downloading Excel files every month and doing manual analysis.

So that's where this project comes in. This pipeline takes all the raw NHS data, cleans it,
aggregates it, and puts it into a dashboard that shows the performance of all 215 trusts at
once. And on top of that, we have a live streaming dashboard that shows what's happening
right now in A&E — not what happened last month.

So that's the business problem. Now let me show you how I built the solution.

---

## SLIDE 4 — Solution Architecture

So here is the overall architecture. I have two pipelines running side by side.

The first one is the batch pipeline. This starts with NHS CSV files in the raw storage layer.
ADF — Azure Data Factory — acts as the orchestration layer, so it's responsible for triggering
everything in the right order. It triggers the Databricks notebooks, which take the data through
Bronze and Silver layers, and then it triggers a Synapse Script activity that builds the Gold
layer. Power BI then connects to Synapse and shows the final dashboard.

The second one is the streaming pipeline. Here, instead of files, we have a producer script
that generates synthetic A&E events and sends them to Azure Event Hub. Event Hub acts like
a message broker — it holds the messages until Databricks reads them. Databricks then processes
the events through Bronze and Silver, and the final live dashboard connects to a Synapse table
that gets updated each time the pipeline runs.

And underneath both pipelines, we have the supporting services — ADLS Gen2 for storage, Key
Vault for secrets, Unity Catalog for data governance, and Logic Apps for failure alerting.

---

## SLIDE 5 — Medallion Architecture

So the architecture follows the Medallion approach — Bronze, Silver, Gold — three layers,
each with a very specific job.

So coming to the Bronze layer. The Bronze layer is nothing but a raw copy of the source data.
We take the NHS files and write them exactly as they are into Delta format in ADLS. We don't
change anything. We just add two tracking columns — source file and ingested timestamp — so
we always know where a row came from and when it arrived. And we register these tables in
Unity Catalog under the yamini_bronze schema.

Coming to the Silver layer. This is where Databricks performs all the transformations. Here I
have implemented things like renaming the columns into a standard snake_case format, converting
the date columns from text into actual DATE types using TRY_CAST, removing duplicate rows, and
handling the NHS suppression markers — those are the dashes and asterisks NHS puts in small
cells for patient privacy. And once this is done, the tables are registered in yamini_silver
schema.

Coming to the Gold layer. Here the data is ready for business reporting. This is where Synapse
runs the aggregations — SUM, AVG, RANK, LAG window functions — and creates 8 external tables
that Power BI reads directly. So the Gold layer is the output of the entire pipeline.

The reason we have three separate layers is isolation. If something changes in Gold logic, we
just rebuild Gold from Silver. We don't touch Bronze. So each layer is independently repairable.

---

## SLIDE 6 — Batch Pipeline

So coming to the batch pipeline in detail. Let me walk through each step.

So the pipeline starts with the 6 NHS datasets — monthly_ae_summary, ae_by_provider,
nel_ytd_growth_rates, ecds_activity, ecds_performance, and ecds_supplementary. These are
real, publicly published NHS England statistics.

Then ADF is responsible for orchestrating the workflow. In ADF, it manages the task execution,
dependencies, retries, and scheduling. So once I trigger the pipeline — either manually or on
a schedule — ADF fires each step in the right order.

Once the raw data is ingested into Bronze, Databricks performs all the transformations —
cleaning the data, standardising the business logic, creating the Silver models. And once
Silver is ready, a Synapse Script activity runs and creates all 8 Gold tables.

So here one more important thing — before building the Gold tables, we have a Databricks
notebook called Clear_Gold_Tables that deletes the old Gold files first. The reason for this
is that in Synapse, when you drop an external table, it only removes the catalog entry —
not the actual files. So if the old files are still there, the CREATE will fail with a
"location already exists" error. So we clear the files first, then rebuild.

And then coming to the failure path. I have added failure alerts using Logic Apps. So if any
activity fails — Bronze, Silver, or Gold — ADF automatically fetches the Logic App URL from
Key Vault and sends a POST request, which triggers an email notification with the pipeline
name, the error message, and the run ID. This is done using a Web Activity chain — one to
get the URL from Key Vault, and one to call the Logic App.

---

## SLIDE 7 — Streaming Pipeline

So coming to the streaming pipeline. Here the approach is different because the data doesn't
exist yet when the pipeline runs — it arrives continuously in real time.

So the pipeline starts with the event producer. I wrote a Python script called
ae_event_producer.py that simulates a live hospital A&E feed — it generates random synthetic
events with trust name, age band, attendance type, and disposition, and sends them to Azure
Event Hub every few seconds.

Coming to Event Hub. Event Hub is like the live mailbox — it holds the messages until
Databricks reads them. Now here, one important thing. The Event Hub namespace is on the Basic
pricing tier, which does not support Kafka. Kafka is the standard protocol that Databricks
uses to read from Event Hub. So I couldn't use the native connector.

So the workaround I implemented was using the plain azure-eventhub Python SDK directly inside
Databricks. It listens in 6 cycles of 20 seconds each — about 2 minutes total — captures
whatever events arrived, and appends them to the Bronze Delta table.

Coming to Silver. Here I used genuine Spark Structured Streaming. So the Silver notebook reads
from Bronze as a real stream using readStream, converts the arrival_time from text to a proper
timestamp, and uses dropDuplicates on event_id to handle cases where Event Hub redelivers
the same message twice.

One critical thing here — I implemented trigger(availableNow=True). Without this, Spark
Structured Streaming runs forever — it just waits for new data continuously. That's fine for
a manual one-off run, but when ADF tries to trigger this notebook on a schedule, each trigger
would start another never-ending job. So availableNow=True makes the job process whatever is
currently available and then stop cleanly.

And same as batch — failure notification is also wired into the streaming pipeline.

---

## SLIDE 8 — Gold Layer — 8 Tables

Coming to the Gold layer. So here the data is business-ready. This is where all the real
value is created.

So I have 8 tables in the Gold layer. Let me walk through each one.

national_monthly_trend — this gives the national monthly totals, summing all attendance
types by month. So you can see the national picture month by month.

national_yearly_trend — this rolls it up further to yearly, and adds a calculated percentage
of breaches per year. So this is what board-level reporting looks at.

trust_performance_ranking — this is the most analytical one. For every trust, every period,
I calculate a RANK using RANK() window function, ordering by 4-hour performance. And I also
calculate the period-over-period change using LAG() — so you can see not just who is
performing well today, but whether they are getting better or worse over time.

regional_summary — this groups all trusts by NHS region, giving SUM, AVG, and trust count
per region. So you can see which part of England has the most pressure.

nel_ytd_growth_rates — this is the year-to-date non-elective growth rates, with an added
regional benchmark using AVG OVER PARTITION BY region. So you can see if a trust's emergency
admissions are growing faster than their neighbours.

ecds_demographic_summary — this consolidates the five demographic breakdowns — age, gender,
ethnicity, chief complaint, and frailty — into one table with proper aggregation. So instead
of having five separate tables with no aggregation, we have one table answering "who is using
A&E?"

ecds_org_summary — per-organisation totals across all available periods.

ecds_performance — average, minimum, and maximum per metric across all organisations. This
shows the spread between the best and worst performers for each metric.

All of these are built using CETAS — Create External Table As Select — in Synapse Serverless
SQL, run by an ADF Script activity. So on every pipeline run, ADF drops the old tables and
recreates them with fresh data.

---

## SLIDE 9 — Azure Services

So coming to the Azure services. I have 7 services in this project and each one has a very
specific, non-overlapping role.

Azure Data Factory — this is the orchestration layer. It doesn't touch data. Its only job is
to trigger the right things in the right order.

ADLS Gen2 — this is the storage. Everything lives here — raw files, Bronze Delta tables,
Silver Delta tables, Gold Parquet files — in four separate containers.

Databricks — this is the processing engine. All the Python and Spark code runs here —
Bronze ingestion, Silver cleaning, and the Gold container clearing notebook.

Synapse Analytics — this is the SQL reporting layer. The 8 Gold tables live here as external
tables. Power BI reads directly from Synapse using DirectQuery.

Azure Event Hubs — this is the streaming mailbox for the live pipeline. Receives events from
the producer script.

Key Vault — this is the secrets management. The storage account key, the Event Hub connection
string, the Logic App webhook URL — all stored in Key Vault. Nothing is hardcoded anywhere in
the code or pipeline. Databricks reads secrets via a secret scope, and ADF reads them via a
Web Activity REST call at runtime.

Logic Apps — this is the alerting system. When any pipeline activity fails, ADF sends a POST
request to the Logic App, which sends an email via SMTP through the Rackspace mail server.

---

## SLIDE 10 — Engineering Challenges

So coming to the engineering challenges. I want to be honest here — the build wasn't smooth.
There were real problems that had to be solved. And I think this is important to share because
in a real production environment, these are exactly the kind of things you'll face.

First challenge — Excel date corruption. When NHS publishes data as Excel workbooks and
someone opens and re-saves them, Excel silently reformats dates. A date like "October 2025"
becomes "10-01-25". It looks fine on screen but breaks downstream parsing completely. The fix
was to regenerate the CSVs directly from the original Excel workbooks using Python — never
opening the source files in Excel ourselves.

Second challenge — NHS suppression markers. NHS puts a dash or asterisk in cells where the
count is too small, to protect patient privacy. This forces the entire column to be read as
text by Synapse. So any SUM or AVG on those columns fails with a type error. The fix was
TRY_CAST — try to convert to a float, and if it can't, return NULL. SUM and AVG ignore NULLs
automatically.

Third challenge — ADF Delete activity removed the whole container. I was using an ADF Delete
activity to clear old Gold files before rebuilding. When I pointed it at the root of the
gold container with Recursive enabled, it deleted the entire container — not just the files
inside it. This happened twice. ADLS Gen2's hierarchical namespace treats a root-level
recursive delete as a filesystem delete. The fix was to replace the Delete activity with a
Databricks notebook that uses dbutils.fs.rm on each specific named folder — never the root.

Fourth challenge — GO syntax not supported in ADF Script activity. ADF sends SQL directly to
the Synapse engine. GO is a client-tool batch separator — SSMS uses it, but the actual SQL
engine doesn't understand it. So every GO caused a syntax error. The fix was to split the
script into 9 separate query blocks — one DROP block and 8 individual CREATE EXTERNAL TABLE
blocks.

Fifth challenge — Event Hub Basic tier doesn't support Kafka. This is a hard Azure limitation,
not a bug you can configure around. The fix was to use the azure-eventhub Python SDK directly
with manual polling bursts inside Databricks.

Sixth challenge — two separate SAS credentials in Synapse. Synapse had two credential objects
— StorageSAS for reading Silver, and GoldStorageCredential for writing Gold. When the SAS
token expired, updating only one of them didn't fix the error. Both had to be updated
separately.

---

## SLIDE 11 — Power BI Dashboards

So coming to the Power BI dashboards. I have created two dashboards — one for batch
historical analysis and one for live streaming monitoring.

Coming to the batch dashboard. This has two pages.

Page 1 is the executive summary. At the top, I have 5 KPI cards — 33 million total A&E
attendances, 215 trusts tracked, 26.7% of patients waiting over 4 hours, average trust
improvement of 0.09%, and 1 million patients waiting over 12 hours — that last card is in
red, which is intentional, to draw attention to it.

Below the cards, I have a dual-line trend chart. One line shows the percentage seen within
4 hours over time, and the other line shows the 12-hour wait count. You can immediately see
that the 4-hour performance line is flat — stuck well below the 95% target — while the
12-hour line is rising. The 95% target is shown as a red dashed reference line.

Then I have the Trust Bottom 10 bar chart, which shows the 10 worst-performing hospital trusts
with RAG colouring — Red, Amber, Green — following the same colour standard NHS itself uses.
All 10 bars are red, all below 70%.

Page 2 has the regional and demographic insights. The regional chart shows total A&E volume
per region alongside average performance — so you can see not just which regions are busy,
but whether high volume is also coming with lower performance. And the demographic breakdown
chart shows who is actually using A&E — the finding here is that working-age adults, not the
elderly, are the dominant group.

I also added a Trust Biggest Improvers chart, which shows the trusts that have made the most
period-over-period improvement. This is very useful because it shows recovery is possible and
identifies which trusts should be studied for best-practice sharing.

Coming to the streaming dashboard. This connects to the live_ae_events Gold table. It shows
the latest event time — which proves the data is live — the disposition breakdown, the events
over time trend, and slicers to filter by hospital or disposition type. Left Before Treatment
is highlighted in red because in a real operational setting, patients leaving before being seen
is a patient safety signal.

---

## SLIDE 12 — Project Outcomes

So overall, this project demonstrates a complete end-to-end data engineering pipeline on Azure.

Starting with data ingestion — we downloaded real NHS England A&E statistics and loaded them
into ADLS as the raw layer.

Then transformation — Databricks processed the data through Bronze, Silver, and Gold layers
with proper column standardisation, date fixing, deduplication, and NHS suppression handling.

Then orchestration — Azure Data Factory orchestrates the entire batch and streaming workflows
with scheduling, task dependencies, retry logic, and failure alerting.

Then governance — Unity Catalog manages 14 managed tables across yamini_bronze and
yamini_silver schemas, providing proper metadata and discoverability.

And then reporting — two Power BI dashboards, one historical and one live, both connected
via DirectQuery.

So overall this project gave me practical experience in building a production-style data
engineering pipeline, covering the complete data lifecycle — from ingestion, storage,
transformation, data governance, and all the way to reporting tools.

---

## ANSWERING THE BUSINESS VALUE QUESTION

*(If asked: "How does this benefit the business or the client?")*

So, yeah — by seeing this dashboard, a business or operational team gets several things they
couldn't get before.

First, they can see which hospitals are performing worst, ranked clearly, not buried in a
spreadsheet of 215 rows. And they can see whether those hospitals are getting better or worse
over time — which tells them whether existing interventions are working.

Second, they can see which regions are under the most pressure. So if you're making decisions
about where to invest — new staff, new capacity, new services — this data tells you where it's
needed most, instead of spreading resources equally regardless of demand.

Third, the demographic breakdown shows who is actually using A&E. If you're a streaming
platform like Netflix and you're deciding which content to promote based on audience — or if
you're NHS and you're deciding what staffing model to design — you need to know who your
actual users are, not who you assume they are. The data shows working-age adults are the
dominant A&E group, not the elderly. That changes workforce planning decisions.

Fourth, the streaming dashboard gives operational teams real-time visibility during a shift.
If "left before treatment" numbers start climbing during a Wednesday afternoon, that's a
signal something is wrong — staff are overwhelmed, waits are too long, patients are giving
up. Catching that in real time means there's still time to act. Catching it in next month's
report doesn't.

So this pipeline turns a mountain of government spreadsheets into actionable insight that
a commissioner, a regional NHS manager, or an operational team can use directly — without
needing a data analyst to pull a custom report every time they have a question.
