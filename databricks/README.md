# Databricks notebooks

| Notebook | Layer | What it does |
|---|---|---|
| `01_bronze.py` | bronze | Loads the regulatory chunks and 1,000 synthetic claims into Delta tables; gold labels kept in a separate table |
| `02_silver_quality.py` | silver | Validates each table against its YAML contract (Pandera), stops on failure, anonymises claims, adds Delta NOT NULL / CHECK constraints generated from the contracts, appends a `quality_runs` history |
| `03_gold_and_governance.py` | gold | Writes triage suggestions and evaluation history, documents tables and columns, tags classification and personal data, grants per role, masks raw identifiers |

The notebooks import the same `ccp` package as the API and the tests, so a rule is written once.

## Run on Databricks Free Edition

1. Sign up at https://www.databricks.com/learn/free-edition (serverless only, one SQL warehouse,
   fair-use quotas, no commercial use: see the "Free Edition limitations" page).
2. Workspace > Create > Git folder > `https://github.com/26sneakysnake/compliance-copilot`.
3. Open `databricks/01_bronze.py`, attach serverless compute, Run all. Then 02 and 03.
4. Optional: Jobs & Pipelines > Create job with the three notebooks as dependent tasks, scheduled daily.

Catalog and schema are widgets (defaults: `workspace` / `compliance_copilot`).
