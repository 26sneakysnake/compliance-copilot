import pytest

from ccp.catalog_sql import _ident, all_sql


def test_sql_generated_from_contracts_and_roles():
    s = all_sql("workspace", "cc")
    raw = "\n".join(s["claims_raw"])
    assert "CHECK (`line_of_business` IN ('auto', 'home', 'liability', 'travel'))" in raw
    assert "CHECK (`report_date` >= `incident_date`)" in raw
    assert "ALTER COLUMN `iban` SET TAGS ('pii' = 'direct')" in raw
    assert "'classification' = 'restricted'" in raw
    grants = "\n".join(s["grants"])
    assert "ON TABLE workspace.cc.`bronze_claims_raw` TO `ccp_data_engineer`" in grants
    assert "bronze_claims_raw` TO `ccp_analyst`" not in grants


def test_identifiers_are_checked():
    with pytest.raises(ValueError):
        _ident("x; DROP TABLE y")
