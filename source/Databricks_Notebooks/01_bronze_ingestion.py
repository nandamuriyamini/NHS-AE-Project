# Databricks notebook source
# MAGIC %md
# MAGIC ## 01 - Bronze: load raw CSVs as-is
# MAGIC Bronze just means "copy the files into Delta format, don't change anything."
# MAGIC We add two tracking columns (`_source_file`, `_ingested_at`) so you always know where a row came from and when it landed.

# COMMAND ----------

# MAGIC %run "./00_config"

# COMMAND ----------

from pyspark.sql import functions as F

for table_name, filename in DATASETS.items():
    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv(f"{raw_path}/{filename}")
    )

    df = (
        df
        .withColumn("_source_file", F.lit(filename))
        .withColumn("_ingested_at", F.current_timestamp())
    )

    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .option("delta.columnMapping.mode", "name")  # original NHS headers have spaces/colons/parens
        .option("delta.minReaderVersion", "2")
        .option("delta.minWriterVersion", "5")
        .save(f"{bronze_path}/{table_name}")
    )

    print(f"Bronze loaded: {table_name}  ({df.count()} rows, {len(df.columns)} cols) -> {bronze_path}/{table_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC Quick check — read every Bronze Delta path back and print its row count.

# COMMAND ----------

for table_name in DATASETS:
    n = spark.read.format("delta").load(f"{bronze_path}/{table_name}").count()
    print(f"{table_name}: {n} rows  ({bronze_path}/{table_name})")

# COMMAND ----------

# MAGIC %md
# MAGIC Register each Bronze table as a Unity Catalog **managed** table under
# MAGIC `adb_training_bd.yamini_bronze`. Managed tables don't need a registered External Location
# MAGIC (unlike external tables), so this works even though this training workspace doesn't have a
# MAGIC Storage Credential set up for `yaminiprojectadls`.

# COMMAND ----------

for table_name in DATASETS:
    df = spark.read.format("delta").load(f"{bronze_path}/{table_name}")
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("delta.columnMapping.mode", "name")  # raw NHS headers have spaces/colons/parens, same as the Bronze path write above
        .option("delta.minReaderVersion", "2")
        .option("delta.minWriterVersion", "5")
        .saveAsTable(f"adb_training_bd.yamini_bronze.{table_name}")
    )
    print(f"Registered: adb_training_bd.yamini_bronze.{table_name}")
