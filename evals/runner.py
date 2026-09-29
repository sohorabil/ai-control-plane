"""Eval runner: scores a provider against evals/golden.jsonl.

Usage: python -m evals.runner <provider> [--judge-provider <provider>]
Example: python -m evals.runner workers_ai --judge-provider bedrock
"""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "gateway"))

from app.pricing import cost_usd
from app.providers import bedrock, mock, openai, vertex, workers_ai

PROVIDERS = {
    "mock": mock,
    "workers_ai": workers_ai,
    "bedrock": bedrock,
    "vertex": vertex,
    "openai": openai,
}

GOLDEN_PATH = Path(__file__).parent / "golden.jsonl"


def load_cases(golden_path: Path = GOLDEN_PATH) -> list[dict]:
    return [json.loads(line) for line in golden_path.read_text().splitlines() if line.strip()]


def normalize(text) -> str:
    return re.sub(r"[^\w]", "", str(text).strip().lower())


def score_exact(case: dict, answer: str) -> bool:
    return normalize(case["expected"]) in normalize(answer)


def score_structured(case: dict, answer: str) -> bool:
    try:
        parsed = json.loads(re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", answer, flags=re.DOTALL))
    except json.JSONDecodeError:
        return False
    return all(str(parsed.get(k, "")).strip() == str(v).strip() for k, v in case["expected"].items())


async def score_judged(case: dict, answer: str, judge_module) -> bool:
    judge_prompt = (
        f"You are grading a customer support AI's response.\n\n"
        f"Original request: {case['prompt']}\n\n"
        f"AI's response: {answer}\n\n"
        f"Rubric: {case['rubric']}\n\n"
        f"Does the response satisfy the rubric? Reply with ONLY the word PASS or FAIL."
    )
    result = await judge_module.chat(judge_prompt)
    return "pass" in result.answer.strip().lower()


async def run_eval(
    provider_name: str, judge_provider_name: str, golden_path: Path = GOLDEN_PATH
) -> dict:
    provider = PROVIDERS[provider_name]
    judge = PROVIDERS[judge_provider_name]
    cases = load_cases(golden_path)

    results = []
    total_cost = 0.0
    total_latency = 0

    for case in cases:
        start = time.perf_counter()
        try:
            result = await provider.chat(case["prompt"])
            error = None
        except Exception as exc:
            result = None
            error = str(exc)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        if error:
            passed = False
        elif case["type"] == "exact":
            passed = score_exact(case, result.answer)
        elif case["type"] == "structured":
            passed = score_structured(case, result.answer)
        elif case["type"] == "judged":
            passed = await score_judged(case, result.answer, judge)
        else:
            passed = False

        cost = cost_usd(provider_name, result.input_tokens, result.output_tokens) if result else 0.0
        total_cost += cost
        total_latency += elapsed_ms

        results.append(
            {
                "id": case["id"],
                "type": case["type"],
                "passed": passed,
                "latency_ms": elapsed_ms,
                "cost_usd": cost,
                "error": error,
                "answer": result.answer if result else None,
            }
        )

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "provider": provider_name,
        "judge_provider": judge_provider_name,
        "total_cases": len(cases),
        "passed": passed_count,
        "score": passed_count / len(cases),
        "total_cost_usd": total_cost,
        "avg_latency_ms": total_latency // len(cases),
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=sorted(PROVIDERS.keys()))
    parser.add_argument("--judge-provider", choices=sorted(PROVIDERS.keys()), default="bedrock")
    parser.add_argument(
        "--golden-file",
        type=Path,
        default=GOLDEN_PATH,
        help="path to a .jsonl golden set (default: evals/golden.jsonl)",
    )
    args = parser.parse_args()

    summary = asyncio.run(run_eval(args.provider, args.judge_provider, args.golden_file))

    print(f"\n=== Eval results: {summary['provider']} ===")
    print(f"Score: {summary['passed']}/{summary['total_cases']} ({summary['score']*100:.1f}%)")
    print(f"Total cost: ${summary['total_cost_usd']:.6f}")
    print(f"Avg latency: {summary['avg_latency_ms']}ms")
    print("\nFailures:")
    for r in summary["results"]:
        if not r["passed"]:
            print(f"  [{r['id']}] {r['error'] or r['answer']}")
