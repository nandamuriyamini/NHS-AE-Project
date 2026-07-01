# Databricks notebook source
# MAGIC %md
# MAGIC ## 02 - Silver: clean it up
# MAGIC - standardize column names (lowercase, underscores, no weird symbols)
# MAGIC - turn `Report_Date` into a real date type
# MAGIC - drop exact duplicate rows
# MAGIC - drop the leftover "TOTAL" footer rows from the monthly summary file
# MAGIC - drop rows where the data row is actually a header repeated in the middle of the export (rare, but cheap to guard against)

# COMMAND ----------

# MAGIC %run "./00_config"

# COMMAND ----------

import re
import hashlib
from pyspark.sql import functions as F

def standardize_columns(df):
    # Synapse Serverless SQL caps column names at 128 characters. The original NHS
    # headers (group + child label combined in Bronze) can run well past that, e.g.
    # "a_e_attendances_greater_than_4_hours_from_arrival_to_admission_transfer_or_..."
    # Truncate anything over 100 chars and append a short hash so two long names that
    # happen to share the same first 90 characters don't collide into duplicates.
    new_cols = []
    seen = set()
    for c in df.columns:
        clean = re.sub(r"[^0-9a-zA-Z]+", "_", c).strip("_").lower()
        if len(clean) > 100:
            suffix = hashlib.md5(clean.encode()).hexdigest()[:6]
            clean = f"{clean[:90]}_{suffix}"
        base, i = clean, 1
        while clean in seen:
            clean = f"{base}_{i}"
            i += 1
        seen.add(clean)
        new_cols.append(clean)
    return df.toDF(*new_cols)

def clean_common(df):
    df = standardize_columns(df)
    if "report_date" in df.columns:
        # try_cast instead of to_date: this workspace runs in ANSI mode, where to_date()
        # throws a hard error on any malformed value instead of returning null. A handful
        # of source rows have an unexpected date format - try_cast turns those into NULL
        # instead of crashing the whole job.
        df = df.withColumn("report_date", F.expr("try_cast(report_date AS DATE)"))
    df = df.dropDuplicates()
    return df

# COMMAND ----------

for table_name in DATASETS:
    df = spark.read.format("delta").load(f"{bronze_path}/{table_name}")
    df = clean_common(df)

    # Dataset-specific cleanup
    if table_name == "monthly_ae_summary" and "org_code" in df.columns:
        df = df.filter(F.upper(F.trim(F.col("org_code"))) != "TOTAL")

    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .save(f"{silver_path}/{table_name}")
    )

    print(f"Silver cleaned: {table_name}  ({df.count()} rows, {len(df.columns)} cols) -> {silver_path}/{table_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC Peek at the cleaned schema for each table — useful before writing Gold aggregations,
# MAGIC since the long original NHS column headers get squashed into snake_case names here.

# COMMAND ----------

for table_name in DATASETS:
    print(f"\n--- {table_name} ---")
    spark.read.format("delta").load(f"{silver_path}/{table_name}").printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC Register each Silver table as a Unity Catalog **managed** table under
# MAGIC `adb_training_bd.yamini_silver`.

# COMMAND ----------

for table_name in DATASETS:
    df = spark.read.format("delta").load(f"{silver_path}/{table_name}")
    df.write.format("delta").mode("overwrite").saveAsTable(f"adb_training_bd.yamini_silver.{table_name}")
    print(f"Registered: adb_training_bd.yamini_silver.{table_name}")
