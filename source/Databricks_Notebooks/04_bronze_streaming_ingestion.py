# Databricks notebook source
# MAGIC %md
# MAGIC ## 04 - Bronze Streaming: ingest live A&E events from Event Hub
# MAGIC Reads the synthetic event stream sent by `Streaming/ae_event_producer.py`.
# MAGIC
# MAGIC This cluster doesn't have the native `azure-eventhubs-spark` Maven connector
# MAGIC available, and the namespace is on Basic tier (no Kafka-compatible endpoint), so this
# MAGIC uses the plain `azure-eventhub` Python SDK instead: listen for a short burst, batch
# MAGIC the events received in that window, append them to Bronze as Delta. Re-running the
# MAGIC loop below repeatedly is what makes this behave like a live feed - Silver still reads
# MAGIC this Bronze table as a genuine Spark stream regardless of how Bronze itself was written.

# COMMAND ----------

# MAGIC %run "./00_config"

# COMMAND ----------

import json
import threading
import time

from azure.eventhub import EventHubConsumerClient
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

event_schema = StructType([
    StructField("event_id", StringType()),
    StructField("arrival_time", StringType()),
    StructField("org_code", StringType()),
    StructField("org_name", StringType()),
    StructField("attendance_type", IntegerType()),
    StructField("age_band", StringType()),
    StructField("gender", StringType()),
    StructField("disposition", StringType()),
])

eh_connection_string = dbutils.secrets.get(scope=kv_scope, key="y-eventhub-connection-string")
eh_name = "ae-events"
bronze_stream_path = f"{bronze_path}/ae_events_stream"

# COMMAND ----------

def capture_batch(listen_seconds=20):
    buffer = []

    def on_event_batch(partition_context, events):
        for event in events:
            try:
                buffer.append(json.loads(event.body_as_str()))
            except Exception:
                pass

    consumer_client = EventHubConsumerClient.from_connection_string(
        conn_str=eh_connection_string,
        consumer_group="$Default",
        eventhub_name=eh_name,
    )

    def stop_after(seconds):
        time.sleep(seconds)
        consumer_client.close()

    stopper = threading.Thread(target=stop_after, args=(listen_seconds,))
    stopper.start()

    with consumer_client:
        try:
            consumer_client.receive_batch(
                on_event_batch=on_event_batch,
                starting_position="@latest",
                max_wait_time=5,
            )
        except Exception:
            pass

    stopper.join()
    return buffer


def write_batch_to_bronze(events):
    if not events:
        print("No events captured this cycle.")
        return
    df = spark.createDataFrame(events, schema=event_schema)
    df = df.withColumn("_ingested_at", F.current_timestamp())
    df.write.format("delta").mode("append").save(bronze_stream_path)
    print(f"Wrote {df.count()} events to Bronze -> {bronze_stream_path}")

# COMMAND ----------

NUMBER_OF_CYCLES = 6
SECONDS_PER_CYCLE = 20

for cycle in range(NUMBER_OF_CYCLES):
    print(f"--- Cycle {cycle + 1}/{NUMBER_OF_CYCLES}: listening for {SECONDS_PER_CYCLE}s ---")
    events = capture_batch(listen_seconds=SECONDS_PER_CYCLE)
    write_batch_to_bronze(events)

print("Done. Re-run this cell to capture another round of live events.")

# COMMAND ----------

# MAGIC %md
# MAGIC Register the Bronze stream table as a Unity Catalog **managed** table under
# MAGIC `adb_training_bd.yamini_bronze`, alongside the batch Bronze tables.

# COMMAND ----------

df_bronze_stream = spark.read.format("delta").load(bronze_stream_path)
df_bronze_stream.write.format("delta").mode("overwrite").saveAsTable(
    "adb_training_bd.yamini_bronze.ae_events_stream"
)
print("Registered: adb_training_bd.yamini_bronze.ae_events_stream")
