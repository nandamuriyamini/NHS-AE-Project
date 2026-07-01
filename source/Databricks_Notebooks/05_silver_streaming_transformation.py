# Databricks notebook source
# MAGIC %md
# MAGIC ## 05 - Silver Streaming: clean the live A&E event stream
# MAGIC - cast `arrival_time` to a real timestamp
# MAGIC - drop duplicate events by `event_id` within a watermark window (Event Hub can redeliver
# MAGIC   the same event on retry, so this guards against double-counting)
# MAGIC
# MAGIC Uses `trigger(availableNow=True)`: processes whatever's currently new in Bronze, then
# MAGIC stops - rather than running forever. This makes the notebook a bounded job ADF can call
# MAGIC on a schedule, instead of leaving an infinite streaming query running every time it's
# MAGIC triggered.

# COMMAND ----------

# MAGIC %run "./00_config"

# COMMAND ----------

from pyspark.sql import functions as F

bronze_stream_path = f"{bronze_path}/ae_events_stream"
silver_stream_path = f"{silver_path}/ae_events_stream"
silver_checkpoint_path = f"{silver_path}/_checkpoints/ae_events_stream"

# COMMAND ----------

bronze_events = spark.readStream.format("delta").load(bronze_stream_path)

silver_events = (
    bronze_events
    .withColumn("arrival_time", F.to_timestamp("arrival_time"))
    .withWatermark("arrival_time", "10 minutes")
    .dropDuplicates(["event_id"])
)

# COMMAND ----------

query = (
    silver_events.writeStream
    .format("delta")
    .option("checkpointLocation", silver_checkpoint_path)
    .outputMode("append")
    .trigger(availableNow=True)
    .start(silver_stream_path)
)

query.awaitTermination()

print("Silver streaming batch complete:", query.id)
print("Writing to:", silver_stream_path)

# COMMAND ----------

# MAGIC %md
# MAGIC Register the Silver stream table as a Unity Catalog **managed** table under
# MAGIC `adb_training_bd.yamini_silver`, alongside the batch Silver tables.

# COMMAND ----------

df_silver_stream = spark.read.format("delta").load(silver_stream_path)
df_silver_stream.write.format("delta").mode("overwrite").saveAsTable(
    "adb_training_bd.yamini_silver.ae_events_stream"
)
print("Registered: adb_training_bd.yamini_silver.ae_events_stream")
