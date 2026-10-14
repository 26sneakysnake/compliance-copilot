"""Run the evaluation and apply the non-regression gate.

Results go to results/<name>.json (metrics) and results/<name>_errors.jsonl
(every failed item, for error analysis). The gate compares a run with
eval/thresholds.yaml (absolute floors) and with the committed baseline
(results/<name>.json at HEAD): a metric may not drop by more than the allowed
tolerance. CI runs the gate on every push and pull request.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pandas as pd
import yaml

from .. import config
from ..corpus import load_corpus
from ..pipeline import claims_to_silver
from ..rag import Copilot, LLMGenerator, load_settings
from ..synthetic import generate
from ..tracing import Tracer
from ..triage import RulesTriage, decide
from .metrics import aggregate, score_item, score_triage

RESULTS = config.ROOT / "results"


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return os.environ.get("GITHUB_SHA", "unknown")[:7]


def load_golden(path: Path | None = None) -> list[dict]:
    return yaml.safe_load((path or config.EVAL_DIR / "golden_set.yaml").read_text(encoding="utf-8"))["items"]


def run_rag(name: str = "rag_extractive", client=None, corpus: str = "sample", limit: int | None = None) -> dict:
    items = load_golden()[:limit] if limit else load_golden()
    copilot = Copilot(chunks=load_corpus(corpus), tracer=Tracer(enabled=False))
    generator = copilot.generator
    if client is not None:
        generator = LLMGenerator(client, copilot.prompt)
    copilot.generator = generator
    rows, answers = [], []
    for item in items:
        ans = copilot.ask(item["question"], user="eval", role="eval").to_dict()
        answers.append({"id": item["id"], **ans})
        rows.append(score_item(item, ans))
    report = {
        "name": name,
        "git_sha": _git_sha(),
        "corpus": corpus,
        "generator": getattr(generator, "model", "unknown"),
        "prompt_ref": copilot.prompt.ref,
        "prompt_sha": copilot.prompt.sha256,
        "settings": load_settings(),
        "golden_set_size": len(items),
        "metrics": {
            "all": aggregate(rows),
            "dev": aggregate([r for r in rows if r["split"] == "dev"]),
            "test": aggregate([r for r in rows if r["split"] == "test"]),
        },
    }
    _write(name, report, [dict(r, answer=a["answer"]) for r, a in zip(rows, answers) if not r["correct"]])
    return report


def run_triage(name: str = "triage_rules", reader=None, n: int = 300, seed: int = 11) -> dict:
    # seed 11 differs from the pipeline seed (7) so the rules are not scored on the data they were written against
    reader = reader or RulesTriage()
    claims = generate(n=n, seed=seed)
    silver = claims_to_silver(pd.DataFrame(claims))
    preds, errors = [], []
    for claim, (_, row) in zip(claims, silver.iterrows()):
        category, urgency = reader.read(row["description_redacted"])
        route = decide(claim, category, urgency).route
        preds.append({"category": category, "urgency": urgency, "route": route})
        if (category, urgency, route) != (claim["gold_category"], claim["gold_urgency"], claim["gold_route"]):
            errors.append({"claim_id": claim["claim_id"], "text": row["description_redacted"],
                           "pred": preds[-1], "gold": {k: claim[k] for k in ("gold_category", "gold_urgency", "gold_route")}})
    report = {"name": name, "git_sha": _git_sha(), "reader": reader.name, "seed": seed,
              "metrics": score_triage(preds, claims)}
    _write(name, report, errors)
    return report


def _write(name: str, report: dict, errors: list[dict]) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (RESULTS / f"{name}_errors.jsonl").write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in errors), encoding="utf-8")


def _flatten(metrics: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in metrics.items():
        if isinstance(v, dict):
            out.update(_flatten(v, f"{prefix}{k}."))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[f"{prefix}{k}"] = v
    return out


def gate(report: dict, thresholds: dict, baseline: dict | None = None) -> list[str]:
    """Return the list of violations (empty list = pass)."""
    spec = thresholds.get(report["name"], {})
    flat = _flatten(report["metrics"])
    problems = []
    for metric, floor in spec.get("min", {}).items():
        v = flat.get(metric)
        if v is None or v < floor:
            problems.append(f"{metric} = {v} is below the floor {floor}")
    for metric, ceiling in spec.get("max", {}).items():
        v = flat.get(metric)
        if v is None or v > ceiling:
            problems.append(f"{metric} = {v} is above the ceiling {ceiling}")
    if baseline:
        tol = spec.get("regression_tolerance", 0.0)
        base = _flatten(baseline["metrics"])
        for metric in spec.get("no_regression", []):
            if metric in base and metric in flat and flat[metric] < base[metric] - tol:
                problems.append(f"{metric} regressed: {base[metric]} -> {flat[metric]} (tolerance {tol})")
    return problems
