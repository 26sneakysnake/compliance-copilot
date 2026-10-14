"""Command line entry point: `python -m ccp.cli <command>` (or `ccp <command>` once installed)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

from . import config


def _baseline(name: str, ref: str | None) -> dict | None:
    rel = f"results/{name}.json"
    if ref:
        try:
            out = subprocess.check_output(["git", "show", f"{ref}:{rel}"], cwd=config.ROOT,
                                          stderr=subprocess.DEVNULL, text=True)
            return json.loads(out)
        except Exception:
            print(f"[gate] no baseline at {ref}:{rel}, using the working copy", file=sys.stderr)
    path = config.ROOT / rel
    return json.loads(path.read_text()) if path.exists() else None


def cmd_pipeline(a):
    from .pipeline import QualityGateError, run

    try:
        reports = run(n=a.n, seed=a.seed)
    except QualityGateError as exc:
        print(f"QUALITY GATE FAILED\n{exc}")
        return 1
    for r in reports.values():
        print(r.summary())
    return 0


def cmd_fetch(a):
    from .eurlex import ACTS, build

    for reg in a.regulation or list(ACTS):
        out = build(reg, config.OFFICIAL_CORPUS_DIR, lang=a.lang, html_file=Path(a.html_file) if a.html_file else None)
        print(f"{reg}: wrote {out}")
    return 0


def _client(a):
    if a.generator == "extractive":
        return None
    from .llm import make_client

    return make_client(a.generator, a.model, a.base_url)


def cmd_ask(a):
    from .audit import AuditLog
    from .rag import Copilot, LLMGenerator
    from .tracing import Tracer

    cop = Copilot(tracer=Tracer(), audit=AuditLog())
    if (client := _client(a)) is not None:
        cop.generator = LLMGenerator(client, cop.prompt)
    ans = cop.ask(" ".join(a.question), user="cli", role="analyst")
    print(json.dumps(ans.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_eval(a):
    from .eval.run import gate, run_rag, run_triage

    thresholds = yaml.safe_load((config.EVAL_DIR / "thresholds.yaml").read_text())
    status = 0
    targets = ["rag", "triage"] if a.target == "all" else [a.target]
    for target in targets:
        if target == "rag":
            name = "rag_extractive" if a.generator == "extractive" else "rag_llm"
            baseline = _baseline(name, a.baseline_ref)
            report = run_rag(name=name, client=_client(a), corpus=a.corpus, limit=a.limit)
        else:
            name = "triage_rules"
            baseline = _baseline(name, a.baseline_ref)
            report = run_triage(name=name)
        print(json.dumps({"name": name, "metrics": report["metrics"].get("all", report["metrics"])}, indent=2))
        if a.gate:
            problems = gate(report, thresholds, baseline)
            if problems:
                status = 1
                print(f"[gate] {name}: FAIL")
                for p in problems:
                    print(f"  - {p}")
            else:
                print(f"[gate] {name}: PASS")
    return status


def cmd_audit(a):
    from .audit import AuditLog

    ok, idx = AuditLog().verify()
    print("audit chain OK" if ok else f"audit chain BROKEN at entry {idx}")
    return 0 if ok else 1


def cmd_traces(a):
    from .tracing import summarize

    print(json.dumps(summarize(last=a.last), indent=2))
    return 0


def cmd_risks(a):
    from .governance import check_register, render_catalog, render_register

    problems = check_register()
    if problems:
        print("\n".join(problems))
        return 1
    print(f"risk register OK, wrote {render_register()} and {render_catalog()}")
    return 0


def cmd_serve(a):
    import uvicorn

    uvicorn.run("ccp.api:app", host=a.host, port=a.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ccp", description="Compliance copilot (synthetic data, fictional bank)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("pipeline", help="build bronze/silver data and enforce data contracts")
    s.add_argument("--n", type=int, default=300)
    s.add_argument("--seed", type=int, default=7)
    s.set_defaults(func=cmd_pipeline)

    s = sub.add_parser("fetch-official", help="download official texts from EUR-Lex")
    s.add_argument("--regulation", action="append", choices=["AI_ACT", "GDPR", "DORA"])
    s.add_argument("--lang", default="EN")
    s.add_argument("--html-file", help="parse a locally saved EUR-Lex HTML file instead of downloading")
    s.set_defaults(func=cmd_fetch)

    for name, func in (("ask", cmd_ask), ("eval", cmd_eval)):
        s = sub.add_parser(name)
        s.add_argument("--generator", default="extractive", choices=["extractive", "anthropic", "openai-compat"])
        s.add_argument("--model")
        s.add_argument("--base-url")
        s.set_defaults(func=func)
        if name == "ask":
            s.add_argument("question", nargs="+")
        else:
            s.add_argument("--target", default="all", choices=["all", "rag", "triage"])
            s.add_argument("--corpus", default="sample", choices=["sample", "official"])
            s.add_argument("--limit", type=int)
            s.add_argument("--gate", action="store_true", help="fail on threshold or regression violations")
            s.add_argument("--baseline-ref", help="git ref holding the baseline results, e.g. origin/main")

    sub.add_parser("audit-verify", help="verify the audit log hash chain").set_defaults(func=cmd_audit)
    s = sub.add_parser("traces", help="latency, cost and refusal summary from logs/traces.jsonl")
    s.add_argument("--last", type=int)
    s.set_defaults(func=cmd_traces)
    sub.add_parser("risk-register", help="validate and render governance/risk_register.yaml").set_defaults(func=cmd_risks)
    s = sub.add_parser("serve", help="run the API locally")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
