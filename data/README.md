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
- `Combined/` — 6 processed combined CSVs excluded from git due to file size limits:

| File | Size | Reason excluded |
|---|---|---|
| `monthly_AE_summary.csv` | 1 MB | Excluded by .gitignore (`*.csv` rule) |
| `AE_by_provider.csv` | 2 MB | Excluded by .gitignore (`*.csv` rule) |
| `NEL_YTD_growth_rates.csv` | 1.5 MB | Excluded by .gitignore (`*.csv` rule) |
| `ECDS_Performance.csv` | 18 MB | Excluded by .gitignore (`*.csv` rule) |
| `ECDS_Activity.csv` | 88 MB | Exceeds GitHub 50MB recommended limit |
| `ECDS_Supplementary.csv` | 117 MB | Exceeds GitHub 100MB hard limit |

These files are uploaded to the `raw/` container in ADLS (`yaminiprojectadls`) and
processed by the pipeline from there. They do not need to be in git — ADLS is the
correct storage location for data files of this size.

## Source
Downloaded from: https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/
