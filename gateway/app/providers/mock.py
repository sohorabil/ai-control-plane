import asyncio
import time

from app.providers.base import ChatResult


async def chat(prompt: str) -> ChatResult:
    start = time.perf_counter()
    await asyncio.sleep(0.1)  # pretend there's network latency
    latency_ms = int((time.perf_counter() - start) * 1000)

    return ChatResult(
        answer=f"[mock] you said: {prompt}",
        input_tokens=len(prompt.split()),
        output_tokens=10,
        latency_ms=latency_ms,
    )
