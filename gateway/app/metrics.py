"""Prometheus metrics for the gateway — Part 11.

One module, one place all metric *definitions* live, so main.py/routing.py
just call record_request()/record_cache_lookup() instead of importing
prometheus_client directly everywhere. Exposed at /metrics (see main.py)
for Prometheus to scrape on a schedule.
"""
from prometheus_client import Counter, Histogram

REQUESTS_TOTAL = Counter(
    "gateway_requests_total",
    "Total chat requests handled, by app/provider/model/status",
    ["app", "provider", "model", "status"],
)

REQUEST_LATENCY_SECONDS = Histogram(
    "gateway_request_latency_seconds",
    "Request latency in seconds, by provider/model — the source for P50/P95",
    ["provider", "model"],
    # Buckets tuned for this project's real observed range (mock ~0.1s,
    # real providers 0.3s-4s) rather than Prometheus's generic web-request
    # defaults, so P50/P95 queries actually land inside measured buckets.
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0),
)

REQUEST_COST_USD = Counter(
    "gateway_request_cost_usd_total",
    "Cumulative cost in USD, by app/provider/model — the CFO's actual question",
    ["app", "provider", "model"],
)

TOKENS_TOTAL = Counter(
    "gateway_tokens_total",
    "Cumulative input/output tokens, by provider/model/direction",
    ["provider", "model", "direction"],
)

FALLBACKS_TOTAL = Counter(
    "gateway_fallbacks_total",
    "Count of requests that needed at least one fallback (first-choice provider failed)",
    ["task"],
)

CACHE_LOOKUPS_TOTAL = Counter(
    "gateway_cache_lookups_total",
    "Cache lookups, by outcome (hit/miss) — the source for cache hit rate",
    ["outcome"],
)


def record_request(app_name, provider, model, status, latency_ms, input_tokens, output_tokens, cost_usd):
    REQUESTS_TOTAL.labels(app=app_name, provider=provider, model=model, status=status).inc()
    REQUEST_LATENCY_SECONDS.labels(provider=provider, model=model).observe(latency_ms / 1000)
    REQUEST_COST_USD.labels(app=app_name, provider=provider, model=model).inc(cost_usd)
    TOKENS_TOTAL.labels(provider=provider, model=model, direction="input").inc(input_tokens)
    TOKENS_TOTAL.labels(provider=provider, model=model, direction="output").inc(output_tokens)


def record_fallback(task: str) -> None:
    FALLBACKS_TOTAL.labels(task=task).inc()


def record_cache_lookup(hit: bool) -> None:
    CACHE_LOOKUPS_TOTAL.labels(outcome="hit" if hit else "miss").inc()
