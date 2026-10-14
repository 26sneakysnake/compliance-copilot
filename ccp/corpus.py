"""Regulatory corpus: loading, chunk identifiers and citation labels."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from . import config

REGULATION_LABELS = {
    "AI_ACT": "EU AI Act (Regulation (EU) 2024/1689)",
    "AI_ACT_OMNIBUS": "Digital Omnibus on AI (Regulation (EU) 2026/1744)",
    "GDPR": "GDPR (Regulation (EU) 2016/679)",
    "DORA": "DORA (Regulation (EU) 2022/2554)",
    "EBA_GL_ICT": "EBA Guidelines on ICT and security risk management (EBA/GL/2019/04)",
    "EBA_GL_OUTSOURCING": "EBA Guidelines on outsourcing arrangements (EBA/GL/2019/02)",
}

EBA_URLS = {
    "EBA_GL_ICT": "https://www.eba.europa.eu/legacy/regulation-and-policy/internal-governance/guidelines-ict-and-security-risk-management",
    "EBA_GL_OUTSOURCING": "https://www.eba.europa.eu/legacy/regulation-and-policy/internal-governance/guidelines-outsourcing-arrangements",
}

CHUNK_ID_RE = re.compile(r"^[A-Z][A-Z_]+-[a-z0-9]+(?:-[a-z0-9]+)*$")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def make_chunk_id(regulation: str, article: str, part: int | None = None) -> str:
    cid = f"{regulation}-{slug(article)}"
    return f"{cid}-p{part}" if part else cid


def source_url(regulation: str, celex: str, article: str) -> str:
    if regulation in EBA_URLS:
        return EBA_URLS[regulation]
    base = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
    return f"{base}#art_{article}" if article.isdigit() else base


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    regulation: str
    celex: str
    article: str
    title: str
    text: str
    source_url: str
    text_type: str  # "paraphrase" (sample corpus) or "official" (EUR-Lex)
    language: str = "en"

    @property
    def label(self) -> str:
        reg = self.regulation.replace("_", " ")
        prefix = "Art. " if self.article[:1].isdigit() else ""
        return f"{reg} {prefix}{self.article}"

    def to_dict(self) -> dict:
        return asdict(self)


def load_sample(path: Path = config.SAMPLE_CORPUS) -> list[Chunk]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    chunks = []
    for doc in raw["documents"]:
        reg, celex = doc["regulation"], str(doc["celex"])
        for art in doc["articles"]:
            article = str(art["article"])
            chunks.append(
                Chunk(
                    chunk_id=make_chunk_id(reg, article),
                    regulation=reg,
                    celex=celex,
                    article=article,
                    title=art["title"].strip(),
                    text=" ".join(art["text"].split()),
                    source_url=source_url(reg, celex, article),
                    text_type="paraphrase",
                )
            )
    return chunks


def load_official(directory: Path = config.OFFICIAL_CORPUS_DIR) -> list[Chunk]:
    chunks = []
    for f in sorted(directory.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunks.append(Chunk(**json.loads(line)))
    return chunks


def load_corpus(mode: str | None = None) -> list[Chunk]:
    mode = mode or config.CORPUS
    if mode == "official":
        chunks = load_official()
        if not chunks:
            raise FileNotFoundError("no official corpus found: run `ccp fetch-official` first")
        return chunks
    if mode == "auto":
        return load_official() or load_sample()
    return load_sample()


def by_id(chunks: list[Chunk]) -> dict[str, Chunk]:
    return {c.chunk_id: c for c in chunks}
