# NHS Streaming Notebooks — Explained in Plain English (Every Detail)

This covers the two notebooks that power the streaming side of this project —
`04_bronze_streaming_ingestion.py` and `05_silver_streaming_transformation.py` — in much more
detail than the general notebook summary, going through what every piece does and why it's there.

---

## The big picture: what these two notebooks are doing together

A fake "hospital" (the `ae_event_producer.py` script, running on your own laptop) sends a steady
trickle of made-up A&E events to Azure Event Hub — think of Event Hub as a mailbox that holds
messages briefly until something comes and reads them. These two notebooks are the "something" that
reads them:

1. **Notebook 04 (Bronze)** — checks the mailbox, grabs whatever's arrived, and writes it down
   exactly as received.
2. **Notebook 05 (Silver)** — takes what notebook 04 wrote down, cleans it up a little, and removes
   anything that looks like a duplicate.

---

## Notebook 04 — `04_bronze_streaming_ingestion.py`

### Why this notebook looks unusual

Normally, reading from Event Hub in Spark uses a connector that speaks a protocol called **Kafka**.
We couldn't use that here for two real, concrete reasons:
1. The Databricks cluster in this training workspace doesn't have the Kafka connector library
   installed.
2. Even if it did, this particular Event Hub is on the cheapest **"Basic"** pricing tier, which
   **does not support Kafka at all** — this is a hard limitation of that pricing tier, not a bug or
   a setting you can flip on.

So instead, this notebook uses a much simpler, lower-level approach: the plain
**`azure-eventhub`** Python library — the same kind of library you'd use in any ordinary Python
script, nothing Spark-specific about how it talks to Event Hub.

### The imports, explained
- `json` — Event Hub messages arrive as raw text; this turns that text back into a Python
  dictionary so we can work with the fields inside it.
- `threading`, `time` — used together to make the "listen for exactly 20 seconds, then stop"
  behavior work (explained below).
- `EventHubConsumerClient` (from `azure.eventhub`) — the actual tool that connects to Event Hub and
  listens for messages.
- `pyspark.sql.functions as F` — Spark's library of column-level operations (here, just used to
  stamp a timestamp).
- `StructType`, `StructField`, `StringType`, `IntegerType` — used to explicitly describe the shape
  of each event (which fields exist and what type each one is), instead of letting Spark guess.

### `event_schema`
This explicitly lists the 8 fields every event has: `event_id`, `arrival_time`, `org_code`,
`org_name`, `attendance_type`, `age_band`, `gender`, `disposition`. Defining this upfront means
Spark doesn't have to guess the structure every time — it just trusts this definition.

### Getting connected
- `eh_connection_string` — fetched from Key Vault (via the Databricks secret scope), not typed
  directly into the notebook — the actual password-equivalent for talking to this Event Hub.
- `eh_name = "ae-events"` — the specific Event Hub's name (a single Event Hub *namespace* can
  contain multiple individual Event Hubs; this is the one the producer script sends to).
- `bronze_stream_path` — where the captured events get written, inside the `bronze` container.

### `capture_batch()` — the actual listening logic
This function listens for a fixed number of seconds and returns whatever arrived in that window.
Step by step:
1. `buffer = []` — an empty list to collect events into.
2. `on_event_batch(...)` — a function that runs automatically every time a new batch of messages
   arrives; it converts each message's text body back into a Python dictionary (via `json.loads`)
   and adds it to `buffer`. Wrapped in `try/except` so one malformed message can't crash the whole
   thing.
3. `EventHubConsumerClient.from_connection_string(...)` — opens the actual connection to Event Hub,
   using consumer group `"$Default"` (the standard, always-available reading channel every Event
   Hub has).
4. **The stop-after-N-seconds trick**: `EventHubConsumerClient.receive_batch(...)` would normally
   keep listening *forever* unless told otherwise. To make it stop after a fixed time, this code
   starts a second background thread (`stopper`) that does nothing but sleep for `listen_seconds`
   and then forcibly closes the connection — which causes `receive_batch` to stop and return
   control back to the main code.
5. `starting_position="@latest"` — only look at messages that arrive **from now onward**, ignoring
   anything that was sent before this listening window started (so re-running this doesn't
   re-process old messages).
6. Returns `buffer` — the list of events captured in that window (could be empty if nothing arrived).

### `write_batch_to_bronze()`
Takes whatever `capture_batch()` returned and:
1. If nothing arrived, just prints a message and stops — there's nothing to write.
2. Otherwise, turns the list of dictionaries into a proper Spark DataFrame using the schema defined
   earlier.
3. Adds an `_ingested_at` column — the exact moment this batch was written, for traceability.
4. **Appends** (not overwrites) it onto whatever's already in the Bronze Delta table — each run adds
   new rows without erasing what came before.

### The main loop — simulating a "live" feed
```python
NUMBER_OF_CYCLES = 6
SECONDS_PER_CYCLE = 20
```
This runs the listen-and-write cycle **6 times**, each listening for **20 seconds** — about 2
minutes total per run of this notebook. This is the practical workaround for not having a true
always-on streaming connector: instead of one continuous stream, it's repeated short bursts.
Running this notebook again later (e.g. via the ADF pipeline) picks up whatever's arrived
*since* the last run, since `starting_position="@latest"` always starts from "now."

### The Unity Catalog registration (last 2 cells)
Reads back everything currently in the Bronze stream Delta table and registers it as a **managed
table** in Unity Catalog (`adb_training_bd.yamini_bronze.ae_events_stream`) — this is what makes it
show up properly in Catalog Explorer, queryable by name, rather than just sitting as files in
storage that only this notebook knows the path to.

---

## Notebook 05 — `05_silver_streaming_transformation.py`

### Why this one looks completely different from notebook 04

Notebook 04 had to use a manual polling workaround because of the Kafka limitation. Notebook 05
doesn't have that problem — it's not talking to Event Hub directly, it's reading from a Delta table
that notebook 04 already wrote to, and **reading from a Delta table as a stream is something Spark
fully supports natively**, no workaround needed. So this notebook uses genuine
**Spark Structured Streaming** — Databricks' real, built-in streaming engine.

### Setting up the paths
Three paths: where Bronze stream data is read from, where the cleaned Silver version gets written
to, and a **checkpoint** path — a small folder Spark uses internally to remember exactly which rows
it has already processed, so re-running this notebook doesn't reprocess the same events twice.

### The actual streaming read and transform
```python
bronze_events = spark.readStream.format("delta").load(bronze_stream_path)
```
This is the key difference from a normal `spark.read` — `readStream` tells Spark "treat this as an
ongoing stream of new rows being added, not a fixed snapshot."

Then three transformations are chained on:
1. **`to_timestamp("arrival_time")`** — the `arrival_time` field arrived as plain text (since JSON
   doesn't have a native date/time type); this converts it into a real timestamp Spark can sort,
   compare, and filter on properly.
2. **`withWatermark("arrival_time", "10 minutes")`** — this tells Spark "don't wait around forever
   for late-arriving events; once 10 minutes have passed for a given time window, consider it
   closed." This is a streaming-specific concept needed to make duplicate-removal work efficiently —
   without it, Spark would have to remember *every single event it has ever seen* to check for
   duplicates, which isn't sustainable for a stream that's meant to run indefinitely.
3. **`dropDuplicates(["event_id"])`** — removes events with an `event_id` that's already been seen
   within that watermark window. This matters because Event Hub can occasionally **redeliver the
   same message more than once** (a normal behavior of most message queue systems, to guarantee a
   message is never silently lost) — without this, the same real-world event could get counted
   twice in the data.

### Writing the result out
```python
query = (
    silver_events.writeStream
    .format("delta")
    .option("checkpointLocation", silver_checkpoint_path)
    .outputMode("append")
    .trigger(availableNow=True)
    .start(silver_stream_path)
)
query.awaitTermination()
```

- **`outputMode("append")`** — only ever add new rows, never rewrite old ones.
- **`trigger(availableNow=True)`** — this is the most important line in the whole notebook. A
  Structured Streaming query, by default, starts and then **runs forever**, continuously waiting for
  new data — it never naturally "finishes." That's fine if you start it once manually and leave it
  running, but it's a real problem the moment something like Azure Data Factory wants to call this
  notebook repeatedly on a schedule: each scheduled run would start *another* never-ending query
  stacking up in the background, since the previous one never stopped. `availableNow=True` changes
  the behavior to "process whatever's currently new, then stop" — turning it into a normal, bounded
  job that's safe to call again and again.
- **`query.awaitTermination()`** — tells the notebook to actually wait until that bounded job
  finishes before moving on to the next cell (otherwise the notebook would race ahead while the
  streaming write was still happening in the background).

### The Unity Catalog registration (last 2 cells)
Same idea as notebook 04 — reads back the current Silver stream Delta table and registers it as a
managed table under `adb_training_bd.yamini_silver.ae_events_stream`.

---

## Summary: the journey of one single event

1. The producer script invents a fake A&E event and sends it to Event Hub.
2. Notebook 04 is listening (during one of its 20-second windows) and catches it, writing it
   into Bronze almost exactly as received, just with a timestamp of when it was caught added.
3. Notebook 05 picks it up from Bronze as part of its next streaming run, fixes its timestamp's
   data type, checks it isn't a duplicate of something already processed, and writes it into Silver.
4. From there, the same event eventually feeds into the `live_ae_events` Gold table in Synapse
   (rebuilt manually, since it's a CETAS external table — a frozen snapshot, not a live view), and
   finally shows up on the Power BI streaming dashboard next time that's refreshed.
