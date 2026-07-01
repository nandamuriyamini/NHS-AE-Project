# NHS Batch_Pipeline — Orchestration Explained (Plain English)

This explains exactly what `Batch_Pipeline` in Azure Data Factory does, activity by activity, why
each piece exists, and the real problems we hit building it — written so you can re-read this in a
few months and remember not just *what* it does but *why* it's built this way.

---

## 1. What this pipeline is, in one sentence

`Batch_Pipeline` is the "one click does everything" automation that refreshes the entire batch side
of this project — Bronze, Silver, and Gold — instead of you manually running notebooks and SQL
scripts by hand every time NHS publishes new data.

---

## 2. The full chain, in order

```
Run_Bronze_Ingestion → Run_Silver_Transformation → Clear_Gold_Tables → Gold_Tables
        |                       |                          |              |
        └───────────────────────┴──────────────────────────┴──────────────┘
                                       (any failure)
                                            ↓
                                    Get_Webhook_URL → Notify_Failure
```

Every activity has two possible paths out of it: a **green (Succeeded)** arrow moving on to the
next step, and a **red (Failed)** arrow going to the failure-notification chain. If *anything*
breaks, anywhere in the pipeline, you get an email about it instead of just silently having stale
data.

---

## 3. `Run_Bronze_Ingestion` (Notebook activity)

Calls the `01_bronze_ingestion.py` Databricks notebook. This copies the 6 raw NHS CSV files into
Delta format, untouched, and registers them as Unity Catalog managed tables. See
`NHS_Databricks_Notebooks_Explained.md` for the full detail on what this notebook does internally.

## 4. `Run_Silver_Transformation` (Notebook activity)

Calls `02_silver_transformation.py`. Cleans up the Bronze data — fixes column names, fixes dates,
removes duplicates — and registers the cleaned tables in Unity Catalog.

## 5. `Clear_Gold_Tables` (Notebook activity)

Calls a small notebook, `06_clear_gold_container.py`, whose only job is to delete the **physical
files** for all 8 Gold tables before they get rebuilt.

**Why this step has to exist at all:** the next step (`Gold_Tables`) rebuilds each Gold table using
`DROP EXTERNAL TABLE` followed by `CREATE EXTERNAL TABLE ... AS SELECT`. The crucial, easy-to-miss
fact about `DROP EXTERNAL TABLE` is that it only removes Synapse's *catalog entry* — the database's
internal record that "this table exists." It does **not** delete the actual Parquet files sitting
in storage. So without this clearing step, the very next `CREATE` for the same table fails with
"External table location already exists," because the old files are still physically there blocking
the new ones from being written.

**Why this is a Databricks notebook and not an ADF Delete activity:** we tried an ADF Delete
activity first, and ran into two separate failure modes:
- Pointed at the `gold` container's **root** with Recursive enabled, it didn't just clear the
  contents — it deleted the **entire container itself** (twice). ADLS Gen2's hierarchical
  namespace can treat a root-level recursive delete as "delete the whole filesystem," unlike flat
  blob storage where the container always survives.
- Switching to a **wildcard**-based delete to avoid that risk caused the opposite problem — it
  matched zero files and silently did nothing, leaving old folders behind.

The fix was to stop using ADF's Delete activity for this entirely and instead use Databricks'
`dbutils.fs.rm(path, recurse=True)`, called once per named table folder (never the container root).
This is simple, reliable, and structurally can't delete the container, since it only ever
operates on specific named subfolders inside it.

## 6. `Gold_Tables` (Script activity)

This is the actual "external tables in ADF" piece your senior asked for — it runs SQL directly
against Synapse Serverless SQL (`gold_db`) via the `yls_synapse` linked service, rebuilding all 8
Gold tables using `CREATE EXTERNAL TABLE ... AS SELECT` (CETAS).

**Why it's split into 9 separate script blocks instead of one big pasted script:** two
Synapse-specific rules forced this:
1. `GO` is not real SQL — it's a client-tool-only batch separator (used in SSMS/Synapse Studio).
   ADF sends a script straight to the database engine, which doesn't understand `GO` at all and
   errors on every occurrence.
2. Synapse Serverless SQL requires `CREATE EXTERNAL TABLE AS SELECT` to be the **only** statement
   in its batch — it can't share a batch with anything else.

So the script is split into Block 1 (all 8 drops, safely wrapped in `IF EXISTS` checks so it never
errors even if a table doesn't exist yet) followed by 8 separate blocks, one CREATE statement each.

The 8 tables it rebuilds are the redesigned Gold layer — see `NHS_Gold_Layer_Business_Value.md` for
what each one actually calculates and why it matters.

## 7. `Get_Webhook_URL` (Web activity)

If *any* of the 4 activities above fails, execution jumps here. This makes a GET request directly
to Azure Key Vault's REST API to fetch a secret called `logic-app-failure-webhook` — the URL of a
Logic App that knows how to send an email. It authenticates using ADF's own **system-assigned
managed identity** (effectively, ADF's own automatic robot login), not a password stored anywhere
in the pipeline itself.

## 8. `Notify_Failure` (Web activity)

Takes the URL fetched in the previous step and sends a POST request to it, with a small JSON body
containing the pipeline's name, a status of "Failed," and the run ID — this is what actually
triggers the Logic App, which then sends you the failure email via SMTP.

---

## 9. Real problems hit while building this, and what they taught us

- **`DROP EXTERNAL TABLE` ≠ deleting files.** This single fact caused the majority of the debugging
  in this entire exercise. Always remember: dropping an external table only ever removes metadata.
- **Recursive delete at a container's root in ADLS Gen2 can delete the container itself.** Always
  point recursive deletes at a specific named subfolder, never the root.
- **`GO` only works in client tools, not when a script is sent programmatically.** Any tool that
  submits SQL directly to the engine (like ADF's Script activity) needs each batch submitted
  separately instead.
- **Two separate credentials existed for Gold vs Silver storage access** (`StorageSAS` and
  `GoldStorageCredential`) — when one stopped working, it wasn't enough to fix the other; both
  needed checking.
- **`HRESULT 0x80070002` means "not found,"** not a permissions problem — worth remembering before
  spending time rotating credentials, since the actual fix that time was just recreating a deleted
  container.
- **Not every Gold table name maps directly to a Silver folder of the same name.** `ecds_org_summary`
  doesn't exist as its own Silver table — it has to be built by combining specific sheets from
  `ecds_activity` and `ecds_supplementary`, the same way `ecds_demographic_summary` is.
