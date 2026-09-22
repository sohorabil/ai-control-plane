from pathlib import Path

import yaml

_PRICES_PATH = Path(__file__).parent.parent / "prices.yaml"
_prices = yaml.safe_load(_PRICES_PATH.read_text())


def cost_usd(provider: str, input_tokens: int, output_tokens: int) -> float:
    rates = _prices.get(provider, {"input_per_1k": 0.0, "output_per_1k": 0.0})
    return (input_tokens / 1000) * rates["input_per_1k"] + (
        output_tokens / 1000
    ) * rates["output_per_1k"]
