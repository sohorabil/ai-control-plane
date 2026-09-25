from pathlib import Path

import yaml

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str, version: int) -> dict:
    path = _PROMPTS_DIR / f"{name}_v{version}.yaml"
    return yaml.safe_load(path.read_text())
