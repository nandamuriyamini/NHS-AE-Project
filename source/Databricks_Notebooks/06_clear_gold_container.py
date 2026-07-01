# Databricks notebook source
# MAGIC %md
# MAGIC ## 06 - Clear Gold tables before rebuild
# MAGIC Deletes each known Gold table's folder (and its contents) before the Synapse Script
# MAGIC activity recreates them via CETAS. `DROP EXTERNAL TABLE` in Synapse only removes the
# MAGIC catalog entry, not the underlying Parquet files, so without this step a rebuild fails
# MAGIC with "External table location already exists."
# MAGIC
# MAGIC Only ever touches these 8 named subfolders directly — never the `gold` container root —
# MAGIC so this can't accidentally delete the container itself (unlike ADF's Delete activity,
# MAGIC which did exactly that when pointed at the root with Recursive enabled).

# COMMAND ----------

# MAGIC %run "./00_config"

# COMMAND ----------

GOLD_TABLES = [
    "national_monthly_trend",
    "national_yearly_trend",
    "trust_performance_ranking",
    "regional_summary",
    "nel_ytd_growth_rates",
    "ecds_demographic_summary",
    "ecds_org_summary",
    "ecds_performance",
]

for table_name in GOLD_TABLES:
    path = f"{gold_path}/{table_name}"
    try:
        dbutils.fs.rm(path, recurse=True)
        print(f"Cleared: {path}")
    except Exception as e:
        print(f"Nothing to clear at {path} ({e})")
