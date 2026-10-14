# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Silver: data contracts, quality gate and anonymisation
# MAGIC
# MAGIC Each table is validated against its YAML contract (`contracts/`) with Pandera **before** it is written.
# MAGIC A failing contract stops the notebook, so a Databricks Job built from these notebooks never publishes bad data.
# MAGIC The same contracts are then enforced inside Delta with NOT NULL and CHECK constraints.

# COMMAND ----------

# MAGIC %pip install pandera pyyaml
# MAGIC %restart_python

# COMMAND ----------

import os
import sys

REPO = os.path.dirname(os.getcwd())
sys.path.insert(0, REPO)
os.environ["CCP_ROOT"] = REPO
dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "compliance_copilot")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
T = lambda name: f"{CATALOG}.{SCHEMA}.{name}"  # noqa: E731

# COMMAND ----------

from ccp.catalog_sql import constraints_sql
from ccp.contracts import load_contract, validate
from ccp.pipeline import claims_to_silver

chunks = spark.table(T("bronze_regulatory_chunks")).toPandas()
raw = spark.table(T("bronze_claims_raw")).toPandas()

reports = [validate(chunks, "regulatory_chunks"), validate(raw, "claims_raw")]
silver = claims_to_silver(raw)
reports.append(validate(silver, "claims_silver"))
for r in reports:
    print(r.summary())
    for f in r.failures[:10]:
        print("   ", f)
assert all(r.passed for r in reports), "data contract violated: stopping before silver"

# COMMAND ----------

def write(df, table):
    (spark.createDataFrame(df).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(T(table)))

write(chunks, "silver_regulatory_chunks")
write(silver, "silver_claims")

# Delta constraints generated from the same contracts: every later write is checked by the platform too.
for name, table in (("regulatory_chunks", "silver_regulatory_chunks"), ("claims_silver", "silver_claims"),
                    ("claims_raw", "bronze_claims_raw")):
    for stmt in constraints_sql(load_contract(name), T(table)):
        try:
            spark.sql(stmt)
        except Exception as exc:  # constraint already present on re-runs
            if "already exists" not in str(exc):
                raise

# COMMAND ----------

# MAGIC %md
# MAGIC ### Quality metrics history
# MAGIC One row per run and per contract, so data quality can be monitored over time.

# COMMAND ----------

import datetime as dt

import pandas as pd

hist = pd.DataFrame([{"run_ts": dt.datetime.utcnow().isoformat(), "contract": r.contract_id,
                      "version": r.version, "rows": r.rows, "passed": r.passed,
                      "failures": len(r.failures)} for r in reports])
spark.createDataFrame(hist).write.mode("append").saveAsTable(T("quality_runs"))
display(spark.table(T("quality_runs")).orderBy("run_ts", ascending=False).limit(10))
