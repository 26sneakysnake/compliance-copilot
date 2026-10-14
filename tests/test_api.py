import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_logs, monkeypatch):
    from ccp import api

    monkeypatch.setenv("CCP_DEMO_KEYS", "1")
    monkeypatch.setenv("CCP_API_KEYS", "secret-auditor:auditor")
    api._state.clear()
    return TestClient(api.app)


def H(key):
    return {"X-API-Key": key}


CLAIM = {"claim_id": "CLM-2026-000042", "description": "Incendie du garage, la maison est inhabitable.",
         "amount_claimed_eur": 4000, "policy_start_date": "2024-01-01", "incident_date": "2026-05-01",
         "report_date": "2026-05-02"}


def test_health_and_disclosure_headers(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["chunks"] > 40
    assert r.headers["X-AI-Generated"] == "true"


def test_ask_requires_a_key_and_the_right_role(client):
    q = {"question": "When is a DPIA required under the GDPR?"}
    assert client.post("/ask", json=q).status_code == 401
    assert client.post("/ask", json=q, headers=H("demo-auditor")).status_code == 403
    r = client.post("/ask", json=q, headers=H("demo-analyst"))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "answered" and body["citations"][0]["chunk_id"] == "GDPR-35"


def test_triage_never_rejects_and_is_audited(client):
    r = client.post("/triage", json=CLAIM, headers=H("demo-claims"))
    assert r.status_code == 200
    assert r.json()["route"] == "human_review"
    audit = client.get("/audit", headers=H("secret-auditor")).json()
    assert audit["chain_ok"] and audit["entries"][-1]["event"] == "triage"


def test_triage_validation(client):
    bad = dict(CLAIM, claim_id="nope")
    assert client.post("/triage", json=bad, headers=H("demo-claims")).status_code == 422
    bad = dict(CLAIM, report_date="not-a-date")
    assert client.post("/triage", json=bad, headers=H("demo-claims")).status_code == 422


def test_separation_of_duties(client):
    assert client.get("/audit", headers=H("demo-analyst")).status_code == 403
    assert client.post("/triage", json=CLAIM, headers=H("demo-analyst")).status_code == 403
    assert client.post("/ask", json={"question": "x"}, headers=H("demo-claims")).status_code == 403


def test_metrics_after_traffic(client):
    client.post("/ask", json={"question": "How often is TLPT required under DORA?"}, headers=H("demo-analyst"))
    client.post("/ask", json={"question": "Best chocolate cake recipe?"}, headers=H("demo-analyst"))
    m = client.get("/metrics", headers=H("demo-auditor")).json()["by_name"]["ask"]
    assert m["count"] == 2 and m["refusal_rate"] == 0.5 and m["latency_ms_p95"] is not None


def test_demo_keys_are_off_by_default(tmp_logs, monkeypatch):
    from ccp import api

    monkeypatch.delenv("CCP_DEMO_KEYS", raising=False)
    monkeypatch.delenv("CCP_API_KEYS", raising=False)
    c = TestClient(api.app)
    assert c.post("/ask", json={"question": "x"}, headers=H("demo-analyst")).status_code == 401
