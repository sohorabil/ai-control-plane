import asyncio
import hashlib
import json
import random
from pathlib import Path

import yaml

from app.redis_client import client as redis_client

_ROUTING_PATH = Path(__file__).parent.parent / "routing.yaml"
_config = yaml.safe_load(_ROUTING_PATH.read_text())

RETRY = _config["retry"]
BREAKER = _config["circuit_breaker"]
CACHE_TTL = _config["cache"]["ttl_seconds"]


def get_candidates(task: str) -> list[str]:
    task_config = _config["tasks"].get(task, _config["tasks"]["chat"])
    return task_config["candidates"]


def get_quality_floor(task: str) -> float:
    task_config = _config["tasks"].get(task, _config["tasks"]["chat"])
    return task_config.get("quality_floor", 0.0)


# --- canary rollout: route a % of one task's traffic to a candidate --------

def get_canary_config() -> dict:
    return _config.get("canary", {"candidate_weight": 0.0})


def pick_ordered_candidates(task: str) -> list[str]:
    """Normal candidate order, unless this task has an active canary
    rollout — then a random slice of requests try the canary candidate
    first instead, falling back to the normal order if it fails.
    """
    candidates = get_candidates(task)
    canary = get_canary_config()

    if canary.get("task") != task or canary.get("candidate_weight", 0.0) <= 0.0:
        return candidates

    if random.random() < canary["candidate_weight"]:
        candidate = canary["candidate"]
        reordered = [candidate] + [c for c in candidates if c != candidate]
        return reordered

    return candidates


# --- circuit breaker: tracked per-provider in Redis -------------------------

def _breaker_key(provider: str) -> str:
    return f"breaker:{provider}:failures"


def _breaker_open_key(provider: str) -> str:
    return f"breaker:{provider}:open"


def is_breaker_open(provider: str) -> bool:
    return redis_client.exists(_breaker_open_key(provider)) == 1


def record_success(provider: str) -> None:
    redis_client.delete(_breaker_key(provider))
    redis_client.delete(_breaker_open_key(provider))


def record_failure(provider: str) -> None:
    failures = redis_client.incr(_breaker_key(provider))
    redis_client.expire(_breaker_key(provider), BREAKER["open_seconds"] * 4)
    if failures >= BREAKER["failure_threshold"]:
        redis_client.set(_breaker_open_key(provider), "1", ex=BREAKER["open_seconds"])


# --- response cache -----------------------------------------------------

def _cache_key(provider: str, prompt: str) -> str:
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    return f"cache:{provider}:{digest}"


def get_cached(provider: str, prompt: str) -> dict | None:
    raw = redis_client.get(_cache_key(provider, prompt))
    return json.loads(raw) if raw else None


def set_cached(provider: str, prompt: str, payload: dict) -> None:
    redis_client.set(_cache_key(provider, prompt), json.dumps(payload), ex=CACHE_TTL)


# --- retry with backoff+jitter, then fallback across candidates -----------

class AllProvidersFailedError(Exception):
    pass


async def call_with_fallback(providers: dict, task: str, prompt: str):
    """Tries each candidate provider in order for `task`. Within a provider,
    retries with backoff+jitter up to max_attempts_per_provider times. Skips
    providers whose circuit breaker is currently open. Returns
    (provider_name, ChatResult, attempted_providers).
    """
    attempted = []

    for provider_name in pick_ordered_candidates(task):
        if provider_name not in providers:
            continue
        if is_breaker_open(provider_name):
            attempted.append({"provider": provider_name, "skipped": "breaker_open"})
            continue

        for attempt in range(RETRY["max_attempts_per_provider"]):
            try:
                result = await providers[provider_name].chat(prompt)
                record_success(provider_name)
                attempted.append({"provider": provider_name, "status": "ok"})
                return provider_name, result, attempted
            except Exception as exc:
                record_failure(provider_name)
                attempted.append(
                    {"provider": provider_name, "status": "error", "detail": str(exc)}
                )
                if attempt < RETRY["max_attempts_per_provider"] - 1:
                    backoff = min(
                        RETRY["backoff_base_ms"] * (2 ** attempt), RETRY["backoff_max_ms"]
                    )
                    jitter = random.uniform(0, backoff * 0.3)
                    await asyncio.sleep((backoff + jitter) / 1000)

    raise AllProvidersFailedError(f"all candidates for task '{task}' failed: {attempted}")
