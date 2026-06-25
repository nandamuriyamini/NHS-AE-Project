# Databricks notebook source
# MAGIC %md
# MAGIC ## 03 - Gold: business-ready tables (11 total)
# MAGIC - `national_monthly_trend`, `trust_kpis_monthly`, `trust_kpis_quarterly`, `nel_ytd_growth_rates`
# MAGIC - `ecds_performance` — one long-format table (its 4 breakdown sheets have unrelated metric sets, so pivoting each separately added little value)
# MAGIC - 6 unified ECDS breakdowns (`ecds_org_summary`, `ecds_age_breakdown`, `ecds_gender_breakdown`,
# MAGIC   `ecds_ethnicity_breakdown`, `ecds_chief_complaint_breakdown`, `ecds_frailty_breakdown`):
# MAGIC   each merges the T1/UTC/"all types" variants of a breakdown into one table with a `basis` column,
# MAGIC   AND unions the two NHS report eras together — `ecds_supplementary` (Apr 2023-Sep 2025) and
# MAGIC   `ecds_activity` (Oct 2025-Mar 2026) are sequential, not overlapping, so this turns 23 disconnected
# MAGIC   tables into 6 continuous ~3-year ones, tagged with a `source_report` column so you can always tell
# MAGIC   which underlying report a row came from.

# COMMAND ----------

# MAGIC %run "./00_config"

# COMMAND ----------

from pyspark.sql import functions as F

def save_gold(df, name):
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .option("delta.columnMapping.mode", "name")  # pivoted ECDS columns have spaces/colons (e.g. "Admitted Attendances: Managing Well")
        .option("delta.minReaderVersion", "2")
        .option("delta.minWriterVersion", "5")
        .save(f"{gold_path}/{name}")
    )
    # No spark.sql(CREATE TABLE...) here — Unity Catalog needs a registered External
    # Location for that, which this training workspace doesn't have. Reading/writing
    # straight from the Delta path works fine without it.
    print(f"Gold saved: {name}  ({df.count()} rows, {len(df.columns)} cols) -> {gold_path}/{name}")

# COMMAND ----------

# MAGIC %md ### 1. National monthly trend (sum every numeric metric by month)

# COMMAND ----------

monthly_summary = spark.read.format("delta").load(f"{silver_path}/monthly_ae_summary")
numeric_cols = [f.name for f in monthly_summary.schema.fields if f.dataType.typeName() in ("integer", "long", "double", "float")]

gold_national_trend = (
    monthly_summary
    .groupBy("report_date")
    .agg(*[F.sum(c).alias(c) for c in numeric_cols])
    .orderBy("report_date")
)
save_gold(gold_national_trend, "national_monthly_trend")

# COMMAND ----------

# MAGIC %md ### 2. Trust-level KPIs, split into monthly and quarterly tables

# COMMAND ----------

ae_by_provider = spark.read.format("delta").load(f"{silver_path}/ae_by_provider")

gold_trust_monthly = ae_by_provider.filter(F.col("period_type") == "Monthly")
gold_trust_quarterly = ae_by_provider.filter(F.col("period_type") == "Quarterly")

save_gold(gold_trust_monthly, "trust_kpis_monthly")
save_gold(gold_trust_quarterly, "trust_kpis_quarterly")

# COMMAND ----------

# MAGIC %md ### 3. NEL YTD growth rates — already clean, just promote it to Gold

# COMMAND ----------

gold_nel_growth = spark.read.format("delta").load(f"{silver_path}/nel_ytd_growth_rates")
save_gold(gold_nel_growth, "nel_ytd_growth_rates")

# COMMAND ----------

# MAGIC %md ### 4. ECDS Performance — one long-format table, no pivot

# COMMAND ----------

save_gold(spark.read.format("delta").load(f"{silver_path}/ecds_performance"), "ecds_performance")

# COMMAND ----------

# MAGIC %md ### 5. ECDS breakdowns — merge T1/UTC variants AND merge the two report eras into one continuous table per dimension

# COMMAND ----------

def basis_from_sheet(sheet):
    s = sheet.lower()
    if "t1" in s:
        return "Type 1 & 2"
    if "utc" in s:
        return "UTC"
    return "All Types"

def clean_metric_col(df):
    # NHS source files vary capitalization/spacing of the same metric between report eras
    # (e.g. "A&E attendances..." vs "a&e attendances..."). Delta's storage layer is
    # case-insensitive on column names even though Spark treated them as distinct strings,
    # so pivoting on the raw text throws DELTA_DUPLICATE_COLUMNS_FOUND. Normalize first.
    cleaned = F.lower(F.trim(F.col("metric")))
    cleaned = F.regexp_replace(cleaned, r"[^0-9a-z]+", "_")
    cleaned = F.regexp_replace(cleaned, r"^_+|_+$", "")
    return df.withColumn("metric", cleaned)

def load_breakdown(table_name, sheet_name, source_report):
    df = spark.read.format("delta").load(f"{silver_path}/{table_name}")
    df = df.filter(F.col("sheet") == sheet_name)
    df = clean_metric_col(df)

    if "parent_organisation" in df.columns:
        # ecds_activity pattern
        df = df.select(
            F.col("parent_organisation").alias("org_region"),
            F.col("organisation").alias("org_name"),
            F.col("organisation_code").alias("org_code"),
            "period_label", "report_date", "metric", "value",
        )
    else:
        # ecds_supplementary pattern
        df = df.select(
            F.col("region").alias("org_region"),
            F.col("org_name").alias("org_name"),
            F.col("org_code").alias("org_code"),
            "period_label", "report_date", "metric", "value",
        )

    return (
        df
        .withColumn("source_report", F.lit(source_report))
        .withColumn("basis", F.lit(basis_from_sheet(sheet_name)))
    )

DIMENSIONS = {
    "ecds_org_summary": [
        ("ecds_activity", "Summary", "ECDS_Activity"),
        ("ecds_supplementary", "System & Provider Summary - T1", "ECDS_Supplementary"),
        ("ecds_supplementary", "System & Provider Summary - UTC", "ECDS_Supplementary"),
    ],
    "ecds_age_breakdown": [
        ("ecds_activity", "Age", "ECDS_Activity"),
        ("ecds_activity", "Age T1", "ECDS_Activity"),
        ("ecds_supplementary", "Age - T1", "ECDS_Supplementary"),
        ("ecds_supplementary", "Age - UTC", "ECDS_Supplementary"),
    ],
    "ecds_gender_breakdown": [
        ("ecds_activity", "Gender", "ECDS_Activity"),
        ("ecds_activity", "Gender T1", "ECDS_Activity"),
        ("ecds_supplementary", "Gender - T1", "ECDS_Supplementary"),
        ("ecds_supplementary", "Gender - UTC", "ECDS_Supplementary"),
    ],
    "ecds_ethnicity_breakdown": [
        ("ecds_activity", "Ethnicity", "ECDS_Activity"),
        ("ecds_activity", "Ethnicity T1", "ECDS_Activity"),
        ("ecds_supplementary", "Ethnicity - T1", "ECDS_Supplementary"),
        ("ecds_supplementary", "Ethnicity - UTC", "ECDS_Supplementary"),
    ],
    "ecds_chief_complaint_breakdown": [
        ("ecds_activity", "Chief Complaint", "ECDS_Activity"),
        ("ecds_activity", "Chief Complaint T1", "ECDS_Activity"),
        ("ecds_supplementary", "Chief Complaint - T1", "ECDS_Supplementary"),
        ("ecds_supplementary", "Chief Complaint - UTC", "ECDS_Supplementary"),
    ],
    "ecds_frailty_breakdown": [
        ("ecds_activity", "Frailty", "ECDS_Activity"),
        ("ecds_activity", "Frailty T1", "ECDS_Activity"),
        ("ecds_supplementary", "Frailty - T1", "ECDS_Supplementary"),
        ("ecds_supplementary", "Frailty - UTC", "ECDS_Supplementary"),
    ],
}

for gold_name, sources in DIMENSIONS.items():
    parts = [load_breakdown(t, s, r) for t, s, r in sources]
    long_df = parts[0]
    for p in parts[1:]:
        long_df = long_df.unionByName(p)

    id_cols = ["source_report", "basis", "period_label", "report_date", "org_region", "org_name", "org_code"]
    wide = long_df.groupBy(*id_cols).pivot("metric").agg(F.first("value"))
    save_gold(wide, gold_name)

# COMMAND ----------

# MAGIC %md
# MAGIC Done. List every Gold Delta path that now exists:

# COMMAND ----------

for f in dbutils.fs.ls(gold_path):
    print(f.name, f.size)
