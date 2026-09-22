import json
import time

import boto3

from app.config import AWS_REGION, BEDROCK_MODEL_ID
from app.providers.base import ChatResult

_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)


async def chat(prompt: str) -> ChatResult:
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    start = time.perf_counter()
    # boto3 is sync-only; this call blocks the event loop briefly, which is
    # acceptable for Part 2 and will be revisited if it becomes a bottleneck.
    response = _client.invoke_model(modelId=BEDROCK_MODEL_ID, body=body)
    latency_ms = int((time.perf_counter() - start) * 1000)

    data = json.loads(response["body"].read())
    usage = data.get("usage", {})

    return ChatResult(
        answer=data["content"][0]["text"],
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        latency_ms=latency_ms,
    )
