import pandas as pd

from ccp.contracts import validate
from ccp.corpus import CHUNK_ID_RE, load_corpus, make_chunk_id, source_url


def test_sample_corpus_passes_its_contract(chunks):
    report = validate(pd.DataFrame([c.to_dict() for c in chunks]), "regulatory_chunks")
    assert report.passed, report.failures


def test_chunk_ids_are_unique_and_well_formed(chunks):
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(CHUNK_ID_RE.match(i) for i in ids)


def test_sample_is_labelled_as_paraphrase(chunks):
    assert {c.text_type for c in chunks} == {"paraphrase"}


def test_chunk_id_and_label():
    assert make_chunk_id("AI_ACT", "Annex III (5)") == "AI_ACT-annex-iii-5"
    assert make_chunk_id("GDPR", "33", part=2) == "GDPR-33-p2"
    assert source_url("GDPR", "32016R0679", "33").endswith("CELEX:32016R0679#art_33")


def test_auto_mode_falls_back_to_sample(tmp_path, monkeypatch):
    from ccp import config, corpus

    monkeypatch.setattr(corpus, "load_official", lambda directory=config.OFFICIAL_CORPUS_DIR: [])
    assert load_corpus("auto")[0].text_type == "paraphrase"
