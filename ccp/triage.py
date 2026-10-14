"""Claims triage for FICTIONAL property & casualty claims.

Two steps, same split as clinical-notes-eval:
1. read the free-text description into (category, urgency), with a rules
   baseline or an LLM (redacted input, strict validation, one retry);
2. apply a written, deterministic routing policy.

Design rule: the system NEVER rejects a claim and NEVER decides on an
indemnity. It routes to `fast_track`, `standard` or `human_review`, and every
route is a queue handled by a person. This keeps the use case outside
GDPR Article 22 (no decision based solely on automated processing) and outside
AI Act Annex III point 5(c), which only covers life and health insurance.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from .redact import redact

CATEGORIES = ("collision", "theft", "water_damage", "fire", "liability", "travel", "other")
URGENCIES = ("low", "normal", "high")
ROUTES = ("fast_track", "standard", "human_review")

FAST_TRACK_MAX_EUR = 1500
HIGH_AMOUNT_EUR = 10000
LATE_REPORT_DAYS = 30
NEW_POLICY_DAYS = 30


@dataclass(frozen=True)
class TriageDecision:
    route: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    signals: tuple[str, ...] = field(default_factory=tuple)


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def signals(claim: dict) -> list[str]:
    """Signals that call for a human look. They are not accusations of fraud."""
    out = []
    if _days(claim["incident_date"], claim["report_date"]) > LATE_REPORT_DAYS:
        out.append(f"reported more than {LATE_REPORT_DAYS} days after the incident")
    if _days(claim["policy_start_date"], claim["incident_date"]) < NEW_POLICY_DAYS:
        out.append(f"incident less than {NEW_POLICY_DAYS} days after policy start")
    if float(claim["amount_claimed_eur"]) > HIGH_AMOUNT_EUR:
        out.append(f"amount above {HIGH_AMOUNT_EUR} EUR")
    return out


def decide(claim: dict, category: str | None, urgency: str | None) -> TriageDecision:
    sig = tuple(signals(claim))
    if category in (None, "other"):
        return TriageDecision("human_review", ("category not identified",), sig)
    if urgency is None:
        return TriageDecision("human_review", ("urgency not identified",), sig)
    if urgency == "high":
        return TriageDecision("human_review", ("high urgency: bodily injury or uninhabitable home",), sig)
    if sig:
        return TriageDecision("human_review", ("review signals present",), sig)
    if float(claim["amount_claimed_eur"]) <= FAST_TRACK_MAX_EUR and urgency == "low":
        return TriageDecision("fast_track", (f"low urgency and amount <= {FAST_TRACK_MAX_EUR} EUR",), sig)
    return TriageDecision("standard", ("no signal, standard handling",), sig)


# --------------------------------------------------------------------------- #
# Readers: description -> (category, urgency)
# --------------------------------------------------------------------------- #
_CATEGORY_RULES = [
    ("fire", r"incendie|feu|brûl"),
    ("water_damage", r"dégât des eaux|fuite|inondation|infiltration"),
    ("theft", r"\bvol\b|volé|cambriolage|dérob"),
    ("travel", r"voyage|bagage|séjour|rapatriement|vol retour|compagnie aérienne"),
    ("collision", r"accrochage|collision|accident|choc|constat"),
    ("liability", r"voisin|passant|client a glissé|réclame|demande réparation|mordu"),
]
_HIGH = re.compile(r"(?<!pas de )(?<!aucun )bless|hospitalis|inhabitable|rapatriement|urgence|mordu", re.I)
_LOW = re.compile(r"rétroviseur|taché|bagage perdu|vitre|ordinateur portable|pas de blessé", re.I)


class RulesTriage:
    name = "rules"

    def read(self, description: str) -> tuple[str, str]:
        low = description.lower()
        # "vol retour" (flight) must not trigger theft: check travel cues first
        category = "other"
        if re.search(r"vol retour|compagnie aérienne", low):
            category = "travel"
        else:
            for cat, rx in _CATEGORY_RULES:
                if re.search(rx, low):
                    category = cat
                    break
        if _HIGH.search(low) and "pas de blessé" not in low and "aucun blessé" not in low:
            urgency = "high"
        elif _LOW.search(low):
            urgency = "low"
        else:
            urgency = "normal"
        return category, urgency


TRIAGE_PROMPT_ID = "claims_triage"


class LLMTriage:
    """Reads the description with an LLM. Input is redacted first."""

    name = "llm"

    def __init__(self, client, prompt, max_retries: int = 1):
        self.client = client
        self.prompt = prompt
        self.max_retries = max_retries
        self.failures = 0

    def read(self, description: str) -> tuple[str | None, str | None]:
        text = redact(description)
        for _ in range(self.max_retries + 1):
            out = self.client.complete(self.prompt.system, self.prompt.render(description=text))
            try:
                start, end = out.text.find("{"), out.text.rfind("}")
                data = json.loads(out.text[start : end + 1])
                cat, urg = data.get("category"), data.get("urgency")
                if cat in CATEGORIES and urg in URGENCIES:
                    return cat, urg
            except (ValueError, json.JSONDecodeError):
                pass
        self.failures += 1
        return None, None  # unreadable output -> human review, never a guess


def triage(claim: dict, reader) -> dict:
    category, urgency = reader.read(claim["description"])
    d = decide(claim, category, urgency)
    return {
        "claim_id": claim["claim_id"],
        "category": category,
        "urgency": urgency,
        "route": d.route,
        "reasons": list(d.reasons),
        "signals": list(d.signals),
        "reader": reader.name,
    }
