import copy

import yaml

from ccp import config
from ccp.eval.metrics import _prf, aggregate, score_item, score_triage
from ccp.eval.run import gate, load_golden


def _ans(status="answered", cited=(), text="", retrieved=()):
    return {"status": status, "answer": text, "refusal_reason": None if status == "answered" else "no_source",
            "citations": [{"chunk_id": c} for c in cited], "retrieved": [{"chunk_id": r} for r in retrieved],
            "invalid_citations": [], "latency_ms": 1.0, "cost_usd": 0.0}


def test_golden_set_is_consistent(chunks):
    items = load_golden()
    ids = {c.chunk_id for c in chunks}
    assert len({i["id"] for i in items}) == len(items)
    assert {i["split"] for i in items} == {"dev", "test"}
    for i in items:
        if i["answerable"]:
            assert set(i["expected"]) <= ids, i["id"]
            assert i["must_mention"]
    assert sum(not i["answerable"] for i in items) >= 10


def test_score_item_and_aggregate():
    item = {"id": "x", "split": "dev", "answerable": True, "expected": ["GDPR-33"], "must_mention": ["72 hours"]}
    good = score_item(item, _ans(cited=["GDPR-33"], text="within 72 hours", retrieved=["GDPR-34", "GDPR-33"]))
    assert good["correct"] and good["reciprocal_rank"] == 0.5
    bad = score_item(item, _ans(status="refused", retrieved=["GDPR-33"]))
    neg = score_item({"id": "y", "split": "dev", "answerable": False}, _ans(status="refused"))
    agg = aggregate([good, bad, neg])
    assert agg["false_refusal_rate"] == 0.5 and agg["refusal_recall"] == 1.0 and agg["refusal_precision"] == 0.5


def test_prf_is_the_clinical_notes_eval_definition():
    assert _prf(0, 0, 0)["f1"] == 1.0
    assert _prf(1, 1, 0) == {"precision": 0.5, "recall": 1.0, "f1": 0.6667}


def test_triage_scoring_flags_missed_reviews():
    golds = [{"gold_category": "fire", "gold_urgency": "high", "gold_route": "human_review"}]
    preds = [{"category": "fire", "urgency": "low", "route": "fast_track"}]
    m = score_triage(preds, golds)
    assert m["missed_human_review"] == 1 and m["human_review_recall"] == 0.0


def test_gate_floors_and_regressions():
    thresholds = yaml.safe_load((config.EVAL_DIR / "thresholds.yaml").read_text())
    report = {"name": "rag_extractive", "metrics": {"all": {
        "refusal_recall": 0.93, "retrieval_hit_rate": 0.98, "cites_expected_rate": 0.97, "answer_rate": 0.94,
        "end_to_end_accuracy": 0.77, "invalid_citation_count": 0, "mrr": 0.87, "fact_recall": 0.77}}}
    assert gate(report, thresholds, copy.deepcopy(report)) == []
    worse = copy.deepcopy(report)
    worse["metrics"]["all"]["fact_recall"] = 0.70
    worse["metrics"]["all"]["invalid_citation_count"] = 2
    problems = gate(worse, thresholds, report)
    assert any("fact_recall regressed" in p for p in problems)
    assert any("invalid_citation_count" in p for p in problems)


def test_committed_baselines_pass_the_gate():
    import json

    thresholds = yaml.safe_load((config.EVAL_DIR / "thresholds.yaml").read_text())
    for name in ("rag_extractive", "triage_rules"):
        report = json.loads((config.ROOT / "results" / f"{name}.json").read_text())
        assert gate(report, thresholds) == [], name
