from dataclasses import dataclass


@dataclass
class ChatResult:
    answer: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
