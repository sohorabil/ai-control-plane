import json
import os
import time
from typing import AsyncIterator

import boto3
import google.auth
import google.auth.aws
import google.auth.exceptions
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

EMBEDDING_MODEL_ID = "text-embedding-005"
EMBEDDING_URL = (
    f"https://{GCP_LOCATION}-aiplatform.googleapis.com/v1/projects/{GCP_PROJECT_ID}"
    f"/locations/{GCP_LOCATION}/publishers/google/models/{EMBEDDING_MODEL_ID}:predict"
)


_credentials = None


class _PodIdentitySupplier(google.auth.aws.AwsSecurityCredentialsSupplier):
    # EKS Pod Identity hands out credentials via AWS_CONTAINER_CREDENTIALS_FULL_URI
    # (a URL only reachable with a bearer token from a mounted file), not the
    # classic EC2 IMDS role-name-then-credentials flow our wif-credential-config.json
    # was written for back in Part 5. google-auth's built-in AWS credential source
    # only knows the IMDS flow, so on AWS we delegate credential lookup to boto3 —
    # which already resolves Pod Identity correctly (same mechanism the Bedrock
    # provider relies on) — instead of reimplementing the container-credentials
    # HTTP call ourselves.
    def get_aws_security_credentials(self, context, request):
        try:
            creds = boto3.Session().get_credentials().get_frozen_credentials()
        except Exception as exc:
            raise google.auth.exceptions.RefreshError(exc, retryable=True)
        return google.auth.aws.AwsSecurityCredentials(
            creds.access_key, creds.secret_key, creds.token
        )

    def get_aws_region(self, context, request):
        return os.environ.get("AWS_REGION") or boto3.Session().region_name


def _access_token() -> str:
    # Application Default Credentials — `gcloud auth application-default login`
    # locally today; Workload Identity Federation via EKS Pod Identity on AWS
    # (Part 9 onward). Credentials are created once and reused; refreshed only
    # when actually expired (Google's client tracks this), instead of forcing
    # a fresh OAuth round-trip on every single call — under eval/retrieval
    # load, doing that dozens of times in quick succession caused timeouts.
    global _credentials
    if _credentials is None:
        wif_config_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if wif_config_path and os.path.exists(wif_config_path):
            with open(wif_config_path) as f:
                config_info = json.load(f)
            # Credentials.from_info() unconditionally overwrites the
            # aws_security_credentials_supplier kwarg with
            # info.get("aws_security_credentials_supplier") (None, since our
            # JSON has no such key) — so it silently discards a supplier
            # passed that way. Calling the constructor directly is the only
            # way to actually wire in a custom supplier.
            _credentials = google.auth.aws.Credentials(
                audience=config_info["audience"],
                subject_token_type=config_info["subject_token_type"],
                token_url=config_info["token_url"],
                service_account_impersonation_url=config_info.get(
                    "service_account_impersonation_url"
                ),
                aws_security_credentials_supplier=_PodIdentitySupplier(),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        else:
            _credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
    if not _credentials.valid:
        _credentials.refresh(google.auth.transport.requests.Request())
    return _credentials.token


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


async def embed(texts: list[str]) -> list[list[float]]:
    """Returns one 768-dim embedding vector per input text, via Vertex's
    text-embedding-005 model.
    """
    headers = {"Authorization": f"Bearer {_access_token()}"}
    payload = {"instances": [{"content": t} for t in texts]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(EMBEDDING_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    return [pred["embeddings"]["values"] for pred in data["predictions"]]


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
