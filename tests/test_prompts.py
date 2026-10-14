import pytest

from ccp.prompts import load, versions


def test_latest_and_pinned_versions():
    assert versions("compliance_answer") == [1, 2]
    assert load("compliance_answer").ref == "compliance_answer@v2"
    assert load("compliance_answer", 1).ref == "compliance_answer@v1"


def test_env_pin(monkeypatch):
    monkeypatch.setenv("CCP_PROMPT_COMPLIANCE_ANSWER_VERSION", "1")
    assert load("compliance_answer").version == 1


def test_hash_changes_with_content():
    assert load("compliance_answer", 1).sha256 != load("compliance_answer", 2).sha256


def test_every_answer_prompt_keeps_the_guardrails():
    for v in versions("compliance_answer"):
        p = load("compliance_answer", v)
        assert "INSUFFICIENT_CONTEXT" in p.system and "{context}" in p.user_template


def test_unknown_prompt():
    with pytest.raises(FileNotFoundError):
        load("nope")
