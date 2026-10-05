"""OpenTelemetry tracing setup — Part 11.

FastAPIInstrumentor auto-creates one span per incoming HTTP request (covers
the "edge -> gateway" hop automatically). provider_span() wraps each actual
provider call as a CHILD span of that request span, so Jaeger shows the full
"edge -> gateway -> provider" journey as one connected trace, not two
disconnected ones — a trace is the whole journey; each hop within it is a
span, nested under its parent.
"""
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import OTEL_EXPORTER_OTLP_ENDPOINT

_tracer = None


def setup_tracing(app) -> None:
    global _tracer
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "eacp-gateway"}))
    exporter = OTLPSpanExporter(endpoint=f"{OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("eacp-gateway")
    FastAPIInstrumentor.instrument_app(app)


@contextmanager
def provider_span(provider_name: str, model: str):
    """Wraps one provider call as a child span of the current request span."""
    tracer = _tracer or trace.get_tracer("eacp-gateway")
    with tracer.start_as_current_span(f"provider.{provider_name}") as span:
        span.set_attribute("gen_ai.system", provider_name)
        span.set_attribute("gen_ai.request.model", model)
        yield span
