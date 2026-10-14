import json

from ccp.llm import cost_usd
from ccp.tracing import Tracer, summarize


def test_traces_written_and_summarised(tmp_path):
    t = Tracer(tmp_path / "t.jsonl")
    for status, cost in (("answered", 0.001), ("refused", 0.0), ("answered", 0.002)):
        with t.trace("ask", prompt_ref="compliance_answer@v2") as tr:
            with tr.span("retrieve", k=4):
                pass
            tr.set(status=status, cost_usd=cost, **{"gen_ai.usage.input_tokens": 100})
    rows = [json.loads(line) for line in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert rows[0]["spans"][0]["name"] == "retrieve"
    s = summarize(tmp_path / "t.jsonl")["by_name"]["ask"]
    assert s["count"] == 3 and s["refusal_rate"] == round(1 / 3, 4)
    assert s["cost_usd_total"] == 0.003 and s["input_tokens_total"] == 300
    assert s["prompt_versions"] == ["compliance_answer@v2"]


def test_errors_are_recorded(tmp_path):
    t = Tracer(tmp_path / "t.jsonl")
    try:
        with t.trace("ask"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert summarize(tmp_path / "t.jsonl")["by_name"]["ask"]["errors"] == 1


def test_cost_table():
    assert cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == 0.6
    assert cost_usd("extractive", 500, 500) == 0.0
    assert cost_usd("qwen2.5:7b", 500, 500) == 0.0
    assert cost_usd("unknown-model", 1, 1) != cost_usd("unknown-model", 1, 1)  # NaN, never a silent 0


def test_spans_are_exported_over_opentelemetry_when_an_sdk_is_configured(tmp_path):
    import pytest

    sdk = pytest.importorskip("opentelemetry.sdk.trace")
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = sdk.TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    t = Tracer(tmp_path / "t.jsonl")
    t._otel = provider.get_tracer("test")
    with t.trace("ask") as tr:
        with tr.span("generate", **{"gen_ai.request.model": "claude-haiku-5-5"}):
            pass
    names = {s.name: s for s in exporter.get_finished_spans()}
    assert set(names) == {"ask", "generate"}
    assert names["generate"].attributes["gen_ai.request.model"] == "claude-haiku-5-5"
    assert names["generate"].parent.span_id == names["ask"].context.span_id
