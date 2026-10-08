# Interview prep: "Tell me about your project"

This is your master script. [`docs/demo_script.md`](demo_script.md) has the exact commands to run
live; [`docs/interview_stories.md`](interview_stories.md) has three deep STAR-format stories for
follow-up questions. This file is the connective tissue: what you say first, how you prove it,
and how to handle the questions that will actually come.

## The 30-second answer (say this first, then stop and let them ask)

> "I built an internal AI gateway — one API that company apps call for AI, instead of every team
> hard-coding their own provider. It authenticates callers, routes across four model providers
> with automatic fallback, tracks cost and quality per request, and hosts two AI systems on top:
> a self-serve data analyst agent, and a production incident-response copilot that investigates
> issues and proposes a fix, but only acts after a human approves. I built it in 14 stages over
> several weeks, proved each stage against real behavior before moving to the next, and twice
> stood up real AWS infrastructure — not just locally — specifically to prove the riskier pieces
> hold up outside a local simulation."

Then stop. Let them pick a thread. Don't keep talking — the roadmap document you built this
course around says it explicitly: the stronger message is a repeatable engineering process, not
a claim that you can do everything.

## The one-sentence version (if they want it shorter)

> "Give me an ambiguous business problem or an existing AI system — I can evaluate it, diagnose
> the gap, prototype a fix, test it against a baseline, and move it toward production. This
> project is the proof: 14 real, verified pieces of exactly that loop."

## A-to-Z narrative, in order you actually built it

Use this if they say "walk me through how you built it" — don't recite all 14 parts; pick the arc.

1. **Started minimal (Part 1)**: one FastAPI endpoint, one free provider (Workers AI), exposed
   through a Cloudflare Worker and Tunnel — proved the simplest possible version end-to-end
   before adding anything else.
2. **Made it provider-agnostic (Part 2)**: added Bedrock (Claude), Vertex (Gemini), OpenAI behind
   one shared interface — the first real architecture decision, so no team's code has to know or
   care which model answers.
3. **Added resilience (Part 4)**: retries, fallback chains, circuit breakers, caching — proved
   with a deliberate forced failure that one provider going down doesn't break the platform.
4. **Added security (Part 5)**: per-app API keys, PII redaction, prompt-injection detection,
   audit logging — proved an SSN gets redacted before it ever reaches a model.
5. **Added evaluation discipline (Part 6)**: a real golden test set and scorecard across all 4
   providers, BEFORE touching cost optimization — you can't safely cut cost without first being
   able to measure quality.
6. **Added RAG (Part 7)**: answers grounded in real company docs, with citations, and proved it
   admits "I don't know" rather than inventing an answer when the docs don't cover something.
7. **Containerized and deployed (Parts 8-9)**: Docker, Kubernetes (local `kind`, then real AWS
   EKS) — the first of two real, billed, time-boxed cloud sessions, torn down immediately after
   verification, cost under $3 total across both.
8. **Added CI/CD with a real quality gate (Part 10)**: proved a deliberately corrupted prompt
   change gets blocked automatically before reaching production — not just "we have a pipeline,"
   but "I corrupted something on purpose and watched it get caught."
9. **Added cost visibility (Part 11)**: real dashboards, real cost-by-model data — then used that
   data to justify switching a workload to a cheaper provider, proven safe first via eval, not
   assumed.
10. **Built the first agent (Part 12)**: a data analyst agent — plain English in, validated SQL
    out, real database answer back. The centerpiece safety proof: a real prompt-injection attempt
    got the model to generate a destructive query, and a code-level validator — not the model's
    judgment — refused it.
11. **Built the second agent (Part 13)**: an incident-response copilot — investigates a real
    production issue, cites real evidence, proposes a fix, and only a human approval triggers a
    rollback, executed by a completely separate, more narrowly-privileged service.
12. **Documented it for a stranger (Part 14)**: README, architecture diagram, decision records,
    a real incident postmortem, an executive cost report — so someone who never talked to you
    could clone the repo and understand, run, and demo it.

## How you'll prove it live (don't just describe — show)

Three tiers, pick based on how much time you have:

**60 seconds — the one moment that lands hardest:**
Run the prompt-injection test against the Analyst Agent live (see
[`demo_script.md`](demo_script.md) section 4). Say out loud while it runs: "I'm about to try to
trick this into deleting data." Show the refusal. This is the single highest-density proof of
engineering judgment in the whole project — it demonstrates you test your own systems
adversarially, not just happily.

**5 minutes — the fuller arc:**
1. Playground: same prompt to two providers side by side, showing cost/latency differ.
2. Force a failure, show fallback catch it silently.
3. RAG: a real question answered with a citation, then an unanswerable one answered honestly.
4. The injection test (above).

**15+ minutes — the Incident Copilot (if they're SRE/platform-leaning):**
Full sequence from `demo_script.md` section 5 — inject a real bug, show the copilot cite real
evidence and propose a rollback, approve it, verify recovery, then run
`kubectl auth can-i patch deployments/gateway --as system:serviceaccount:...` live to prove the
investigating service and the acting service are genuinely different identities — not just a
code-level convention.

## Tools used, and why — the table they're actually listening for

Don't recite a tool list. For each one, say the ONE-LINE reason, because "why this and not X" is
what distinguishes someone who understands tradeoffs from someone who followed a tutorial.

| Tool | What it's for | Why this, not the obvious alternative |
|---|---|---|
| FastAPI | the core gateway | async, typed, auto-generates OpenAPI — Flask lacks native async |
| Cloudflare Worker + Tunnel | public entry point from a laptop | no port-forwarding or public IP needed; ngrok works but isn't the target production shape |
| Postgres + pgvector | usage/audit data AND vector search | one database for both relational and vector data, not two systems to keep in sync |
| Redis | cache, rate limits, circuit-breaker state | fast, ephemeral — exactly matches all three use cases |
| `sqlparse` (real tokenizer) | validating LLM-generated SQL | regex-based SQL safety checks are a known bypass surface — proved this myself, found two real bypasses before trusting it |
| Terraform | AWS infrastructure | plan/apply/destroy discipline — you can SEE what will change before it costs money |
| Kubernetes (kind locally, EKS for real) | running the gateway | same primitives locally (free) and in production (real) — no "works on my laptop" gap |
| Jenkins | CI/CD | self-hosted, full control over the pipeline stages, including a custom AI-review stage |
| Prometheus + Grafana | metrics/cost dashboards | pull-based, industry standard, free, and what Part 13's Incident Agent itself queries |
| A custom agent runtime (not LangChain) | both AI agents | deliberately small and auditable — every decision point is code I can point to and read, not framework internals. (Honest gap: this means no hands-on LangChain/LangGraph time — say this plainly if asked, see below.) |

## Questions they WILL ask, and the honest answer to each

**"Did you build the customer-facing chat app, or just the backend?"**
> "Just the backend — the AI gateway. There's no customer-facing chat widget in this project;
> every test I ran stood in for 'the company's app' calling the gateway, which is exactly how
> you'd test a backend before the frontend exists. The architecture diagram shows this honestly —
> 'client app' is the one box upstream of everything I built."

This is a real distinction you corrected mid-project — bring it up unprompted if it's relevant,
it shows self-awareness rather than overclaiming.

**"Can this integrate with [some tool they use, e.g. email, Slack, Salesforce]?"**
> "Architecturally yes — I built a generic tool-registration pattern and proved it twice with two
> completely different integrations (BigQuery and Kubernetes/Prometheus). Adding a new one is
> real work — auth, deciding what data is safe to expose, and a safety design for that specific
> tool's blast radius — not a checkbox. I haven't built that specific integration, but I've
> proven the pattern it would plug into, twice, independently."

**"What's the biggest gap in this project right now?"**
Pick ONE honestly, don't list five:
> "Fine-tuning — I never hit a problem in 14 parts that required it, which is actually consistent
> with how this role itself is supposed to work: reach for fine-tuning only when the simpler
> options (prompting, RAG, routing) genuinely can't solve it. But if asked to demonstrate
> fine-tuning specifically, I don't have a project to point to yet."

**"How do you know your tests actually tested what you think they tested?"**
This is a GOOD question to get, because you have a real story for it:
> "I found exactly this bug in my own work. During a cost-optimization eval, a canary test
> looked successful for 20 straight requests — but it turned out the 'new' candidate was already
> the default, so the test was comparing a scenario against itself. I only caught it by checking
> which provider actually answered each request, not just whether the requests succeeded."

**"Walk me through a real bug you found and fixed."**
Three ready-made, from `docs/interview_stories.md` — pick based on who's asking:
- Applied AI / Agent Engineer → the SQL validator subquery bypass
- SRE / Platform → the Incident Copilot's real-AWS demo (Pod Identity gap, missing Prometheus)
- Solutions/Consultant → the vendor-switch canary bug

## If you freeze or get a question you can't answer

Say this, it's true and it's the right instinct:
> "I don't know that one off the top of my head, but here's where I'd look and how I'd find out"
— then actually describe the lookup (which file, which log, which command). That's the
engineering-judgment answer the roadmap itself says to aim for — not pretending to know
everything.
