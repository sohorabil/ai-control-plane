import json
import time
from typing import AsyncIterator

import google.auth
import google.auth.transport.requests
import httpx

from app.config import GCP_LOCATION, GCP_PROJECT_ID, VERTEX_MODEL_ID
from app.providers.base import ChatResult

VERTEX_URL = (
    f"https://{GCP_LOCATION}-aiplatform.googleapis.com/v1/projects/{GCP_PROJECT_ID}"
    f"/locations/{GCP_LOCATION}/publishers/google/models/{VERTEX_MODEL_ID}:generateContent"
)

VERTEX_STREAM_URL = (
    f"https://{GCP_LOCATION}-aiplatform.googleapis.com/v1/projects/{GCP_PROJECT_ID}"
    f"/locations/{GCP_LOCATION}/publishers/google/models/{VERTEX_MODEL_ID}:streamGenerateContent"
)


def _access_token() -> str:
    # Application Default Credentials — `gcloud auth application-default login`
    # locally today; a service account via Workload Identity Federation later.
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


async def chat(prompt: str) -> ChatResult:
    headers = {"Authorization": f"Bearer {_access_token()}"}
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(VERTEX_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    latency_ms = int((time.perf_counter() - start) * 1000)

    candidate = data["candidates"][0]
    usage = data.get("usageMetadata", {})

    return ChatResult(
        answer=candidate["content"]["parts"][0]["text"],
        input_tokens=usage.get("promptTokenCount", 0),
        output_tokens=usage.get("candidatesTokenCount", 0),
        latency_ms=latency_ms,
    )


async def chat_with_document(prompt: str, file_bytes: bytes, mime_type: str) -> ChatResult:
    import base64

    headers = {"Authorization": f"Bearer {_access_token()}"}
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(file_bytes).decode("ascii"),
                        }
                    },
                ],
            }
        ]
    }

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(VERTEX_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    latency_ms = int((time.perf_counter() - start) * 1000)

    candidate = data["candidates"][0]
    usage = data.get("usageMetadata", {})

    return ChatResult(
        answer=candidate["content"]["parts"][0]["text"],
        input_tokens=usage.get("promptTokenCount", 0),
        output_tokens=usage.get("candidatesTokenCount", 0),
        latency_ms=latency_ms,
    )


async def chat_stream(prompt: str) -> AsyncIterator[str]:
    headers = {"Authorization": f"Bearer {_access_token()}"}
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST", VERTEX_STREAM_URL, headers=headers, json=payload
        ) as resp:
            resp.raise_for_status()
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                # Vertex streams a JSON array; parse out each complete object
                # as it arrives rather than waiting for the whole array to close.
                while True:
                    buffer = buffer.lstrip(", \n\r\t[")
                    try:
                        obj, idx = json.JSONDecoder().raw_decode(buffer)
                    except json.JSONDecodeError:
                        break
                    buffer = buffer[idx:]
                    parts = obj.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part:
                            yield part["text"]
