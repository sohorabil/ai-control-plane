# ADR 0005 — `workers_ai` (Llama) promoted over `bedrock` (Claude Haiku) as `support_chat`'s primary provider

**Status**: Accepted
**Date**: 2026-10-05 (Part 11 vendor-switch drill)

## Context

Part 11's observability work (Prometheus, BigQuery usage export) made real per-provider cost
visible for the first time. The `support_chat` task's existing default, `bedrock` (Claude
Haiku), was found to be the most expensive real workload at **~$0.00048/request** — 3-5.5x
pricier than the alternatives evaluated.

## Decision

Promote `workers_ai` (Llama via Cloudflare Workers AI) to primary for the `support_chat` task,
keeping `bedrock` as a fallback (not removed) in `routing.yaml`.

## Why

This wasn't a cost-vs-quality tradeoff decision — it was only made because the eval evidence
showed no tradeoff existed. Two cheaper candidates were evaluated against the existing 33-case
golden set before any routing change:

| Provider | Eval score | Cost/request |
|---|---|---|
| `bedrock` (baseline) | 87.9% | ~$0.00048 |
| `workers_ai` | 90.9% | $0 |
| `openai` | 87.9% | ~$0.001 |

`workers_ai` beat the baseline's quality score at zero marginal cost. The switch was canaried
first (20% weight) to confirm the split was genuinely random against real live traffic — not
simulated — before fully promoting it, and the canary mechanism itself (`routing.yaml`'s
`candidate_weight`, Part 6) is what made "try it on a slice of traffic before committing"
possible without redeploying code.

A genuine bug was caught and fixed during this process, not after: the first canary attempt
measured nothing, because `workers_ai` was already `support_chat`'s first-choice candidate
before any change — the canary's reorder-the-candidate-list logic was a no-op, and 20/20 test
requests landing on it was consistent with both "the canary worked" and "the canary did
nothing," indistinguishable from request success/failure alone. Caught only by checking *which
provider actually answered each request*. Fixed by genuinely making `bedrock` primary first
(matching the real pre-switch state), which made the canary's effect observable: a real 13/7
split against a configured 20% weight.

## Consequences

- `support_chat` traffic now defaults to `workers_ai`; `bedrock` remains configured as a fallback
  candidate, so a `workers_ai` outage degrades to the previous (costlier but known-good) path
  rather than failing outright.
- This result is specific to `support_chat`'s question style (support-style exchanges, scored
  against this project's golden set) — it should not be read as "Llama is always better than
  Claude Haiku." Any future provider-cost decision should repeat this same eval-before-switch
  pattern, not copy this conclusion into a different task type without re-testing.
- The canary-measured-nothing bug is the generalizable lesson here, independent of which
  provider won: "the request succeeded" is not evidence a test actually exercised what it was
  meant to test — verify the mechanism (which provider actually answered), not just the outcome.
