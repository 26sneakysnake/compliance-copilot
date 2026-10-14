import json

from ccp.audit import AuditLog


def test_chain_verifies_and_detects_tampering(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    for i in range(3):
        log.record("ask", user=f"user{i}", role="analyst", question=f"q{i}", status="answered")
    assert log.verify() == (True, None)

    lines = log.path.read_text().splitlines()
    e = json.loads(lines[1])
    e["status"] = "refused"
    lines[1] = json.dumps(e)
    log.path.write_text("\n".join(lines) + "\n")
    assert log.verify() == (False, 1)


def test_deleting_an_entry_breaks_the_chain(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    for i in range(3):
        log.record("ask", user="u", role="analyst", n=i)
    lines = log.path.read_text().splitlines()
    log.path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert log.verify() == (False, 1)


def test_text_is_redacted_and_user_pseudonymised(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    e = log.record("ask", user="alice@example.org", role="analyst", question="mail bob@example.org")
    assert "alice" not in e["user"] and "[EMAIL]" in e["question"]
