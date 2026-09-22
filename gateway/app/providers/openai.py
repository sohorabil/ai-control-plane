import time

import httpx

from app.config import CF_ACCOUNT_ID, CF_AIG_NAME, OPENAI_API_KEY, OPENAI_MODEL
from app.providers.base import ChatResult

AI_GATEWAY_URL = f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_AIG_NAME}/openai/chat/completions"


async def chat(prompt: str) -> ChatResult:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(AI_GATEWAY_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    latency_ms = int((time.perf_counter() - start) * 1000)

    usage = data.get("usage", {})
    return ChatResult(
        answer=data["choices"][0]["message"]["content"],
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        latency_ms=latency_ms,
    )
