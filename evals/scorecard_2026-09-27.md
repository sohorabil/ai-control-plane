# Eval scorecard — 2026-09-27

Golden set: `evals/golden.jsonl` (33 cases — 15 exact, 12 judged, 3 structured, plus 3 added later)
Judge model: Bedrock (Claude Haiku 4.5)

| Provider    | Score        | Total Cost (USD) | Avg Latency |
|-------------|--------------|-------------------|-------------|
| workers_ai  | 29/33 (88%)  | $0.000000         | 571ms       |
| vertex      | 30/33 (91%)  | $0.000512         | 3525ms      |
| bedrock     | 29/33 (88%)  | $0.008776         | 1126ms      |
| openai      | 28/33 (85%)  | $0.001004         | 1036ms      |

## Interpretation

- workers_ai matches Bedrock's quality (88%) at zero cost and roughly half the
  latency — strong case for keeping it as the default `chat` candidate.
- vertex scores highest (91%) but is ~5x slower — a reasonable second-tier
  fallback, not a good default for latency-sensitive tasks.
- openai scores lowest of the real providers (85%), still comfortably above
  the 80% quality_floor — safe as a canary candidate.
- Structured-output cases failed for workers_ai/bedrock when called via plain
  `chat()` (not the schema-validated `/v1/chat/structured` path from Part 3) —
  expected, and a good illustration of why that retry/validation wrapper
  exists: raw model output doesn't reliably self-format as JSON.

## Canary + rollback test (same day)

- Set `canary.candidate = openai`, `candidate_weight = 0.2` → `canary_check.py`
  scored it at 84.8%, above the 80% floor → weight kept unchanged.
- Set `canary.candidate = mock` (deliberately bad — mock can't answer real
  questions), same weight → scored 0.0% → automatically rolled back to
  `candidate_weight: 0.0`, with a reason written into `routing.yaml`.
- Confirmed via 10 live `/v1/chat/smart` calls that traffic never routed to
  mock after rollback — the routing code respects the rolled-back weight.
