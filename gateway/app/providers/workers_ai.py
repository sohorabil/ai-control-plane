import time

import httpx

from app.config import CF_ACCOUNT_ID, CF_AIG_NAME, CF_API_TOKEN, WORKERS_AI_MODEL
from app.providers.base import ChatResult

# AI Gateway sits in front of Workers AI: same call, but responses get logged,
# cached, and given analytics for free — no extra code needed for that part.
AI_GATEWAY_URL = (
    f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_AIG_NAME}"
    f"/workers-ai/{WORKERS_AI_MODEL}"
)


async def chat(prompt: str) -> ChatResult:
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
    payload = {"messages": [{"role": "user", "content": prompt}]}

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(AI_GATEWAY_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    latency_ms = int((time.perf_counter() - start) * 1000)

    result = data["result"]
    # Some Workers AI models return {"response": "..."}; newer ones return
    # OpenAI-style {"choices": [{"message": {"content": "..."}}]}.
    if "response" in result:
        answer = result["response"]
    else:
        answer = result["choices"][0]["message"]["content"]

    usage = result.get("usage", {})
    return ChatResult(
        answer=answer,
        input_tokens=usage.get("prompt_tokens", 0),
        output_tokens=usage.get("completion_tokens", 0),
        latency_ms=latency_ms,
    )
