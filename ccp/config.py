"""Paths and settings, overridable through environment variables."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("CCP_ROOT", Path(__file__).resolve().parent.parent))

DATA = ROOT / "data"
SAMPLE_CORPUS = DATA / "corpus" / "sample_corpus.yaml"
OFFICIAL_CORPUS_DIR = DATA / "corpus" / "official"
CLAIMS_DIR = DATA / "claims"
SILVER_DIR = DATA / "silver"

CONTRACTS = ROOT / "contracts"
PROMPTS = ROOT / "prompts"
GOVERNANCE = ROOT / "governance"
EVAL_DIR = ROOT / "eval"

LOG_DIR = Path(os.environ.get("CCP_LOG_DIR", ROOT / "logs"))
TRACE_FILE = LOG_DIR / "traces.jsonl"
AUDIT_FILE = LOG_DIR / "audit.jsonl"

# Which corpus the copilot answers from: "sample" (paraphrased, committed) or
# "official" (fetched from EUR-Lex, see ccp/eurlex.py). "auto" uses official if present.
CORPUS = os.environ.get("CCP_CORPUS", "auto")

# Generator: "extractive" (offline, deterministic, free) or "anthropic" / "openai-compat".
GENERATOR = os.environ.get("CCP_GENERATOR", "extractive")
DEFAULT_MODEL = os.environ.get("CCP_MODEL", "claude-haiku-5-5")

# Salt for pseudonymising customer identifiers. Set a real secret in production.
PSEUDO_SALT = os.environ.get("CCP_PSEUDO_SALT", "demo-salt-not-secret")
