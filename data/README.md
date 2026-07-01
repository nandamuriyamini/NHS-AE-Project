# Data

Raw NHS England A&E data files are stored here locally but excluded from git via `.gitignore`.

## Where the data lives
- **Azure Data Lake Storage (ADLS)**: `yaminiprojectadls` storage account
  - `raw/` container — 6 combined CSV files uploaded as source data
  - `bronze/` container — Delta tables written by Databricks Bronze notebooks
  - `silver/` container — Delta tables written by Databricks Silver notebooks
  - `gold/` container — Parquet files written by Synapse CETAS queries

## Local folders (git-ignored)
- `All_CSV/` — raw monthly NHS Excel/CSV workbooks downloaded from NHS England website
- `Combined/` — 6 processed combined CSVs ready for ADLS upload:
  - `monthly_AE_summary.csv`
  - `AE_by_provider.csv`
  - `NEL_YTD_growth_rates.csv`
  - `ECDS_Activity.csv`
  - `ECDS_Performance.csv`
  - `ECDS_Supplementary.csv`

## Source
Downloaded from: https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/
