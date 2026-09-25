import json
import time

import boto3

from app.config import AWS_REGION, BEDROCK_MODEL_ID
from app.providers.base import ChatResult
from app.tools import GET_TICKET_SCHEMA, get_ticket

_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def _invoke(messages: list, tools: list | None = None) -> dict:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "messages": messages,
    }
    if tools:
        body["tools"] = tools

    response = _client.invoke_model(modelId=BEDROCK_MODEL_ID, body=json.dumps(body))
    return json.loads(response["body"].read())


async def chat(prompt: str) -> ChatResult:
    start = time.perf_counter()
    # boto3 is sync-only; this call blocks the event loop briefly, which is
    # acceptable for now and will be revisited if it becomes a bottleneck.
    data = _invoke([{"role": "user", "content": prompt}])
    latency_ms = int((time.perf_counter() - start) * 1000)

    usage = data.get("usage", {})
    return ChatResult(
        answer=data["content"][0]["text"],
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        latency_ms=latency_ms,
    )


async def chat_with_tools(prompt: str) -> ChatResult:
    """Claude's native tool-use flow: the model can ask us to run get_ticket,
    we run it and send the result back, then the model finishes its answer.
    """
    tools = [GET_TICKET_SCHEMA]
    messages = [{"role": "user", "content": prompt}]

    start = time.perf_counter()
    data = _invoke(messages, tools=tools)

    total_input_tokens = data.get("usage", {}).get("input_tokens", 0)
    total_output_tokens = data.get("usage", {}).get("output_tokens", 0)

    if data.get("stop_reason") == "tool_use":
        tool_use_block = next(b for b in data["content"] if b["type"] == "tool_use")
        result = get_ticket(tool_use_block["input"]["ticket_id"])

        messages.append({"role": "assistant", "content": data["content"]})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block["id"],
                        "content": json.dumps(result),
                    }
                ],
            }
        )
        data = _invoke(messages, tools=tools)
        total_input_tokens += data.get("usage", {}).get("input_tokens", 0)
        total_output_tokens += data.get("usage", {}).get("output_tokens", 0)

    latency_ms = int((time.perf_counter() - start) * 1000)
    text_block = next(b for b in data["content"] if b["type"] == "text")

    return ChatResult(
        answer=text_block["text"],
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        latency_ms=latency_ms,
    )
