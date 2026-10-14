"""HTTP API (FastAPI).

Authentication: an `X-API-Key` header mapped to a role. Keys come from the
CCP_API_KEYS environment variable ("key1:analyst,key2:auditor"). For the public
demo, CCP_DEMO_KEYS=1 enables the documented keys demo-analyst, demo-claims and
demo-auditor. Permissions per role are read from governance/access_roles.yaml.

Every response carries `X-AI-Generated: true`, and answers carry a disclaimer,
in line with the transparency logic of AI Act Article 50.
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache

import yaml
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from . import __version__, config
from .audit import AuditLog
from .rag import Copilot, LLMGenerator
from .tracing import Tracer, setup_otel, summarize
from .triage import RulesTriage, decide

DEMO_KEYS = {"demo-analyst": "analyst", "demo-claims": "claims_handler", "demo-auditor": "auditor"}


@lru_cache(maxsize=1)
def permissions() -> dict[str, set[str]]:
    raw = yaml.safe_load((config.GOVERNANCE / "access_roles.yaml").read_text())
    return {role: set(spec.get("api", [])) for role, spec in raw["roles"].items()}


def api_keys() -> dict[str, str]:
    keys = {}
    for pair in filter(None, os.environ.get("CCP_API_KEYS", "").split(",")):
        key, _, role = pair.partition(":")
        keys[key.strip()] = role.strip()
    if os.environ.get("CCP_DEMO_KEYS") == "1":
        keys.update(DEMO_KEYS)
    return keys


class Principal(BaseModel):
    user: str
    role: str


_api_key = APIKeyHeader(name="X-API-Key", auto_error=False, description="Demo keys: demo-analyst, demo-claims, demo-auditor")


def principal(x_api_key: str | None = Security(_api_key)) -> Principal:
    role = api_keys().get(x_api_key or "")
    if not role:
        raise HTTPException(401, "missing or unknown X-API-Key")
    # the user id is a hash of the key: no personal identifier is stored
    return Principal(user="key_" + hashlib.sha256(x_api_key.encode()).hexdigest()[:10], role=role)


def require(permission: str):
    def dep(p: Principal = Depends(principal)) -> Principal:
        if permission not in permissions().get(p.role, set()):
            raise HTTPException(403, f"role {p.role!r} is not allowed to {permission}")
        return p

    return dep


def build_copilot() -> Copilot:
    setup_otel()
    cop = Copilot(tracer=Tracer(), audit=AuditLog())
    if config.GENERATOR != "extractive":
        from .llm import make_client

        cop.generator = LLMGenerator(make_client(config.GENERATOR, config.DEFAULT_MODEL), cop.prompt)
    return cop


app = FastAPI(
    title="Compliance Copilot (fictional bank, synthetic data)",
    version=__version__,
    description="RAG over the EU AI Act, DORA, GDPR and EBA guidelines, with citations, refusal without "
    "source, audit log and monitoring. Not legal advice. All claims data is synthetic.",
)
_state: dict = {}


def copilot() -> Copilot:
    if "copilot" not in _state:
        _state["copilot"] = build_copilot()
    return _state["copilot"]


@app.middleware("http")
async def ai_disclosure(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-AI-Generated"] = "true"
    response.headers["X-Data-Notice"] = "synthetic-and-fictional"
    return response


class AskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class ClaimIn(BaseModel):
    claim_id: str = Field(..., pattern=r"^CLM-\d{4}-\d{6}$")
    description: str = Field(..., min_length=5, max_length=5000)
    amount_claimed_eur: float = Field(..., ge=0)
    policy_start_date: str
    incident_date: str
    report_date: str


@app.get("/")
def root():
    return {
        "service": "compliance-copilot",
        "version": __version__,
        "notice": "You are interacting with an AI system. Answers are generated from cited passages and are "
        "not legal advice. All organisations are fictional and all claims data is synthetic.",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    cop = copilot()
    return {"status": "ok", "chunks": len(cop.chunks), "generator": getattr(cop.generator, "model", "?"),
            "prompt": cop.prompt.ref, "corpus_types": sorted({c.text_type for c in cop.chunks})}


@app.post("/ask")
def ask(body: AskIn, p: Principal = Depends(require("ask"))):
    return copilot().ask(body.question, user=p.user, role=p.role).to_dict()


@app.post("/triage")
def triage_claim(body: ClaimIn, p: Principal = Depends(require("triage"))):
    cop = copilot()
    claim = body.model_dump()
    with cop.tracer.trace("triage", reader="rules") as tr:
        category, urgency = RulesTriage().read(claim["description"])
        try:
            d = decide(claim, category, urgency)
        except ValueError as exc:
            raise HTTPException(422, f"invalid date: {exc}")
        tr.set(route=d.route, category=category, urgency=urgency, cost_usd=0.0)
    out = {"claim_id": claim["claim_id"], "category": category, "urgency": urgency, "route": d.route,
           "reasons": list(d.reasons), "signals": list(d.signals),
           "notice": "Routing suggestion only. A claims handler decides; the system never rejects a claim."}
    if cop.audit:
        cop.audit.record("triage", user=p.user, role=p.role, trace_id=tr.trace_id, claim_id=claim["claim_id"],
                         route=d.route, signals=list(d.signals))
    return out


@app.get("/audit")
def audit(limit: int = 50, p: Principal = Depends(require("read_audit"))):
    log = copilot().audit
    ok, broken_at = log.verify()
    return {"chain_ok": ok, "broken_at": broken_at, "entries": log.entries(limit=min(limit, 500))}


@app.get("/metrics")
def metrics(last: int | None = None, p: Principal = Depends(require("read_metrics"))):
    return summarize(copilot().tracer.path, last=last)
