import pandas as pd
import pytest

from ccp.contracts import load_contract, to_pandera, validate
from ccp.pipeline import LABEL_COLUMNS, QualityGateError, claims_to_silver, run
from ccp.synthetic import generate


@pytest.fixture(scope="module")
def raw():
    return pd.DataFrame(generate(n=80, seed=3)).drop(columns=LABEL_COLUMNS)


def test_raw_and_silver_pass(raw):
    assert validate(raw, "claims_raw").passed
    assert validate(claims_to_silver(raw), "claims_silver").passed


def test_silver_rejects_identifier_columns(raw):
    silver = claims_to_silver(raw)
    silver["customer_email"] = raw["customer_email"]
    report = validate(silver, "claims_silver")
    assert not report.passed
    assert {"rule": "forbidden_column", "column": "customer_email"} in report.failures


def test_silver_rejects_unredacted_text(raw):
    silver = claims_to_silver(raw)
    silver.loc[0, "description_redacted"] = "Rappeler au 06 39 98 11 22"
    assert not validate(silver, "claims_silver").passed


def test_dates_order_rule(raw):
    bad = raw.copy()
    bad.loc[1, "report_date"] = "2020-01-01"
    report = validate(bad, "claims_raw")
    assert any(f["rule"] == "column_gte" for f in report.failures)


def test_enum_pattern_and_synthetic_flag(raw):
    bad = raw.copy()
    bad.loc[0, "line_of_business"] = "crypto"
    bad.loc[1, "claim_id"] = "X-1"
    bad.loc[2, "is_synthetic"] = False
    bad.loc[3, "customer_email"] = "someone@gmail.com"  # synthetic data must use example.org
    cols = {f["column"] for f in validate(bad, "claims_raw").failures if f["rule"] == "schema"}
    assert {"line_of_business", "claim_id", "is_synthetic", "customer_email"} <= cols


def test_every_contract_compiles():
    for name in ("regulatory_chunks", "claims_raw", "claims_silver"):
        c = load_contract(name)
        assert to_pandera(c).name == c["id"]
        assert c["owner"] and c["classification"]


def test_pipeline_quality_gate_stops_bad_runs(tmp_path, monkeypatch):
    from ccp import config, pipeline

    monkeypatch.setattr(config, "CLAIMS_DIR", tmp_path)
    reports = run(n=60, seed=1, out_dir=tmp_path)
    assert all(r.passed for r in reports.values())
    monkeypatch.setattr(pipeline, "claims_to_silver", lambda raw: raw)  # forget to anonymise
    with pytest.raises(QualityGateError):
        run(n=60, seed=1, out_dir=tmp_path)
