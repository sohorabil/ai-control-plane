"""Checks the current canary candidate's eval score against the task's
quality_floor. If it's below the floor, automatically rolls back the canary
weight to 0 in routing.yaml. Meant to run after promoting a candidate to a
small canary weight, as a safety net before it gets more traffic.

Usage: python -m evals.canary_check
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "gateway"))

import asyncio

from evals.runner import run_eval

ROUTING_PATH = Path(__file__).parent.parent / "gateway" / "routing.yaml"


def load_routing() -> dict:
    return yaml.safe_load(ROUTING_PATH.read_text())


def rollback_canary(reason: str) -> None:
    text = ROUTING_PATH.read_text()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("candidate_weight:"):
            indent = line[: len(line) - len(line.lstrip())]
            lines[i] = f"{indent}candidate_weight: 0.0  # auto-rolled-back: {reason}"
            break
    ROUTING_PATH.write_text("\n".join(lines) + "\n")


async def main():
    config = load_routing()
    canary = config.get("canary", {})

    if canary.get("candidate_weight", 0.0) <= 0.0:
        print("No active canary (candidate_weight is 0). Nothing to check.")
        return

    task = canary["task"]
    candidate = canary["candidate"]
    quality_floor = config["tasks"][task]["quality_floor"]

    print(f"Checking canary candidate '{candidate}' for task '{task}' "
          f"(current weight: {canary['candidate_weight']}, floor: {quality_floor})...")

    summary = await run_eval(candidate, judge_provider_name="bedrock")
    print(f"Candidate score: {summary['score']*100:.1f}% "
          f"({summary['passed']}/{summary['total_cases']})")

    if summary["score"] < quality_floor:
        reason = f"score {summary['score']*100:.1f}% below floor {quality_floor*100:.0f}%"
        rollback_canary(reason)
        print(f"ROLLED BACK: {reason}")
    else:
        print("Candidate passes quality floor — canary weight unchanged.")


if __name__ == "__main__":
    asyncio.run(main())
