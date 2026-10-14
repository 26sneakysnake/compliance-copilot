import pytest

from ccp.corpus import load_sample


@pytest.fixture(scope="session")
def chunks():
    return load_sample()


@pytest.fixture
def tmp_logs(tmp_path, monkeypatch):
    from ccp import config

    monkeypatch.setattr(config, "TRACE_FILE", tmp_path / "traces.jsonl")
    monkeypatch.setattr(config, "AUDIT_FILE", tmp_path / "audit.jsonl")
    return tmp_path
