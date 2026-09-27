# Retrieval eval scorecard — 2026-09-27

Golden set: `evals/retrieval_golden.jsonl` (12 questions across 7 docs)
Metric: hit@3 — did the expected source document appear in the top 3 results?

| Strategy       | hit@3         |
|----------------|---------------|
| vector         | 12/12 (100%)  |
| keyword        | 1/12 (8%)     |
| hybrid         | 12/12 (100%)  |
| hybrid_rerank  | 12/12 (100%)  |

## Interpretation

- Pure keyword (Postgres full-text search) badly underperforms because
  customer questions rarely share exact wording with policy documents (e.g.
  "how long do I have to request a refund?" vs. "refunds... within 30 days
  of purchase" — no shared distinctive keywords).
- Vector search alone already hits 100% on this test set — semantic
  similarity closes the wording gap keyword search can't.
- Hybrid and hybrid+rerank tie with vector at 100% here — this dataset (12
  questions, 7 short docs) is likely too small/easy to show reranking's
  benefit; a larger, harder golden set (near-duplicate docs, ambiguous
  questions) would be needed to see real separation between these three.
- Practical takeaway: default to `hybrid` for production (keyword's
  precision on exact-term queries + vector's semantic recall), skip the
  added latency/cost of reranking unless a harder eval set shows it's
  needed.
