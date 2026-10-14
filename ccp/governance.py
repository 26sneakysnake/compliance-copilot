"""Risk register checks and rendering (governance as code)."""
from __future__ import annotations

from pathlib import Path

import yaml

from . import config
from .corpus import load_sample

REGISTER = config.GOVERNANCE / "risk_register.yaml"
OUTPUT = config.ROOT / "docs" / "risk_register.md"


def load_register(path: Path = REGISTER) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check_register(reg: dict | None = None) -> list[str]:
    reg = reg or load_register()
    known = {c.chunk_id for c in load_sample()}
    systems = {s["id"] for s in reg["systems"]}
    problems = []
    for s in reg["systems"]:
        for ref in s.get("regulatory_refs", []):
            if ref not in known:
                problems.append(f"{s['id']}: unknown regulatory reference {ref}")
    ids = set()
    for r in reg["risks"]:
        rid = r["id"]
        if rid in ids:
            problems.append(f"{rid}: duplicate id")
        ids.add(rid)
        if r["system"] not in systems:
            problems.append(f"{rid}: unknown system {r['system']}")
        for f in ("likelihood", "impact", "residual_likelihood", "residual_impact"):
            if not 1 <= int(r[f]) <= 5:
                problems.append(f"{rid}: {f} out of range")
        if r["residual_likelihood"] * r["residual_impact"] > r["likelihood"] * r["impact"]:
            problems.append(f"{rid}: residual risk higher than inherent risk")
        if not r.get("controls"):
            problems.append(f"{rid}: no control")
        for c in r.get("controls", []):
            for ev in c.get("evidence", []):
                if not (config.ROOT / ev).exists():
                    problems.append(f"{rid}: evidence not found: {ev}")
        for ref in r.get("regulatory_refs", []):
            if ref not in known:
                problems.append(f"{rid}: unknown regulatory reference {ref}")
    return problems


def _level(score: int) -> str:
    return "high" if score >= 15 else "medium" if score >= 8 else "low"


def render_register(reg: dict | None = None, out: Path = OUTPUT) -> Path:
    reg = reg or load_register()
    lines = [
        "# Risk register",
        "",
        f"Generated from `governance/risk_register.yaml` (v{reg['version']}, last review {reg['last_review']}). "
        "Do not edit by hand: run `python -m ccp.cli risk-register`.",
        "",
        "Fictional organisation, synthetic data. Scores are likelihood × impact on 1-5 scales "
        "(high ≥ 15, medium ≥ 8).",
        "",
        "## AI Act classification of the systems",
        "",
        "| System | Role | Classification | Rationale | References |",
        "|---|---|---|---|---|",
    ]
    for s in reg["systems"]:
        lines.append(f"| **{s['id']}** {s['name']} | {s['ai_act_role']} | {s['ai_act_classification']} | "
                     f"{' '.join(s['rationale'].split())} | {', '.join(s['regulatory_refs'])} |")
    lines += ["", "## Risks", "", "| ID | System | Risk | Inherent | Residual | Owner | Status | References |",
              "|---|---|---|---|---|---|---|---|"]
    for r in reg["risks"]:
        inh, res = r["likelihood"] * r["impact"], r["residual_likelihood"] * r["residual_impact"]
        lines.append(f"| {r['id']} | {r['system']} | **{r['title']}**: {r['description']} | {inh} ({_level(inh)}) | "
                     f"{res} ({_level(res)}) | {r['owner']} | {r['status']} | {', '.join(r['regulatory_refs'])} |")
    lines += ["", "## Controls and evidence", ""]
    for r in reg["risks"]:
        lines.append(f"### {r['id']} {r['title']}")
        lines.append("")
        for c in r["controls"]:
            ev = ", ".join(f"[`{e}`](../{e})" for e in c["evidence"])
            lines.append(f"- {c['description']} Evidence: {ev}")
        lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


CATALOG_OUT = config.ROOT / "docs" / "data_catalog.md"


def render_catalog(out: Path = CATALOG_OUT) -> Path:
    """Data catalog generated from the contracts and the access roles."""
    from .contracts import load_contract

    roles = yaml.safe_load((config.GOVERNANCE / "access_roles.yaml").read_text())["roles"]
    lines = ["# Data catalog", "",
             "Generated from `contracts/*.yaml` and `governance/access_roles.yaml` by "
             "`python -m ccp.cli risk-register`. Fictional organisation, synthetic data.", "",
             "| Dataset | Databricks table | Classification | Personal data | Owner | Contract |",
             "|---|---|---|---|---|---|"]
    contracts = [load_contract(p) for p in sorted(config.CONTRACTS.glob("*.yaml"))]
    for c in contracts:
        lines.append(f"| {c['id']} | `{c['tables']['databricks']}` | {c['classification']} | "
                     f"{c.get('contains_personal_data')} | {c['owner']} | v{c['version']} |")
    for c in contracts:
        lines += ["", f"## {c['id']}", "", " ".join(c["description"].split()), ""]
        if c.get("legal_basis"):
            lines.append(f"Legal basis: {c['legal_basis']}. ")
        lines.append(f"Retention: {c.get('retention', 'n/a')}.")
        lines += ["", "| Column | Type | Required | Rules | Personal data |", "|---|---|---|---|---|"]
        for f in c["schema"]:
            rules = [f"{k}={f[k]}" for k in ("enum", "pattern", "min", "max", "min_length", "equals") if k in f]
            if f.get("unique"):
                rules.append("unique")
            if f.get("no_pii"):
                rules.append("no personal data pattern")
            lines.append(f"| `{f['name']}` | {f['type']} | {'yes' if f.get('required') else 'no'} | "
                         f"{'; '.join(map(str, rules)).replace('|', '¦')} | {f.get('pii', '')} |")
        if c.get("forbidden_columns"):
            lines.append(f"\nForbidden columns: {', '.join(c['forbidden_columns'])}.")
    lines += ["", "## Access by role", "", "| Role | API permissions | Databricks privileges |", "|---|---|---|"]
    for role, spec in roles.items():
        db = "; ".join(f"{t}: {p if isinstance(p, str) else ', '.join(p)}" for t, p in (spec.get("databricks") or {}).items())
        lines.append(f"| {role} | {', '.join(spec.get('api', [])) or '-'} | {db} |")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
