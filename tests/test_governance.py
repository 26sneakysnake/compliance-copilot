import copy

from ccp.governance import check_register, load_register, render_register


def test_register_is_valid():
    assert check_register() == []


def test_missing_evidence_or_reference_is_caught():
    reg = copy.deepcopy(load_register())
    reg["risks"][0]["controls"][0]["evidence"].append("does/not/exist.py")
    reg["risks"][1]["regulatory_refs"].append("GDPR-9999")
    problems = check_register(reg)
    assert any("evidence not found" in p for p in problems)
    assert any("GDPR-9999" in p for p in problems)


def test_render(tmp_path):
    out = render_register(out=tmp_path / "r.md")
    text = out.read_text()
    assert "| R01 |" in text and "not high-risk" in text
