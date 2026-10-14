"""Evaluation metrics for the copilot (RAG) and the claims triage.

The structure is carried over from clinical-notes-eval: score each item,
aggregate per field, write every error to a JSONL file for error analysis, and
let the numbers (not the model) decide what ships.
"""
from __future__ import annotations

import math

from ..tracing import _pct


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    """Micro precision / recall / F1, as in clinical-notes-eval."""
    if tp + fp + fn == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def score_item(item: dict, ans: dict) -> dict:
    """Per-question verdict. `ans` is Answer.to_dict()."""
    retrieved = [r["chunk_id"] for r in ans["retrieved"]]
    cited = [c["chunk_id"] for c in ans["citations"]]
    refused = ans["status"] == "refused"
    out = {"id": item["id"], "split": item["split"], "answerable": item["answerable"], "refused": refused,
           "refusal_reason": ans["refusal_reason"], "invalid_citations": len(ans["invalid_citations"]),
           "latency_ms": ans["latency_ms"], "cost_usd": ans["cost_usd"]}
    if not item["answerable"]:
        out["correct"] = refused
        return out
    expected = set(item["expected"])
    ranks = [i for i, cid in enumerate(retrieved, start=1) if cid in expected]
    facts = item.get("must_mention", [])
    text = ans["answer"].lower()
    found = [f for f in facts if f.lower() in text] if not refused else []
    out.update(
        retrieval_hit=bool(ranks),
        reciprocal_rank=1 / ranks[0] if ranks else 0.0,
        cites_expected=bool(expected & set(cited)),
        cited=cited,
        cited_in_expected=sum(c in expected for c in cited),
        facts_total=len(facts),
        facts_found=len(found),
    )
    out["correct"] = (not refused) and out["cites_expected"] and len(found) == len(facts)
    return out


def aggregate(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["answerable"]]
    una = [r for r in rows if not r["answerable"]]
    answered = [r for r in ans if not r["refused"]]
    refused_all = [r for r in rows if r["refused"]]
    n_cited = sum(len(r["cited"]) for r in answered)
    costs = [r["cost_usd"] for r in rows if isinstance(r["cost_usd"], (int, float)) and not math.isnan(r["cost_usd"])]
    return {
        "n_questions": len(rows),
        "n_answerable": len(ans),
        "n_unanswerable": len(una),
        "retrieval_hit_rate": _ratio(sum(r["retrieval_hit"] for r in ans), len(ans)),
        "mrr": round(sum(r["reciprocal_rank"] for r in ans) / len(ans), 4) if ans else None,
        "answer_rate": _ratio(len(answered), len(ans)),
        "false_refusal_rate": _ratio(len(ans) - len(answered), len(ans)),
        "refusal_recall": _ratio(sum(r["refused"] for r in una), len(una)),
        "refusal_precision": _ratio(sum(not r["answerable"] for r in refused_all), len(refused_all)),
        "citation_precision": _ratio(sum(r["cited_in_expected"] for r in answered), n_cited),
        "cites_expected_rate": _ratio(sum(r["cites_expected"] for r in answered), len(answered)),
        "fact_recall": _ratio(sum(r["facts_found"] for r in answered), sum(r["facts_total"] for r in answered)),
        "end_to_end_accuracy": _ratio(sum(r["correct"] for r in rows), len(rows)),
        "invalid_citation_count": sum(r["invalid_citations"] for r in rows),
        "latency_ms_p50": _pct([r["latency_ms"] for r in rows], 0.5),
        "latency_ms_p95": _pct([r["latency_ms"] for r in rows], 0.95),
        "cost_usd_total": round(sum(costs), 6),
    }


def score_triage(preds: list[dict], golds: list[dict]) -> dict:
    """Field accuracy and decision agreement, the clinical-notes-eval pattern applied to claims."""
    n = len(golds)
    if n == 0 or len(preds) != n:
        raise ValueError("preds and golds must be non-empty and aligned")
    acc = lambda f, g: round(sum(p[f] == gd[g] for p, gd in zip(preds, golds)) / n, 4)  # noqa: E731
    routes = ("fast_track", "standard", "human_review")
    confusion = {g: {p: 0 for p in routes} for g in routes}
    for p, gd in zip(preds, golds):
        confusion[gd["gold_route"]][p["route"]] += 1
    # The costly error: a case that needed a human was fast-tracked or handled as standard.
    missed = sum(gd["gold_route"] == "human_review" and p["route"] != "human_review" for p, gd in zip(preds, golds))
    needs_human = sum(gd["gold_route"] == "human_review" for gd in golds)
    return {
        "n_claims": n,
        "category_accuracy": acc("category", "gold_category"),
        "urgency_accuracy": acc("urgency", "gold_urgency"),
        "route_agreement": acc("route", "gold_route"),
        "human_review_recall": _ratio(needs_human - missed, needs_human),
        "missed_human_review": missed,
        "route_confusion": confusion,
    }
