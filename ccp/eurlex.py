"""Fetch official regulation texts from EUR-Lex and split them into article chunks.

EUR-Lex publishes acts as HTML in which each article sits in a
`<div class="eli-subdivision" id="art_N">`, with the heading in an element of
class `oj-ti-art` / `ti-art` and the article title in `oj-sti-art` / `sti-art`.
The parser relies only on those markers and the standard library.

EUR-Lex content may be reused with acknowledgement of the source (Commission
Decision 2011/833/EU). Only the official texts are authentic; this tool keeps a
link to the source for every chunk.

The parser is tested on a fixture that mimics EUR-Lex markup. If EUR-Lex
returns an anti-bot page instead of the act, download the HTML in a browser and
pass it with --html-file.
"""
from __future__ import annotations

import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from .corpus import Chunk, make_chunk_id, source_url

ACTS = {
    "AI_ACT": "32024R1689",
    "GDPR": "32016R0679",
    "DORA": "32022R2554",
}

HTML_URL = "https://eur-lex.europa.eu/legal-content/{lang}/TXT/HTML/?uri=CELEX:{celex}"
_ART_ID = re.compile(r"^art_(\d+[a-z]?)$")
_BLOCK_TAGS = {"p", "div", "td", "li", "tr", "table"}
_VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "col", "wbr", "area", "base", "source"}


class _ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.articles: list[dict] = []
        self._stack: list[tuple[str, bool]] = []  # (tag, opens_article)
        self._current: dict | None = None
        self._mode: str | None = None  # "heading" | "title" | None
        self._mode_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _VOID_TAGS:
            return
        attrs = dict(attrs)
        opens = False
        if tag == "div" and self._current is None and (m := _ART_ID.match(attrs.get("id") or "")):
            self._current = {"article": m.group(1), "title": "", "parts": [""]}
            opens = True
        self._stack.append((tag, opens))
        if self._current is None:
            return
        cls = attrs.get("class") or ""
        if re.search(r"\b(oj-)?sti-art\b", cls):
            self._mode, self._mode_depth = "title", len(self._stack)
        elif re.search(r"\b(oj-)?ti-art\b", cls):
            self._mode, self._mode_depth = "heading", len(self._stack)
        if tag in _BLOCK_TAGS and self._current["parts"][-1].strip():
            self._current["parts"].append("")

    def handle_endtag(self, tag):
        if tag in _VOID_TAGS or all(t != tag for t, _ in self._stack):
            return  # stray end tag: ignore rather than unwind the stack
        # pop to the matching tag (EUR-Lex HTML is mostly well formed)
        while self._stack:
            t, opens = self._stack.pop()
            if self._mode and len(self._stack) < self._mode_depth:
                self._mode = None
            if opens and self._current is not None:
                self._finish()
            if t == tag:
                break

    def handle_data(self, data):
        if self._current is None:
            return
        if self._mode == "heading":
            return
        if self._mode == "title":
            self._current["title"] += data
            return
        self._current["parts"][-1] += data

    def _finish(self):
        cur = self._current
        paras = [" ".join(p.split()) for p in cur["parts"]]
        cur["paragraphs"] = [p for p in paras if p]
        cur["title"] = " ".join(cur["title"].split())
        del cur["parts"]
        self.articles.append(cur)
        self._current = None
        self._mode = None


def parse_articles(html: str) -> list[dict]:
    parser = _ArticleParser()
    parser.feed(html)
    parser.close()
    return parser.articles


def _split(paragraphs: list[str], max_chars: int) -> list[str]:
    parts, buf = [], ""
    for p in paragraphs:
        if buf and len(buf) + len(p) + 1 > max_chars:
            parts.append(buf)
            buf = p
        else:
            buf = f"{buf} {p}".strip()
    if buf:
        parts.append(buf)
    return parts


def to_chunks(regulation: str, celex: str, articles: list[dict], lang: str = "en", max_chars: int = 1500) -> list[Chunk]:
    chunks = []
    for art in articles:
        parts = _split(art["paragraphs"], max_chars)
        for i, text in enumerate(parts, start=1):
            chunks.append(
                Chunk(
                    chunk_id=make_chunk_id(regulation, art["article"], i if len(parts) > 1 else None),
                    regulation=regulation,
                    celex=celex,
                    article=art["article"],
                    title=art["title"] or f"Article {art['article']}",
                    text=text,
                    source_url=source_url(regulation, celex, art["article"]),
                    text_type="official",
                    language=lang,
                )
            )
    return chunks


def fetch_html(celex: str, lang: str = "EN", timeout: int = 60) -> str:
    req = urllib.request.Request(
        HTML_URL.format(lang=lang, celex=celex),
        headers={"User-Agent": "compliance-copilot/0.1 (research; contact via GitHub)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def build(regulation: str, out_dir: Path, lang: str = "EN", html_file: Path | None = None) -> Path:
    celex = ACTS[regulation]
    html = html_file.read_text(encoding="utf-8") if html_file else fetch_html(celex, lang)
    articles = parse_articles(html)
    if not articles:
        raise RuntimeError(
            f"no articles parsed for {regulation}: EUR-Lex may have returned an anti-bot page. "
            "Download the HTML in a browser and pass --html-file."
        )
    chunks = to_chunks(regulation, celex, articles, lang.lower())
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{regulation.lower()}_{lang.lower()}.jsonl"
    out.write_text("\n".join(json.dumps(c.to_dict(), ensure_ascii=False) for c in chunks) + "\n", encoding="utf-8")
    return out
