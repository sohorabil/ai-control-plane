"""Compares retrieval strategies (vector, keyword, hybrid, hybrid+rerank)
using hit@k against evals/retrieval_golden.jsonl: did the expected source
document appear anywhere in the top-k results?

Usage: python -m evals.retrieval_eval [--top-k 3]
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "gateway"))

from app.retrieval import hybrid_search, keyword_search, rerank, vector_search

GOLDEN_PATH = Path(__file__).parent / "retrieval_golden.jsonl"

STRATEGIES = {
    "vector": vector_search,
    "keyword": keyword_search,
    "hybrid": hybrid_search,
}


def load_cases() -> list[dict]:
    return [json.loads(line) for line in GOLDEN_PATH.read_text().splitlines() if line.strip()]


async def run_strategy(strategy_name: str, top_k: int) -> dict:
    cases = load_cases()
    hits = 0

    for case in cases:
        if strategy_name == "hybrid_rerank":
            candidates = await hybrid_search(case["question"], top_k=top_k * 2)
            results = await rerank(case["question"], candidates, top_k=top_k)
        else:
            results = await STRATEGIES[strategy_name](case["question"], top_k=top_k)

        found_sources = {r["source_path"] for r in results}
        if case["expected_source"] in found_sources:
            hits += 1

    return {"strategy": strategy_name, "hits": hits, "total": len(cases), "hit_rate": hits / len(cases)}


async def main(top_k: int):
    results = []
    for strategy in ["vector", "keyword", "hybrid", "hybrid_rerank"]:
        print(f"Running {strategy}...")
        results.append(await run_strategy(strategy, top_k))

    print(f"\n{'Strategy':<16}{'hit@' + str(top_k):<12}")
    print("=" * 28)
    for r in results:
        print(f"{r['strategy']:<16}{r['hits']}/{r['total']} ({r['hit_rate']*100:.0f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(main(args.top_k))
