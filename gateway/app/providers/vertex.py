import time

import google.auth
import google.auth.transport.requests
import httpx

from app.config import GCP_LOCATION, GCP_PROJECT_ID, VERTEX_MODEL_ID
from app.providers.base import ChatResult

VERTEX_URL = (
    f"https://{GCP_LOCATION}-aiplatform.googleapis.com/v1/projects/{GCP_PROJECT_ID}"
    f"/locations/{GCP_LOCATION}/publishers/google/models/{VERTEX_MODEL_ID}:generateContent"
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
