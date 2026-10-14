"""Lexical retrieval with BM25 (Okapi), standard library only.

Why BM25 and not embeddings by default: it is deterministic, needs no API key
and no GPU, runs in CI in milliseconds, and regulatory questions are rich in
exact terms ("72 hours", "DPIA", "TLPT", "Annex III"). An embedding retriever
can be plugged in behind the same `search` interface; the evaluation decides
whether it earns its cost.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .corpus import Chunk

STOPWORDS = set(
    """a an and are as at be by can do does for from has have how i if in into is it its may
    must not of on or our shall should so such that the their them then there these this to under
    was we what when where which who why will with within would you your about any all also than
    us""".split()
)

# Small domain synonym map: user wording -> corpus wording. Kept explicit and reviewable.
SYNONYMS = {
    "gdpr": ["personal", "data"],
    "rgpd": ["gdpr", "personal", "data"],
    "dpia": ["impact", "assessment", "data", "protection"],
    "aipd": ["impact", "assessment", "data", "protection"],
    "fria": ["fundamental", "rights", "impact", "assessment"],
    "breach": ["breach", "notification"],
    "fine": ["fines", "penalties"],
    "fines": ["penalties"],
    "sanction": ["fines", "penalties"],
    "sanctions": ["fines", "penalties"],
    "logs": ["logging", "record", "keeping"],
    "outsourcing": ["third", "party", "contractual"],
    "cloud": ["ict", "third", "party", "provider"],
    "pentest": ["penetration", "testing", "tlpt"],
    "watermark": ["machine", "readable", "marking"],
    "deepfake": ["deep", "fakes"],
    "chatbot": ["interact", "directly", "natural", "persons"],
    "insurer": ["insurance"],
    "bank": ["credit", "institutions", "financial", "entities"],
    "banks": ["credit", "institutions", "financial", "entities"],
}


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def _stem(tok: str) -> str:
    for suf in ("ings", "ing", "ies", "es", "s"):
        if len(tok) > len(suf) + 3 and tok.endswith(suf):
            return tok[: -len(suf)] + ("y" if suf == "ies" else "")
    return tok


def analyze(text: str, expand: bool = False) -> list[str]:
    toks = tokenize(text)
    if expand:
        toks = toks + [s for t in toks for s in SYNONYMS.get(t, [])]
    return [_stem(t) for t in toks]


_REG_MENTIONS = {
    "GDPR": r"\b(gdpr|rgpd)\b",
    "DORA": r"\bdora\b",
    "AI_ACT": r"\b(ai act|artificial intelligence act|omnibus)\b",
    "EBA": r"\beba\b",
}


def mentioned_regulations(query: str) -> set[str]:
    """Regulations explicitly named in the question, used as a retrieval filter."""
    low = query.lower()
    regs = set()
    for reg, rx in _REG_MENTIONS.items():
        if re.search(rx, low):
            regs |= {"AI_ACT", "AI_ACT_OMNIBUS"} if reg == "AI_ACT" else (
                {"EBA_GL_ICT", "EBA_GL_OUTSOURCING"} if reg == "EBA" else {reg})
    return regs


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    matched_terms: tuple[str, ...]


class BM25Retriever:
    def __init__(self, chunks: list[Chunk], k1: float = 1.4, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        # title and regulation name are indexed with the text (title counted twice)
        self.docs = [
            analyze(f"{c.regulation.replace('_', ' ')} article {c.article} {c.title} {c.title} {c.text}")
            for c in chunks
        ]
        self.tf = [Counter(d) for d in self.docs]
        self.avgdl = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 4) -> list[Hit]:
        q = analyze(query, expand=True)
        regs = mentioned_regulations(query)
        scored = []
        for i, tf in enumerate(self.tf):
            if regs and self.chunks[i].regulation not in regs:
                continue  # metadata filter: the question names a regulation
            dl = len(self.docs[i])
            score, matched = 0.0, []
            for t in set(q):
                if t not in tf:
                    continue
                f = tf[t]
                score += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                matched.append(t)
            if score > 0:
                scored.append(Hit(self.chunks[i], round(score, 4), tuple(sorted(matched))))
        scored.sort(key=lambda h: (-h.score, h.chunk.chunk_id))
        return scored[:k]

    def term_weight(self, term: str) -> float:
        return self.idf.get(term, 0.0)

    def query_coverage(self, query: str, hits: list[Hit]) -> float:
        """Share of distinct (non-expanded) query terms found in the retrieved chunks."""
        q = set(analyze(query))
        if not q:
            return 0.0
        found = set().union(*(set(h.matched_terms) for h in hits)) if hits else set()
        return len(q & found) / len(q)
