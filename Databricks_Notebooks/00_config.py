# Databricks notebook source
# MAGIC %md
# MAGIC ## 00 - Config
# MAGIC Shared settings used by the Bronze, Silver, and Gold notebooks.
# MAGIC Run this notebook first (or `%run` it from the others) so every layer points at the same storage account.
# MAGIC
# MAGIC Wired up for this project's actual resources:
# MAGIC - Storage account: `yaminiprojectadls`
# MAGIC - 4 separate containers: `raw`, `bronze`, `silver`, `gold`
# MAGIC - Key Vault: `kv-bd-training-uk`, secret `storage-account-key`
# MAGIC - Databricks secret scope: `kv-bd-training-uk` (create it once via `#secrets/createScope` if you haven't)

# COMMAND ----------

dbutils.widgets.text("storage_account", "yaminiprojectadls", "Storage account name")
dbutils.widgets.text("raw_container", "raw", "Raw container name")
dbutils.widgets.text("bronze_container", "bronze", "Bronze container name")
dbutils.widgets.text("silver_container", "silver", "Silver container name")
dbutils.widgets.text("gold_container", "gold", "Gold container name")
dbutils.widgets.text("kv_scope", "kv-bd-training-uk", "Key Vault-backed secret scope name")
dbutils.widgets.text("kv_secret_key", "storage-account-key", "Secret name holding the storage key")

storage_account = dbutils.widgets.get("storage_account")
raw_container = dbutils.widgets.get("raw_container")
bronze_container = dbutils.widgets.get("bronze_container")
silver_container = dbutils.widgets.get("silver_container")
gold_container = dbutils.widgets.get("gold_container")
kv_scope = dbutils.widgets.get("kv_scope")
kv_secret_key = dbutils.widgets.get("kv_secret_key")

def require(value, widget_name):
    assert value and value.strip(), f"Set the {widget_name} widget before running."

require(storage_account, "storage_account")
require(raw_container, "raw_container")
require(bronze_container, "bronze_container")
require(silver_container, "silver_container")
require(gold_container, "gold_container")
require(kv_scope, "kv_scope")
require(kv_secret_key, "kv_secret_key")

# COMMAND ----------

# Pull the storage key out of Key Vault (via the Databricks secret scope) and authenticate.
account_key = dbutils.secrets.get(scope=kv_scope, key=kv_secret_key)
spark.conf.set(f"fs.azure.account.key.{storage_account}.dfs.core.windows.net", account_key)

# COMMAND ----------

# Each layer is its own container (not a folder inside one container)
raw_path = f"abfss://{raw_container}@{storage_account}.dfs.core.windows.net"
bronze_path = f"abfss://{bronze_container}@{storage_account}.dfs.core.windows.net"
silver_path = f"abfss://{silver_container}@{storage_account}.dfs.core.windows.net"
gold_path = f"abfss://{gold_container}@{storage_account}.dfs.core.windows.net"

spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
spark.sql("CREATE DATABASE IF NOT EXISTS silver")
spark.sql("CREATE DATABASE IF NOT EXISTS gold")

# The 6 combined CSVs you uploaded into the raw container (matches the actual filenames there)
DATASETS = {
    "monthly_ae_summary":   "monthly_AE_summary.csv",
    "ae_by_provider":       "AE_by_provider.csv",
    "nel_ytd_growth_rates": "NEL_YTD_growth_rates.csv",
    "ecds_activity":        "ECDS_Activity.csv",
    "ecds_performance":     "ECDS_Performance.csv",
    "ecds_supplementary":   "ECDS_Supplementary.csv",
}

print("raw_path   :", raw_path)
print("bronze_path:", bronze_path)
print("silver_path:", silver_path)
print("gold_path  :", gold_path)
print("datasets   :", list(DATASETS.keys()))
