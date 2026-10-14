"""Data contracts (YAML) compiled into Pandera schemas, plus dataset-level rules.

A contract is the single source of truth for a table: types, constraints,
classification and owner. The same YAML drives the local pipeline, the tests,
and the Databricks notebooks, so a contract change shows up in code review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import yaml

from . import config
from .redact import contains_pii

_DTYPES = {
    "string": pa.String,
    "integer": pa.Int64,
    "float": pa.Float64,
    "boolean": pa.Bool,
    "date": pa.String,  # ISO dates kept as strings; parsed in a dedicated check
}


@dataclass
class ContractReport:
    contract_id: str
    version: str
    rows: int
    passed: bool
    failures: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        status = "PASS" if self.passed else f"FAIL ({len(self.failures)} issue(s))"
        return f"{self.contract_id} v{self.version}: {self.rows} rows, {status}"


def load_contract(name_or_path: str | Path) -> dict:
    p = Path(name_or_path)
    if not p.suffix:
        p = config.CONTRACTS / f"{name_or_path}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _is_iso_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%Y-%m-%d", errors="coerce").notna()


def to_pandera(contract: dict) -> pa.DataFrameSchema:
    columns = {}
    for f in contract["schema"]:
        checks = []
        if "enum" in f:
            checks.append(pa.Check.isin(f["enum"]))
        if "pattern" in f:
            checks.append(pa.Check.str_matches(f["pattern"]))
        if "min" in f:
            checks.append(pa.Check.ge(f["min"]))
        if "max" in f:
            checks.append(pa.Check.le(f["max"]))
        if "min_length" in f:
            checks.append(pa.Check.str_length(min_value=f["min_length"]))
        if "max_length" in f:
            checks.append(pa.Check.str_length(max_value=f["max_length"]))
        if "equals" in f:
            checks.append(pa.Check.eq(f["equals"]))
        if f["type"] == "date":
            checks.append(pa.Check(_is_iso_date, error="not an ISO date (YYYY-MM-DD)"))
        if f.get("no_pii"):
            checks.append(pa.Check(lambda s: ~s.map(contains_pii), error="personal data pattern found"))
        columns[f["name"]] = pa.Column(
            _DTYPES[f["type"]],
            checks=checks,
            nullable=not f.get("required", False),
            unique=f.get("unique", False),
            coerce=f["type"] in ("integer", "float"),
            required=True,
        )
    return pa.DataFrameSchema(columns, strict=False, name=contract["id"])


def _dataset_rules(contract: dict, df: pd.DataFrame) -> list[dict]:
    failures = []
    for col in contract.get("forbidden_columns", []):
        if col in df.columns:
            failures.append({"rule": "forbidden_column", "column": col})
    for rule in contract.get("quality", []):
        kind = rule["rule"]
        if kind == "row_count_min" and len(df) < rule["value"]:
            failures.append({"rule": kind, "expected": rule["value"], "actual": len(df)})
        elif kind == "regulations_present":
            missing = sorted(set(rule["value"]) - set(df.get("regulation", pd.Series(dtype=str))))
            if missing:
                failures.append({"rule": kind, "missing": missing})
        elif kind == "column_gte":
            left = pd.to_datetime(df[rule["left"]], errors="coerce")
            right = pd.to_datetime(df[rule["right"]], errors="coerce")
            bad = df.loc[left < right]
            if len(bad):
                failures.append({"rule": kind, "left": rule["left"], "right": rule["right"],
                                 "rows": bad.index.tolist()[:10], "count": len(bad)})
    return failures


def validate(df: pd.DataFrame, contract: dict | str) -> ContractReport:
    if isinstance(contract, str):
        contract = load_contract(contract)
    failures: list[dict] = []
    try:
        to_pandera(contract).validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        fc = exc.failure_cases
        for _, row in fc.head(50).iterrows():
            failures.append({"rule": "schema", "column": row.get("column"), "check": str(row.get("check")),
                             "value": None if pd.isna(row.get("failure_case")) else str(row.get("failure_case"))[:80]})
    failures += _dataset_rules(contract, df)
    return ContractReport(contract["id"], str(contract["version"]), len(df), not failures, failures)
