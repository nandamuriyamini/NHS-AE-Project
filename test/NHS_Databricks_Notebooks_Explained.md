# NHS Databricks Notebooks — Explained in Plain English

This covers every notebook in the `Databricks_Notebooks` folder: what it's for, what it actually
does step by step, and why each transformation exists. Written so you can come back to this in a
few months and immediately remember what each notebook does without re-reading the code.

---

## `00_config.py` — the shared setup notebook

Every other notebook starts with `%run "./00_config"`, which is just Databricks' way of saying
"run this other notebook first, and let me use everything it defines." Think of it as a settings
file every other notebook imports.

**What it does, in order:**
1. Defines a handful of "widgets" — basically configurable text boxes (storage account name,
   container names, Key Vault scope/secret name). Defaults are filled in for this project, but they
   can be overridden without touching code.
2. Reads your storage account's secret key out of Azure Key Vault (via a Databricks secret scope
   linked to it), so the notebook can authenticate to Azure Storage without ever putting a password
   directly in code.
3. Builds the 4 storage paths — one per layer (`raw`, `bronze`, `silver`, `gold`) — since each layer
   lives in its own separate container, not a folder inside one container.
4. Creates two old-style Hive databases (`bronze`, `silver`, `gold`) — leftover from before Unity
   Catalog was added to this project; not actually used for anything important now.
5. Creates two **Unity Catalog schemas** — `adb_training_bd.yamini_bronze` and
   `adb_training_bd.yamini_silver` — this is where the "real" Unity Catalog tables for this project
   now live.
6. Defines the `DATASETS` dictionary — the 6 real NHS files this project works with, mapping a clean
   short name (e.g. `monthly_ae_summary`) to its actual filename in the `raw` container.

---

## `01_bronze_ingestion.py` — Bronze (batch)

**Purpose:** copy the 6 raw NHS CSV files into Delta format, completely untouched. Bronze's whole
point is "a safe, exact copy of what arrived" — no cleaning, no renaming, nothing fixed yet.

**Steps:**
1. Loop through each of the 6 datasets, read the raw CSV (letting Spark guess the column types).
2. Add two extra tracking columns: `_source_file` (which file this row came from) and
   `_ingested_at` (the exact timestamp it was loaded) — so you can always trace a row back to its
   origin.
3. Write it to the `bronze` container as a Delta table. One special setting here —
   `delta.columnMapping.mode = "name"` — is needed because the original NHS column headers contain
   spaces, colons, and parentheses (e.g. "A&E attendances Type 1"), which Delta normally won't allow
   as column names unless this mode is turned on.
4. A quick verification cell reads every Bronze table back and prints its row count.
5. A final cell **registers** each of the 6 Bronze tables in Unity Catalog, as **managed tables**
   under `adb_training_bd.yamini_bronze` — this is what makes them show up and be queryable in
   Catalog Explorer / by anyone with access to that schema, not just something sitting in a storage
   folder. ("Managed" means Databricks owns where the data physically lives — simpler than an
   "external" table, which needs extra permissions this training workspace doesn't have set up.)

---

## `02_silver_transformation.py` — Silver (batch)

**Purpose:** take the raw Bronze copy and actually clean it up into something usable.

**Steps:**
1. **Standardize every column name** — lowercase, spaces/symbols replaced with underscores. NHS's
   original headers are long and inconsistent, so this makes every dataset's columns predictable and
   safe to use in SQL later. Anything over 100 characters gets shortened with a short unique hash
   suffix, since Synapse SQL has a 128-character column name limit.
2. **Fix the date column** — `report_date` gets converted from text into a real date type, using
   `try_cast` instead of a strict cast, so a handful of malformed date values quietly become blank
   instead of crashing the whole job.
3. **Remove exact duplicate rows.**
4. **Dataset-specific cleanup** — for `monthly_ae_summary` specifically, drop the leftover "TOTAL"
   summary row that NHS includes at the bottom of that report (it would otherwise get counted as if
   it were a real hospital).
5. Write the cleaned result to the `silver` container.
6. A schema-printing cell lets you visually check the final, cleaned column names for each table.
7. A final cell **registers** each of the 6 Silver tables in Unity Catalog as managed tables under
   `adb_training_bd.yamini_silver`.

---

## `03_gold_aggregation.py` — Gold (batch, Databricks version)

**Important note:** this notebook is the **original** way Gold tables were built, by aggregating
directly in Spark and saving Delta files straight to the `gold` container. It was later
**superseded** — the actual Gold layer your dashboard uses now lives in **Synapse**, built with SQL
(`CREATE EXTERNAL TABLE ... AS SELECT`, i.e. CETAS) using the redesigned 8-table structure with
proper `SUM`/`RANK`/`LAG`-based aggregations. This notebook is kept as a record of the earlier
approach, not something you need to keep running.

**What it originally did, for reference:**
1. **`national_monthly_trend`** — summed every numeric column in `monthly_ae_summary`, grouped by
   month, to get one national total row per month.
2. **`trust_kpis_monthly` / `trust_kpis_quarterly`** — split `ae_by_provider` into two tables based
   on its `period_type` column, no aggregation, just a filter.
3. **`nel_ytd_growth_rates`** — promoted straight from Silver with no changes (NHS had already
   pre-calculated the growth rates).
4. **`ecds_performance`** — promoted straight from Silver, kept in long format (one row per
   metric), since its underlying sheets measure unrelated things and didn't pivot cleanly into one
   wide table.
5. **The 6 ECDS breakdown tables** (org/age/gender/ethnicity/chief complaint/frailty) — the most
   complex step: each one **merges multiple report variants together**. NHS publishes the same kind
   of breakdown in different "flavours" (Type 1&2 hospitals only, vs UTCs/minor injury units, vs all
   types combined) and across **two non-overlapping time periods** (`ecds_supplementary` covering
   Apr 2023–Sep 2025, then `ecds_activity` covering Oct 2025 onward, as NHS changed which report it
   publishes). This step unions all of those pieces into one continuous ~3-year table per breakdown
   type, tagging each row with `source_report` (which NHS report it came from) and `basis` (which
   hospital-type variant), then pivots the long metric/value rows into a wide table (one column per
   metric).

---

## `04_bronze_streaming_ingestion.py` — Bronze (streaming)

**Purpose:** capture live, synthetic A&E events arriving via Azure Event Hub.

**Why this looks different from batch Bronze:** the training cluster doesn't have the native
Spark/Event Hub connector available, and the Event Hub namespace is on the cheapest "Basic" pricing
tier, which doesn't support the usual Kafka-based streaming protocol at all. So instead of a true
continuous stream, this notebook does a **polling workaround**:

**Steps:**
1. Connect to Event Hub using the plain `azure-eventhub` Python library (not Spark streaming).
2. Listen for a short burst — 20 seconds at a time, repeated 6 times (about 2 minutes total) —
   collecting whatever events arrive in each burst into a buffer.
3. After each burst, convert the buffer into a Spark DataFrame and **append** it to the Bronze
   streaming Delta table.
4. Repeating this notebook run is what simulates "live" behavior — each run picks up new events that
   arrived since the last run.
5. A final cell **registers** the accumulated Bronze stream table in Unity Catalog as
   `adb_training_bd.yamini_bronze.ae_events_stream`.

---

## `05_silver_streaming_transformation.py` — Silver (streaming)

**Purpose:** clean the live event stream using genuine Spark Structured Streaming (a real streaming
engine, unlike Bronze's manual polling workaround).

**Steps:**
1. Read the Bronze stream table as a Spark **streaming** source (`readStream`), not a static read.
2. Convert `arrival_time` from text into a real timestamp.
3. Apply a **watermark** (10 minutes) and **drop duplicate events by `event_id`** — Event Hub can
   occasionally redeliver the same message more than once, so this prevents double-counting the same
   real-world event.
4. Write the result out using `.trigger(availableNow=True)` — this is a key fix: by default, a
   Structured Streaming query runs **forever**, waiting for new data indefinitely. That's fine for a
   one-off manual test, but a real problem if Data Factory is going to trigger this notebook
   repeatedly on a schedule — each run would start *another* never-ending job stacking up in the
   background. `availableNow=True` instead tells Spark "process whatever's currently new, then stop,"
   making the notebook safe to call repeatedly.
5. A final cell **registers** the Silver stream table in Unity Catalog as
   `adb_training_bd.yamini_silver.ae_events_stream`.

---

## Summary table

| Notebook | Layer | Input | Key transformation | Unity Catalog table |
|---|---|---|---|---|
| `00_config` | — | — | shared paths, secrets, schema setup | — |
| `01_bronze_ingestion` | Bronze (batch) | raw CSVs | copy as-is + tracking columns | `yamini_bronze.<6 tables>` |
| `02_silver_transformation` | Silver (batch) | Bronze | clean column names, fix dates, dedupe | `yamini_silver.<6 tables>` |
| `03_gold_aggregation` | Gold (batch, superseded) | Silver | aggregations, merges, pivots | *(now done in Synapse instead)* |
| `04_bronze_streaming_ingestion` | Bronze (streaming) | Event Hub | poll in bursts, append | `yamini_bronze.ae_events_stream` |
| `05_silver_streaming_transformation` | Silver (streaming) | Bronze stream | dedupe, bounded streaming trigger | `yamini_silver.ae_events_stream` |
