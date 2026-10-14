from ccp.llm import FakeClient
from ccp.prompts import load
from ccp.synthetic import generate
from ccp.triage import LLMTriage, RulesTriage, decide, triage

BASE = {"claim_id": "CLM-2026-000001", "policy_start_date": "2025-01-01", "incident_date": "2026-03-01",
        "report_date": "2026-03-02", "amount_claimed_eur": 800.0}


def test_never_rejects():
    routes = {decide(c, c["gold_category"], c["gold_urgency"]).route for c in generate(n=200)}
    assert routes <= {"fast_track", "standard", "human_review"}


def test_high_urgency_and_signals_go_to_a_human():
    assert decide(BASE, "fire", "high").route == "human_review"
    late = dict(BASE, report_date="2026-05-01")
    d = decide(late, "theft", "low")
    assert d.route == "human_review" and d.signals
    assert decide(dict(BASE, amount_claimed_eur=20000), "collision", "normal").route == "human_review"
    assert decide(dict(BASE, policy_start_date="2026-02-20"), "collision", "normal").route == "human_review"


def test_unknown_reading_goes_to_a_human():
    assert decide(BASE, None, None).route == "human_review"
    assert decide(BASE, "other", "low").route == "human_review"


def test_fast_track_and_standard():
    assert decide(BASE, "water_damage", "low").route == "fast_track"
    assert decide(BASE, "water_damage", "normal").route == "standard"


def test_rules_reader_negation():
    r = RulesTriage()
    assert r.read("Collision au rond-point, aucun blessé.") == ("collision", "normal")
    assert r.read("Accident, le conducteur adverse a été blessé.")[1] == "high"
    assert r.read("Bagage perdu par la compagnie aérienne lors du vol retour.") == ("travel", "low")


def test_llm_reader_redacts_validates_and_retries():
    client = FakeClient(["not json", '{"category": "fire", "urgency": "high"}'])
    reader = LLMTriage(client, load("claims_triage"))
    assert reader.read("Assuré : Camille Martin, 06 39 98 12 34. Incendie du garage.") == ("fire", "high")
    assert all("Camille" not in user and "06 39 98" not in user for _, user in client.calls)


def test_llm_reader_invalid_labels_fall_back_to_human_review():
    reader = LLMTriage(FakeClient(['{"category": "reject", "urgency": "none"}']), load("claims_triage"))
    out = triage(dict(BASE, description="Incendie"), reader)
    assert out["route"] == "human_review" and reader.failures == 1
