# NHS Project — Senior's Requirements Checklist

This documents exactly how each item your senior asked for was implemented, where to find it, and
how it works — so you can explain or demo any of these directly.

---

## 1. Unity Catalog

**What was asked:** register tables in Databricks Unity Catalog, not just leave them as files in
storage.

**What was built:** two schemas under the shared `adb_training_bd` catalog —
**`yamini_bronze`** and **`yamini_silver`** — created automatically by `00_config.py`
(`CREATE SCHEMA IF NOT EXISTS adb_training_bd.yamini_bronze` / `yamini_silver`).

Every Bronze and Silver notebook (batch **and** streaming) ends with a cell that registers its
output as a **managed table** in the relevant schema:
- `01_bronze_ingestion.py` → registers all 6 batch datasets under `yamini_bronze`
- `02_silver_transformation.py` → registers all 6 batch datasets under `yamini_silver`
- `04_bronze_streaming_ingestion.py` → registers `ae_events_stream` under `yamini_bronze`
- `05_silver_streaming_transformation.py` → registers `ae_events_stream` under `yamini_silver`

**Why managed tables, not external tables, here:** registering an *external* table (one pointing at
an arbitrary storage path) requires a Unity Catalog **External Location** and **Storage
Credential** to be set up for `yaminiprojectadls` first — this shared training workspace doesn't
have one configured for this storage account. **Managed** tables don't need that, since they use
the metastore's own pre-configured storage, so this was the practical way to satisfy the Unity
Catalog requirement within this environment's constraints.

**To show this working:** Databricks → Catalog Explorer → `adb_training_bd` → `yamini_bronze` /
`yamini_silver` → 7 tables in each (6 batch + 1 streaming).

---

## 2. External tables in ADF

**What was asked:** demonstrate external tables being created/managed through Azure Data Factory,
not only manually in Synapse Studio.

**What was built:** a **Script activity** named **`Gold_Tables`** inside `Batch_Pipeline`, using
the `yls_synapse` linked service to run SQL directly against Synapse Serverless SQL (`gold_db`).
It executes `DROP EXTERNAL TABLE` + `CREATE EXTERNAL TABLE ... AS SELECT` (CETAS) for all 8 Gold
tables, split across 9 separate script blocks (1 for the drops, 8 for the creates — required
because Synapse needs each CETAS statement to be the only statement in its batch).

**To show this working:** ADF Studio → `Batch_Pipeline` → click `Gold_Tables` → Settings tab shows
the 9 script blocks. Running Debug on the pipeline executes them live.

---

## 3. Key Vault

**What was asked:** use Azure Key Vault for secrets instead of hardcoding credentials.

**What was built:** a linked service **`yls_keyvault`** in ADF, pointing at the shared vault
**`kv-bd-training-uk`**. Secrets used from it:
- `yamini-storage-account-key` — the ADLS storage account key, fetched by Databricks notebooks via
  a secret scope (`dbutils.secrets.get(scope=kv_scope, key=kv_secret_key)` in `00_config.py`)
- `logic-app-failure-webhook` — the Logic App's trigger URL, fetched at runtime by ADF's
  `Get_Webhook_URL` activity (a direct REST call to Key Vault's API, authenticated via ADF's own
  system-assigned managed identity — no password stored anywhere in the pipeline)

**To show this working:** Azure Portal → Key Vault `kv-bd-training-uk` → Secrets, or ADF → Manage →
Linked services → `yls_keyvault` → Test connection.

---

## 4. Email notification / Logic App

**What was asked:** get an actual email alert when something fails, and explore building a Logic
App.

**What was built:** a Consumption-plan Logic App, **`la-nhs-pipeline-alerts`**, with:
- Trigger: **"When an HTTP request is received"** — accepts a JSON body with `pipelineName`,
  `status`, `errorMessage`, `runId`
- Action: **Send Email (V3)** via an SMTP connector (since the work email domain is hosted on
  Rackspace, not Microsoft 365 or Gmail — both were tried first and didn't work), sending a
  formatted alert email with all 4 fields included

**To show this working:** Azure Portal → Logic Apps → `la-nhs-pipeline-alerts` → Run history, or
just trigger a real pipeline failure and check your inbox.

---

## 5. Pipeline failure handling

**What was asked:** the pipeline should actually respond to failures, not just stop silently.

**What was built:** every activity in both `Batch_Pipeline` and `Streaming_Pipeline` has a **red
(Failed)** dependency arrow leading to a 2-step chain:
1. **`Get_Webhook_URL`** (Web activity) — fetches the Logic App's URL from Key Vault
2. **`Notify_Failure`** (Web activity) — POSTs the failure details to that URL, triggering the
   email

This means a failure anywhere in either pipeline — a notebook erroring, a Script activity failing —
results in an actual email, not a silent failure only visible if someone happens to check ADF's
monitoring tab.

---

## 6. Complete data orchestration with ADF

**What was asked:** the whole batch flow should be runnable end-to-end from ADF, not require manual
steps in Synapse/Databricks each time.

**What was built:** **`Batch_Pipeline`** now runs the full chain with one click:
```
Run_Bronze_Ingestion → Run_Silver_Transformation → Clear_Gold_Tables → Gold_Tables
```
- `Run_Bronze_Ingestion` / `Run_Silver_Transformation` — Databricks notebook activities
- `Clear_Gold_Tables` — a Databricks notebook activity that clears old Gold table files before
  rebuild (necessary because `DROP EXTERNAL TABLE` only removes catalog metadata, not the actual
  files — without this step, rebuilding fails with "location already exists")
- `Gold_Tables` — the Script activity covered in item 2 above

**`Streaming_Pipeline`** runs its own two-step chain (`Run_Streaming_Bronze` →
`Run_Streaming_Silver`) the same way, with the same failure-notification safety net.

**Deliberate decision: no automatic schedule trigger on either pipeline.** Both data sources only
update when manually triggered anyway (NHS publishes monthly; the streaming producer script has to
be started by hand), so a timer wouldn't remove real manual work — it would just add compute cost
for runs that might capture nothing. Both pipelines are triggered manually (via Debug or "Trigger
now") when you actually want fresh data.

**To show this working:** ADF Studio → either pipeline → **Debug**, and watch all activities turn
green end-to-end.
