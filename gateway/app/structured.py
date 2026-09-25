import json
import re

from pydantic import BaseModel, ValidationError

MAX_RETRIES = 2


def _strip_markdown_fences(text: str) -> str:
    # Models often wrap JSON in ```json ... ``` even when told not to.
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text


async def extract_structured_from_document(
    provider_module, prompt: str, file_bytes: bytes, mime_type: str, schema: type[BaseModel]
):
    """Same schema-validate-and-retry approach as chat_structured, but for a
    document (PDF or photo) instead of plain text — used by
    /v1/extract/document.
    """
    schema_prompt = (
        f"{prompt}\n\nRespond with ONLY valid JSON matching this schema, "
        f"no other text:\n{schema.model_json_schema()}"
    )

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        result = await provider_module.chat_with_document(schema_prompt, file_bytes, mime_type)
        try:
            parsed = schema.model_validate(json.loads(_strip_markdown_fences(result.answer)))
            return parsed, result
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            schema_prompt = (
                f"{prompt}\n\nYour previous answer was invalid: {exc}\n"
                f"Respond with ONLY valid JSON matching this schema, "
                f"no other text:\n{schema.model_json_schema()}"
            )

    raise ValueError(f"provider never returned valid JSON after {MAX_RETRIES + 1} attempts: {last_error}")


async def chat_structured(provider_module, prompt: str, schema: type[BaseModel]):
    """Calls a provider, asking for JSON matching `schema`. If the response
    isn't valid JSON for that schema, retries with the validation error fed
    back to the model, up to MAX_RETRIES times.
    """
    schema_prompt = (
        f"{prompt}\n\nRespond with ONLY valid JSON matching this schema, "
        f"no other text:\n{schema.model_json_schema()}"
    )

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        result = await provider_module.chat(schema_prompt)
        try:
            parsed = schema.model_validate(json.loads(_strip_markdown_fences(result.answer)))
            return parsed, result
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            schema_prompt = (
                f"{prompt}\n\nYour previous answer was invalid: {exc}\n"
                f"Respond with ONLY valid JSON matching this schema, "
                f"no other text:\n{schema.model_json_schema()}"
            )

    raise ValueError(f"provider never returned valid JSON after {MAX_RETRIES + 1} attempts: {last_error}")
