# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Gold, catalog documentation and access control
# MAGIC
# MAGIC - `gold_claims_triage`: routing suggestions (never a rejection) for the anonymised claims
# MAGIC - `gold_eval_runs`: evaluation history of the copilot, for monitoring
# MAGIC - table/column comments and tags generated from the contracts (the documented catalog)
# MAGIC - GRANTs per role from `governance/access_roles.yaml`, and a column mask on raw identifiers
# MAGIC
# MAGIC Create the groups `ccp_analyst`, `ccp_claims_handler`, `ccp_auditor` and `ccp_data_engineer`
# MAGIC in the workspace settings first. Free Edition has a single user, so grants are demonstrative there.

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

import pandas as pd

from ccp.eval.metrics import score_triage
from ccp.triage import RulesTriage, decide

silver = spark.table(T("silver_claims")).toPandas()
reader = RulesTriage()
rows = []
for c in silver.to_dict("records"):
    category, urgency = reader.read(c["description_redacted"])
    d = decide(c, category, urgency)
    rows.append({"claim_id": c["claim_id"], "category": category, "urgency": urgency, "route": d.route,
                 "reasons": "; ".join(d.reasons), "signals": "; ".join(d.signals), "reader": reader.name})
gold = pd.DataFrame(rows)
spark.createDataFrame(gold).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(T("gold_claims_triage"))

labels = spark.table(T("eval_claims_labels")).toPandas().set_index("claim_id").loc[gold.claim_id].reset_index()
print(score_triage(gold.to_dict("records"), labels.to_dict("records")))

# COMMAND ----------

import datetime as dt
import json

from ccp.eval.run import run_rag

report = run_rag()
m = report["metrics"]["all"]
row = {"run_ts": dt.datetime.utcnow().isoformat(), "git_sha": report["git_sha"], "generator": report["generator"],
       "prompt_ref": report["prompt_ref"], **{k: float(v) for k, v in m.items() if isinstance(v, (int, float))}}
spark.createDataFrame(pd.DataFrame([row])).write.mode("append").option("mergeSchema", "true").saveAsTable(T("gold_eval_runs"))
spark.sql(f"CREATE TABLE IF NOT EXISTS {T('audit_log')} (ts STRING, event STRING, user STRING, role STRING, "
          "payload STRING, prev_hash STRING, hash STRING) COMMENT 'Hash-chained audit log exported from the API'")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Catalog documentation, tags and grants (generated from YAML)

# COMMAND ----------

from ccp.catalog_sql import all_sql

statements = all_sql(CATALOG, SCHEMA)
for name in ("regulatory_chunks", "claims_raw", "claims_silver"):
    for stmt in statements[name]:
        if " CONSTRAINT " in stmt or "SET NOT NULL" in stmt:
            continue  # constraints were added in notebook 02
        spark.sql(stmt)

for stmt in statements["grants"]:
    try:
        spark.sql(stmt)
    except Exception as exc:
        print("skipped (create the group first):", stmt, "|", str(exc).splitlines()[0][:120])

# COMMAND ----------

# Column mask: only data engineers see raw contact details in bronze.
spark.sql(f"""
CREATE OR REPLACE FUNCTION {T('mask_pii')}(v STRING)
RETURN CASE WHEN is_account_group_member('ccp_data_engineer') THEN v ELSE '***' END
""")
for col in ("customer_name", "customer_email", "customer_phone", "iban"):
    try:
        spark.sql(f"ALTER TABLE {T('bronze_claims_raw')} ALTER COLUMN {col} SET MASK {T('mask_pii')}")
    except Exception as exc:
        print("mask not applied on", col, "|", str(exc).splitlines()[0][:120])

display(spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}"))
