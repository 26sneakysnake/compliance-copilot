"""Tracing, latency and cost monitoring.

Each request produces one trace with nested spans (retrieve, generate,
validate...). Traces are always written as JSON lines to logs/traces.jsonl,
which the /metrics endpoint aggregates. When OpenTelemetry is configured, the
same spans are exported over OTLP, using the GenAI semantic conventions
(gen_ai.request.model, gen_ai.usage.input_tokens, ...), so they show up in
Langfuse, Jaeger, Grafana Tempo or Azure Monitor without code changes.

Langfuse: set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and optionally
LANGFUSE_HOST; `setup_otel()` then points the OTLP exporter at Langfuse's
OpenTelemetry endpoint. Any other backend: set OTEL_EXPORTER_OTLP_ENDPOINT.
"""
from __future__ import annotations

import base64
import json
import math
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from . import config

try:  # the API package is tiny; without an SDK every call is a no-op
    from opentelemetry import trace as _otel_trace
except ImportError:  # pragma: no cover
    _otel_trace = None

_lock = threading.Lock()


def setup_otel(service_name: str = "compliance-copilot") -> str | None:
    """Configure an OTLP exporter if the environment asks for one. Returns the endpoint."""
    if _otel_trace is None:
        return None
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    headers = {}
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
        endpoint = f"{host}/api/public/otel/v1/traces"
        token = base64.b64encode(
            f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}".encode()
        ).decode()
        headers["Authorization"] = f"Basic {token}"
    elif endpoint:
        endpoint = endpoint.rstrip("/") + "/v1/traces"
    if not endpoint:
        return None
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return None
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers)))
    _otel_trace.set_tracer_provider(provider)
    return endpoint


def _clean(value):
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return str(value)


class Span:
    def __init__(self, name: str, otel_span=None):
        self.name = name
        self.attributes: dict = {}
        self.start = time.time()
        self.duration_ms = 0.0
        self._otel = otel_span

    def set(self, **attrs) -> "Span":
        for k, v in attrs.items():
            if v is None:
                continue
            self.attributes[k] = _clean(v)
            if self._otel is not None:
                self._otel.set_attribute(k, _clean(v))
        return self

    def to_dict(self) -> dict:
        return {"name": self.name, "duration_ms": self.duration_ms, "attributes": self.attributes}


class Trace:
    def __init__(self, tracer: "Tracer", name: str):
        self.tracer = tracer
        self.name = name
        self.trace_id = uuid.uuid4().hex
        self.root = Span(name)
        self.spans: list[Span] = []

    @contextmanager
    def span(self, name: str, **attrs):
        otel_cm = self.tracer._otel.start_as_current_span(name) if self.tracer._otel else None
        otel_span = otel_cm.__enter__() if otel_cm else None
        s = Span(name, otel_span).set(**attrs)
        t0 = time.perf_counter()
        try:
            yield s
        finally:
            s.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            self.spans.append(s)
            if otel_cm:
                otel_cm.__exit__(None, None, None)

    def set(self, **attrs) -> "Trace":
        self.root.set(**attrs)
        return self

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "ts": round(self.root.start, 3),
            "duration_ms": self.root.duration_ms,
            "attributes": self.root.attributes,
            "spans": [s.to_dict() for s in self.spans],
        }


class Tracer:
    def __init__(self, path: Path | None = None, enabled: bool = True):
        self.path = Path(path) if path else config.TRACE_FILE
        self.enabled = enabled
        self._otel = _otel_trace.get_tracer("ccp") if _otel_trace else None

    @contextmanager
    def trace(self, name: str, **attrs):
        tr = Trace(self, name)
        otel_cm = self._otel.start_as_current_span(name) if self._otel else None
        tr.root._otel = otel_cm.__enter__() if otel_cm else None
        tr.set(**attrs)
        t0 = time.perf_counter()
        try:
            yield tr
        except Exception as exc:
            tr.set(error=type(exc).__name__)
            raise
        finally:
            tr.root.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            if otel_cm:
                otel_cm.__exit__(None, None, None)
            if self.enabled:
                self._write(tr.to_dict())

    def _write(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))
    return round(values[idx], 2)


def summarize(path: Path | None = None, last: int | None = None) -> dict:
    """Aggregate traces: volume, latency percentiles, cost, refusal rate, per prompt version."""
    path = Path(path) if path else config.TRACE_FILE
    if not path.exists():
        return {"traces": 0}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if last:
        rows = rows[-last:]
    out: dict = {"traces": len(rows), "by_name": {}}
    for name in sorted({r["name"] for r in rows}):
        rs = [r for r in rows if r["name"] == name]
        lat = [r["duration_ms"] for r in rs]
        costs = [r["attributes"].get("cost_usd", 0.0) for r in rs]
        costs = [c for c in costs if isinstance(c, (int, float)) and not math.isnan(c)]
        stats = {
            "count": len(rs),
            "latency_ms_p50": _pct(lat, 0.5),
            "latency_ms_p95": _pct(lat, 0.95),
            "cost_usd_total": round(sum(costs), 6),
            "cost_usd_per_request": round(sum(costs) / len(rs), 8) if rs else 0,
            "input_tokens_total": sum(r["attributes"].get("gen_ai.usage.input_tokens", 0) for r in rs),
            "output_tokens_total": sum(r["attributes"].get("gen_ai.usage.output_tokens", 0) for r in rs),
            "errors": sum(1 for r in rs if "error" in r["attributes"]),
        }
        statuses = [r["attributes"].get("status") for r in rs if r["attributes"].get("status")]
        if statuses:
            stats["refusal_rate"] = round(sum(s == "refused" for s in statuses) / len(statuses), 4)
        versions = {r["attributes"].get("prompt_ref") for r in rs} - {None}
        if versions:
            stats["prompt_versions"] = sorted(versions)
        out["by_name"][name] = stats
    return out
