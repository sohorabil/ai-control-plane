import asyncio
import re
import time
from typing import AsyncIterator

from app.providers.base import ChatResult
from app.tools import get_ticket


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


async def chat_with_tools(prompt: str) -> ChatResult:
    """Mimics tool-calling: if the prompt mentions a ticket ID, "call" get_ticket
    and use its result, the same shape real tool-calling APIs follow — decide
    to call a tool, run it, then answer using the result. No real model call,
    so this is free and works without any provider credentials.
    """
    start = time.perf_counter()
    await asyncio.sleep(0.1)

    match = re.search(r"T-\d{4}", prompt)
    if match:
        ticket = get_ticket(match.group(0))
        if "error" in ticket:
            answer = f"[mock] {ticket['error']}"
        else:
            answer = (
                f"[mock] Ticket {ticket['id']} ('{ticket['subject']}') "
                f"is currently {ticket['status']}."
            )
    else:
        answer = "[mock] I can look up a ticket if you give me an ID like T-1001."

    latency_ms = int((time.perf_counter() - start) * 1000)
    return ChatResult(
        answer=answer,
        input_tokens=len(prompt.split()),
        output_tokens=len(answer.split()),
        latency_ms=latency_ms,
    )


async def chat_stream(prompt: str) -> AsyncIterator[str]:
    words = f"[mock stream] you said: {prompt}".split(" ")
    for word in words:
        await asyncio.sleep(0.2)  # slow enough to visibly see words appear
        yield word + " "
