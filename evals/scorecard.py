"""Runs the eval against multiple providers and prints a comparison scorecard.

Usage: python -m evals.scorecard <provider1> <provider2> ... [--judge-provider <provider>]
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "gateway"))

from evals.runner import run_eval


async def main(providers: list[str], judge_provider: str):
    summaries = []
    for provider in providers:
        print(f"Running eval for {provider}...")
        summary = await run_eval(provider, judge_provider)
        summaries.append(summary)

    print("\n" + "=" * 78)
    print(f"{'Provider':<14}{'Score':<16}{'Cost (USD)':<16}{'Avg Latency':<14}")
    print("=" * 78)
    for s in summaries:
        score_str = f"{s['passed']}/{s['total_cases']} ({s['score']*100:.0f}%)"
        cost_str = f"${s['total_cost_usd']:.6f}"
        print(f"{s['provider']:<14}{score_str:<16}{cost_str:<16}{s['avg_latency_ms']}ms")
    print("=" * 78)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("providers", nargs="+")
    parser.add_argument("--judge-provider", default="bedrock")
    args = parser.parse_args()

    asyncio.run(main(args.providers, args.judge_provider))
