"""Local medallion pipeline (bronze -> silver), mirrored by the Databricks notebooks.

bronze: raw synthetic claims (restricted) and regulatory chunks, validated against contracts
silver: anonymised claims (no direct identifiers, redacted text) and validated chunks
labels: gold labels kept apart from the claims, used only by the evaluation

Every step validates its output against the matching data contract and stops
the run on failure: bad data never reaches the copilot.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from . import config
from .contracts import ContractReport, validate
from .corpus import load_corpus
from .redact import pseudonymise, redact
from .synthetic import generate, write_jsonl

LABEL_COLUMNS = ["gold_category", "gold_urgency", "gold_route"]


class QualityGateError(RuntimeError):
    def __init__(self, report: ContractReport):
        super().__init__(report.summary() + "\n" + "\n".join(map(str, report.failures[:10])))
        self.report = report


def _check(df: pd.DataFrame, contract: str) -> ContractReport:
    report = validate(df, contract)
    if not report.passed:
        raise QualityGateError(report)
    return report


def claims_to_silver(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "claim_id": raw["claim_id"],
            "customer_pseudo_id": raw["customer_email"].map(pseudonymise),
            "line_of_business": raw["line_of_business"],
            "channel": raw["channel"],
            "policy_start_date": raw["policy_start_date"],
            "incident_date": raw["incident_date"],
            "report_date": raw["report_date"],
            "report_delay_days": [
                (date.fromisoformat(r) - date.fromisoformat(i)).days
                for i, r in zip(raw["incident_date"], raw["report_date"])
            ],
            "amount_claimed_eur": raw["amount_claimed_eur"].astype(float),
            "description_redacted": raw["description"].map(redact),
            "is_synthetic": raw["is_synthetic"].astype(bool),
        }
    )
    return out


def run(n: int = 300, seed: int = 7, out_dir: Path | None = None) -> dict[str, ContractReport]:
    out_dir = out_dir or config.SILVER_DIR
    reports: dict[str, ContractReport] = {}

    chunks = pd.DataFrame([c.to_dict() for c in load_corpus()])
    reports["regulatory_chunks"] = _check(chunks, "regulatory_chunks")

    claims = generate(n=n, seed=seed)
    raw = pd.DataFrame(claims)
    write_jsonl([{k: v for k, v in c.items() if k not in LABEL_COLUMNS} for c in claims],
                config.CLAIMS_DIR / "raw_claims.jsonl")
    reports["claims_raw"] = _check(raw.drop(columns=LABEL_COLUMNS), "claims_raw")

    silver = claims_to_silver(raw)
    reports["claims_silver"] = _check(silver, "claims_silver")

    out_dir.mkdir(parents=True, exist_ok=True)
    chunks.to_json(out_dir / "regulatory_chunks.jsonl", orient="records", lines=True, force_ascii=False)
    silver.to_json(out_dir / "claims.jsonl", orient="records", lines=True, force_ascii=False)
    raw[["claim_id", *LABEL_COLUMNS]].to_json(out_dir / "claims_labels.jsonl", orient="records", lines=True)
    return reports
