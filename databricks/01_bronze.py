# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Bronze: ingest regulatory texts and synthetic claims
# MAGIC
# MAGIC Runs on **Databricks Free Edition** (serverless compute, Unity Catalog catalog `workspace`).
# MAGIC Import this repository as a Git folder (Workspace > Create > Git folder), then run the notebooks in order.
# MAGIC
# MAGIC All claims are **synthetic** and the insurer is **fictional**. The regulatory sample corpus is a paraphrase;
# MAGIC run `python -m ccp.cli fetch-official` locally and commit the output to `data/corpus/official/` to use the
# MAGIC official EUR-Lex texts instead (Free Edition restricts outbound internet access).

# COMMAND ----------

# MAGIC %pip install pandera pyyaml
# MAGIC %restart_python

# COMMAND ----------

import os
import sys

REPO = os.path.dirname(os.getcwd())  # notebooks live in <repo>/databricks
sys.path.insert(0, REPO)
os.environ["CCP_ROOT"] = REPO

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "compliance_copilot")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA} COMMENT 'Compliance copilot demo: fictional bank, synthetic data'")

# COMMAND ----------

import pandas as pd

from ccp.corpus import load_corpus
from ccp.pipeline import LABEL_COLUMNS
from ccp.synthetic import generate

chunks = pd.DataFrame([c.to_dict() for c in load_corpus("auto")])
claims = pd.DataFrame(generate(n=1000, seed=7))
labels = claims[["claim_id", *LABEL_COLUMNS]]
raw = claims.drop(columns=LABEL_COLUMNS)
print(len(chunks), "chunks,", len(raw), "claims")

# COMMAND ----------

def write(df: pd.DataFrame, table: str):
    (spark.createDataFrame(df).write.mode("overwrite").option("overwriteSchema", "true")
         .saveAsTable(f"{CATALOG}.{SCHEMA}.{table}"))

write(chunks, "bronze_regulatory_chunks")
write(raw, "bronze_claims_raw")       # restricted: direct identifiers
write(labels, "eval_claims_labels")   # gold labels, kept apart from the claims

display(spark.table(f"{CATALOG}.{SCHEMA}.bronze_claims_raw").limit(5))
