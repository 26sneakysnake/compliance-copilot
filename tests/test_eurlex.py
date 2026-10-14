from pathlib import Path

from ccp.eurlex import build, parse_articles, to_chunks

FIXTURE = Path(__file__).parent / "fixtures" / "eurlex_sample.html"


def test_parse_articles_from_eurlex_markup():
    arts = parse_articles(FIXTURE.read_text())
    assert [a["article"] for a in arts] == ["1", "2", "33"]
    assert arts[0]["title"] == "Subject matter"
    assert "Article 1" not in " ".join(arts[0]["paragraphs"])  # heading skipped
    assert arts[2]["paragraphs"][0].startswith("1. In the case")


def test_nested_divs_and_line_breaks_do_not_leak_between_articles():
    arts = parse_articles(FIXTURE.read_text())
    assert not any("Subject matter" in p for p in arts[1]["paragraphs"])
    assert any("second line" in p for p in arts[1]["paragraphs"])


def test_long_articles_are_split_into_parts():
    arts = [{"article": "9", "title": "Long", "paragraphs": ["x" * 900, "y" * 900, "z" * 900]}]
    chunks = to_chunks("GDPR", "32016R0679", arts, max_chars=1500)
    assert [c.chunk_id for c in chunks] == ["GDPR-9-p1", "GDPR-9-p2", "GDPR-9-p3"]
    assert all(c.text_type == "official" for c in chunks)


def test_build_from_saved_html(tmp_path):
    out = build("GDPR", tmp_path, html_file=FIXTURE)
    assert out.exists() and "GDPR-33" in out.read_text()
