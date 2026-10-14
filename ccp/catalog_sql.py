"""Generate Unity Catalog SQL (Databricks) from the data contracts and access roles.

The same YAML files drive the local checks and the platform configuration:
- NOT NULL and CHECK constraints on Delta tables (enforced on every write),
- table and column comments (the documented catalog),
- tags for classification and personal data,
- GRANTs per role (least privilege).
Groups must exist in the workspace (Settings > Identity and access > Groups).
"""
from __future__ import annotations

import re

import yaml

from . import config
from .contracts import load_contract

GROUP_PREFIX = "ccp_"


def _q(s: str) -> str:
    return s.replace("'", "''")


def _ident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"unsafe identifier {name!r}")
    return f"`{name}`"


def table_name(contract: dict, catalog: str, schema: str) -> str:
    short = contract["tables"]["databricks"].split(".")[-1]
    return f"{catalog}.{schema}.{short}"


def constraints_sql(contract: dict, table: str) -> list[str]:
    out = []
    for f in contract["schema"]:
        col = _ident(f["name"])
        if f.get("required"):
            out.append(f"ALTER TABLE {table} ALTER COLUMN {col} SET NOT NULL")
        if "enum" in f:
            values = ", ".join(f"'{_q(str(v))}'" for v in f["enum"])
            out.append(f"ALTER TABLE {table} ADD CONSTRAINT {f['name']}_enum CHECK ({col} IN ({values}))")
        if "min" in f:
            out.append(f"ALTER TABLE {table} ADD CONSTRAINT {f['name']}_min CHECK ({col} >= {f['min']})")
        if "max" in f:
            out.append(f"ALTER TABLE {table} ADD CONSTRAINT {f['name']}_max CHECK ({col} <= {f['max']})")
    for rule in contract.get("quality", []):
        if rule["rule"] == "column_gte":
            l, r = _ident(rule["left"]), _ident(rule["right"])
            out.append(f"ALTER TABLE {table} ADD CONSTRAINT {rule['left']}_gte_{rule['right']} CHECK ({l} >= {r})")
    return out


def documentation_sql(contract: dict, table: str) -> list[str]:
    out = [f"COMMENT ON TABLE {table} IS '{_q(' '.join(contract['description'].split()))} "
           f"Owner: {_q(contract['owner'])}. Contract: {contract['id']} v{contract['version']}.'"]
    for f in contract["schema"]:
        desc = f.get("description") or f["name"].replace("_", " ")
        if f.get("pii"):
            desc += f" [personal data: {f['pii']}]"
        out.append(f"ALTER TABLE {table} ALTER COLUMN {_ident(f['name'])} COMMENT '{_q(desc)}'")
    tags = {"classification": contract["classification"],
            "contains_personal_data": str(contract.get("contains_personal_data", False)).lower(),
            "data_contract": f"{contract['id']}_v{contract['version']}",
            "synthetic": "true" if contract["id"].startswith("claims") else "false"}
    tag_list = ", ".join(f"'{k}' = '{_q(v)}'" for k, v in tags.items())
    out.append(f"ALTER TABLE {table} SET TAGS ({tag_list})")
    for f in contract["schema"]:
        if f.get("pii"):
            out.append(f"ALTER TABLE {table} ALTER COLUMN {_ident(f['name'])} SET TAGS ('pii' = '{f['pii']}')")
    return out


def grants_sql(catalog: str, schema: str) -> list[str]:
    roles = yaml.safe_load((config.GOVERNANCE / "access_roles.yaml").read_text())["roles"]
    out = []
    for role, spec in roles.items():
        group = f"`{GROUP_PREFIX}{role}`"
        out.append(f"GRANT USE CATALOG ON CATALOG {catalog} TO {group}")
        out.append(f"GRANT USE SCHEMA ON SCHEMA {catalog}.{schema} TO {group}")
        for table, privs in (spec.get("databricks") or {}).items():
            privs = [privs] if isinstance(privs, str) else privs
            out.append(f"GRANT {', '.join(privs)} ON TABLE {catalog}.{schema}.{_ident(table)} TO {group}")
    return out


def all_sql(catalog: str = "workspace", schema: str = "compliance_copilot") -> dict[str, list[str]]:
    out = {}
    for name in ("regulatory_chunks", "claims_raw", "claims_silver"):
        c = load_contract(name)
        t = table_name(c, catalog, schema)
        out[name] = constraints_sql(c, t) + documentation_sql(c, t)
    out["grants"] = grants_sql(catalog, schema)
    return out
