import httpx

from app.config import CF_ACCOUNT_ID, CF_AIG_NAME, CF_API_TOKEN, WORKERS_AI_MODEL

# AI Gateway sits in front of Workers AI: same call, but responses get logged,
# cached, and given analytics for free — no extra code needed for that part.
AI_GATEWAY_URL = (
    f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_AIG_NAME}"
    f"/workers-ai/{WORKERS_AI_MODEL}"
)


async def chat(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
    payload = {"messages": [{"role": "user", "content": prompt}]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(AI_GATEWAY_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    result = data["result"]
    # Some Workers AI models return {"response": "..."}; newer ones return
    # OpenAI-style {"choices": [{"message": {"content": "..."}}]}.
    if "response" in result:
        return result["response"]
    return result["choices"][0]["message"]["content"]
