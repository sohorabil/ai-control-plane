"""Read-only Prometheus query tool — Part 13's Incident Agent.

Prometheus's HTTP API is inherently read-only for queries (there's no
"delete a metric" endpoint this client could even accidentally call) — the
safety model here is simpler than the Kubernetes/BigQuery tools, which is
itself worth noting: not every tool needs the same depth of guardrail, only
the ones that can actually cause harm.
"""
import httpx

from app.config import PROMETHEUS_URL


async def query(promql: str) -> list[dict]:
    """Runs an instant PromQL query, returns the raw result vector."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{PROMETHEUS_URL}/api/v1/query", params={"query": promql}
        )
        resp.raise_for_status()
        data = resp.json()
    return data.get("data", {}).get("result", [])


async def error_rate(environment: str = "prod", window: str = "5m") -> float | None:
    """Fraction of requests with status="error" in the given window.

    rate() needs at least two samples across the window to compute anything
    — with very little traffic (e.g. right after a fresh deploy, or in this
    project's low real volume), Prometheus legitimately returns NaN rather
    than 0, meaning "not enough data yet," not "zero errors." Returning 0.0
    for that case would be a false "all clear" — surfacing it as None
    instead so the agent can say "not enough data" rather than wrongly
    reporting a clean bill of health.
    """
    promql = (
        f'sum(rate(gateway_requests_total{{environment="{environment}",status="error"}}[{window}])) '
        f'/ sum(rate(gateway_requests_total{{environment="{environment}"}}[{window}]))'
    )
    result = await query(promql)
    if not result:
        return None
    try:
        value = float(result[0]["value"][1])
    except (KeyError, IndexError, ValueError):
        return None
    return None if value != value else value  # NaN != NaN is the standard float NaN check


async def p95_latency(environment: str = "prod", window: str = "5m") -> dict:
    """P95 latency per provider, in seconds, for the given environment.
    A provider with too few samples in the window to estimate a quantile
    shows as None (not NaN) — "not enough data," not "zero latency."
    """
    promql = (
        f'histogram_quantile(0.95, sum(rate(gateway_request_latency_seconds_bucket'
        f'{{environment="{environment}"}}[{window}])) by (le, provider))'
    )
    result = await query(promql)
    output = {}
    for r in result:
        provider = r["metric"].get("provider", "unknown")
        try:
            value = float(r["value"][1])
        except (KeyError, IndexError, ValueError):
            value = None
        output[provider] = None if value is not None and value != value else value
    return output
