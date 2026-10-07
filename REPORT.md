# REPORT — Enterprise AI Control Plane: what we built, what it costs, what's next

**Audience**: CEO / leadership — one page, no code required to read this.

## What we built

A single internal API that every company app calls for AI, instead of each team hard-coding its
own provider integration. It authenticates callers, applies security policy, routes across four
model providers with automatic fallback, tracks cost and quality per request, and hosts two
shared AI systems: a self-serve data analyst agent and a production incident-response copilot.

Four real internal teams now have a concrete capability they didn't have before:

- **Support**: a chat API with streaming, structured output, document extraction, and
  retrieval-augmented answers from company policy docs (with citations)
- **Data**: ask a plain-English question ("top 5 teams by AI cost last week"), get a safe,
  validated SQL query run against real usage data and a plain-English answer — with a hard,
  code-enforced guarantee that a destructive query is refused regardless of what the model
  generates
- **SRE**: a copilot that investigates a production issue, cites real evidence (metrics, logs,
  deploy history), proposes a fix, and — only after a named human approves — executes a rollback
  via a separately-privileged service that holds the only write credential in the system
- **Engineering**: every code and prompt change goes through an automated pipeline that blocks a
  quality regression before it reaches production, not after

## Cost

| Item | Cost |
|---|---|
| Local development (Docker, Kubernetes via `kind`, Jenkins, Postgres, Redis, Prometheus, Grafana, Jaeger) | **$0** — all free/local tools, used for nearly all of this project's work |
| BigQuery (usage analytics, eval history) | **$0** — within the free tier |
| Real AWS session #1 (Part 9 — prove the design on real EKS) | ~$1.50–2.50 |
| Real AWS session #2 (Part 13 — prove the incident-response loop on real EKS) | <$1 |
| **Total spend across the entire project** | **~$2–3.50**, against a $20 budget cap |

Real cloud infrastructure was only stood up for two short, explicitly-approved, fully-destroyed
sessions — not left running. Every resource created in both sessions was independently verified
gone afterward via direct AWS CLI checks, not just trusted from a tool's exit code.

**Ongoing cost if this ran in production** would be the real driver: an always-on EKS cluster +
RDS + model API usage, not the near-$0 figure above, which reflects a training/prototyping
project that deliberately keeps AWS bounded to short demo windows. A production cost estimate
would need real traffic volume assumptions that don't exist yet — a reasonable next step before
any real deployment decision.

## Quality and latency — a real vendor comparison, not a guess

The CFO's question ("can we move work to a cheaper model without answers getting worse?") was
answered with actual evaluation data, not intuition. A 33-case golden test set (exact-match,
LLM-judged, and structured-output cases) was scored against all four providers:

| Provider | Quality score | Cost/request | Avg latency |
|---|---|---|---|
| Workers AI (Llama) | 88% | $0 | 571ms |
| Vertex (Gemini Flash) | 91% | $0.0005 | 3525ms |
| Bedrock (Claude Haiku) | 88% | $0.0088 | 1126ms |
| OpenAI (gpt-4o-mini) | 85% | $0.001 | 1036ms |

*(full numbers: `evals/scorecard_2026-09-27.md`)*

This data directly justified a real production change: the `support_chat` task's most expensive
real workload (Bedrock, ~$0.00048/request measured from actual usage) was switched to Workers AI
after a fresh eval showed it scoring *higher* (90.9% vs. 87.9% baseline) at **zero** marginal
cost — a canaried, eval-proven switch with no quality-for-cost tradeoff (see
[`docs/adr/0005`](docs/adr/0005-workers-ai-over-bedrock-for-support-chat.md)). Bedrock remains
configured as a fallback, not removed.

**Recommendation**: default new workloads to the cheapest provider that clears the quality bar
for that specific task (proven by eval, not assumed), with a pricier provider kept as fallback —
the pattern this project used once should become the standard playbook for any future
cost-reduction request, rather than a one-time exercise.

## What's working well

- The provider-fallback and circuit-breaker design means one provider's outage degrades gracefully
  instead of breaking the whole platform — demonstrated directly, not just claimed (Part 4).
- The eval-gate CI pipeline has already proven it blocks a bad change: a deliberately corrupted
  golden set failed the pipeline at the gate stage, with production provably untouched (Part 10).
- The Analyst Agent's safety design held up against a real prompt-injection attempt that
  successfully got the model to generate a destructive query — the code-level validator, not the
  model's judgment, is what actually stopped it (Part 12).
- The Incident Copilot's human-approval boundary is enforced at the infrastructure level (a
  separate service identity), not just in application code — proven on real EKS, not only
  locally (Part 13).

## Known gaps / what to do next

- **Vertex (Gemini) via cross-cloud identity (AWS → GCP Workload Identity Federation) is
  unresolved** — Bedrock's simpler single-cloud auth path works on real EKS; Vertex's does not
  yet, for reasons not fully root-caused (parked to protect the cost budget during a live AWS
  session — see `architecture.md`). Any workload planning to run Vertex on real EKS needs this
  fixed first.
- **No production traffic volume exists yet** — every quality/cost number here is measured
  against a 33-case eval set and manual testing, not real usage at scale. Before any production
  rollout decision, this platform needs a pilot with one real internal team's actual traffic.
- **Prompt caching (provider-native)** was deferred early in the project and never revisited —
  worth evaluating once real traffic shows which prompts repeat often enough to matter.
- See [`PROGRESS.md`](PROGRESS.md)'s open-issues line for the complete, current list.

## Where to look for more detail

- [`README.md`](README.md) — how to run this yourself, full API surface
- [`architecture.md`](architecture.md) — system diagram, trust boundaries, folder map
- [`docs/adr/`](docs/adr/) — why each contested design decision was made the way it was
- [`docs/incidents/`](docs/incidents/) — a real incident report from the Part 13 production demo
- [`PROGRESS.md`](PROGRESS.md) — the complete, part-by-part build log: every tool choice, every
  real bug found and fixed, every verification result
