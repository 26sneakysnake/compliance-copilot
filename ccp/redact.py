"""Anonymisation helpers applied before any text leaves the process or reaches
the silver layer.

Two operations:
- `redact(text)` replaces direct identifiers (emails, French and international
  phone numbers, IBANs, card-like numbers, French social security numbers,
  policy holder names after known cues) with typed placeholders;
- `pseudonymise(value)` replaces an identifier with a salted SHA-256 token so
  records can still be joined without exposing the identifier.

Adapted from the redaction step of clinical-notes-eval. This is a demo
safeguard, NOT a certified anonymisation: regexes miss free-text names,
addresses and indirect identifiers. Under the GDPR, pseudonymised data is still
personal data (Article 4(5)).
"""
from __future__ import annotations

import hashlib
import hmac
import re

from . import config

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL]"),
    (re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b"), "[IBAN]"),
    (re.compile(r"\b[12]\s?\d{2}\s?\d{2}\s?(?:\d{2}|2A|2B)\s?\d{3}\s?\d{3}(?:\s?\d{2})?\b"), "[NIR]"),
    (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[CARD]"),
    (re.compile(r"(?:\+33\s?|\b0)[1-9](?:[\s.-]?\d{2}){4}\b"), "[PHONE]"),
    (re.compile(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b(?:M\.|Mme|Mlle|Monsieur|Madame|Mr\.?|Mrs\.?|Ms\.?)\s+[A-ZÉÈ][\w'-]+(?:\s+[A-ZÉÈ][\w'-]+)?"), "[NAME]"),
    (re.compile(r"((?:Assuré|Assurée|Client|Cliente|Nom|Name|Policyholder)\s*:\s*)[A-ZÉÈ][\w'-]+(?:\s+[A-ZÉÈ][\w'-]+)+"), r"\1[NAME]"),
    (re.compile(r"\b\d{1,3}(?:\s?(?:bis|ter))?,?\s+(?:rue|avenue|boulevard|bd|chemin|allée|place|impasse)\s+[^,.\n]+", re.I), "[ADDRESS]"),
]

PLACEHOLDERS = ("[EMAIL]", "[IBAN]", "[NIR]", "[CARD]", "[PHONE]", "[NAME]", "[ADDRESS]")


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def pseudonymise(value: str, salt: str | None = None) -> str:
    key = (salt or config.PSEUDO_SALT).encode()
    return "psd_" + hmac.new(key, value.strip().lower().encode(), hashlib.sha256).hexdigest()[:16]


def contains_pii(text: str) -> bool:
    """True if any pattern still matches (used by data quality checks)."""
    return any(p.search(text) for p, _ in _PATTERNS)
