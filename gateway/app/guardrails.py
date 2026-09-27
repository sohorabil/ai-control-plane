import re

import httpx

from app.config import CF_ACCOUNT_ID, CF_AIG_NAME, CF_API_TOKEN

# Deliberately simple, deterministic patterns — good enough to catch common,
# clearly-structured PII without an extra model call. Not a substitute for a
# real DLP system, but matches this part's scope.
PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
}


def scan_for_pii(text: str) -> dict[str, list[str]]:
    """Returns {pii_type: [matches]} for every PII pattern found in text."""
    found = {}
    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            found[pii_type] = matches
    return found


def redact_pii(text: str) -> str:
    redacted = text
    for pii_type, pattern in PII_PATTERNS.items():
        redacted = pattern.sub(f"[REDACTED_{pii_type.upper()}]", redacted)
    return redacted


# Heuristic check: phrases commonly used to try to override a system prompt.
INJECTION_PHRASES = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard the system prompt",
    "you are now",
    "new instructions:",
    "system prompt:",
    "reveal your instructions",
    "print your prompt",
]


def heuristic_injection_check(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in INJECTION_PHRASES)


LLAMA_GUARD_URL = (
    f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_AIG_NAME}"
    f"/workers-ai/@cf/meta/llama-guard-3-8b"
)


# S7 = Llama Guard's "Privacy" category. We deliberately ignore it here
# because our own scan_for_pii()/redact_pii() already own that concern with
# a redact-and-continue policy — letting Llama Guard also block on S7 would
# mean any prompt that even mentions PII-type topics gets rejected outright,
# which defeats the point of redacting instead of blocking.
IGNORED_CATEGORIES = {"S7"}


async def llama_guard_check(text: str) -> bool:
    """Returns True if Llama Guard flags the text as unsafe, for any category
    other than the ones we've deliberately chosen to ignore (see above).
    """
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
    payload = {"messages": [{"role": "user", "content": text}]}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(LLAMA_GUARD_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    result = data["result"]
    answer = result.get("response", "").strip().lower()
    if "unsafe" not in answer:
        return False

    flagged_categories = re.findall(r"\bs\d+\b", answer, re.IGNORECASE)
    flagged_categories = {c.upper() for c in flagged_categories}
    return bool(flagged_categories - IGNORED_CATEGORIES)


async def check_prompt_injection(text: str) -> dict:
    """Combines the fast heuristic check with Llama Guard. Returns a dict
    describing what (if anything) was flagged, without raising — callers
    decide what to do with the result.
    """
    heuristic_flag = heuristic_injection_check(text)

    try:
        guard_flag = await llama_guard_check(text)
    except Exception:
        # If Llama Guard itself is unavailable, don't fail the whole request
        # over a guardrail check — fall back to the heuristic result alone.
        guard_flag = False

    return {
        "flagged": heuristic_flag or guard_flag,
        "heuristic_flag": heuristic_flag,
        "llama_guard_flag": guard_flag,
    }
