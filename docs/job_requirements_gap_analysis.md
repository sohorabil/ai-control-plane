# Gap analysis: this project vs. the Applied AI / AI Solutions / Prototyping Engineer profile

Source: `Applied_AI_Solutions_Prototyping_Engineer_Roadmap.pdf`, section 2's 12 requirement bullets.
This is an honest self-check, not a sales pitch — every "Solid" claim below points to a specific
part and a specific real, verified moment; every "Gap" is a real gap, not hedging.

Use this to decide what to test yourself first (the solid stuff, to build real confidence you can
explain it) and what to be upfront about in an interview (the gaps, framed as "here's what I'd do
next" rather than pretending they don't exist — the roadmap itself says this is the stronger
message, not "I can do everything").

## Solid — directly built and verified

| Requirement | Where | What to go test yourself |
|---|---|---|
| **Business discovery & solution design** | Parts 1-14, every part's step 2 ("restate the stakeholder's problem in one sentence") | Read `PROGRESS.md`'s Part 12 origin — you yourself corrected the scope mid-build ("if marketing asks for a PDF in natural language..."), which is a real discovery moment, not scripted |
| **Rapid prototyping / PoCs** | Every part: build → verify → break-it, in hours not weeks | Pick any part, re-read its verification test, run it yourself |
| **Existing AI system & model evaluation** | Part 6 (golden set, scorecard across 4 providers), Part 11 (vendor-switch drill) | `evals/scorecard_2026-09-27.md` — run `python -m evals.scorecard` yourself |
| **Root-cause diagnosis** | Part 13 Incident Agent explicitly does this (prompt vs. retrieval vs. infra vs. deploy); Part 11's canary-bug diagnosis | Re-run the Part 13 incident demo locally against `kind`, or read `docs/incidents/2026-10-06-part13-eks-demo.md` |
| **RAG & enterprise knowledge** | Part 7 — hybrid search, citations, retrieval eval | `curl .../v1/rag/ask -d '{"question": "how long do I have to request a refund?"}'` — confirm citation, then ask something not in the docs and confirm it admits it doesn't know |
| **Agents, tool calling & workflows (MCP-style)** | Part 12 (Analyst Agent), Part 13 (Incident Agent) — both are real multi-step tool-using agents with step limits, human approval gates | `curl .../v1/ask -d '{"question": "top 5 teams by AI cost last week"}'`, then try the injection prompt in `docs/demo_script.md` section 4 |
| **Evaluation engineering** | Parts 6, 7, 11 — golden sets, retrieval hit@k, canary auto-rollback | Deliberately corrupt `evals/ci_smoke.jsonl` and watch the CI pipeline block it (Part 10's exact break-it test) |
| **Software & data engineering** | FastAPI, Postgres/pgvector, Redis, SQLAlchemy, real data pipelines (ingestion, chunking, usage export) throughout | Read `gateway/app/db.py` and `gateway/scripts/ingest_docs.py` |
| **AI-assisted development** | This entire project — built with Claude Code as build partner, you reviewing/testing/directing every part | This gap analysis itself is an example of it |
| **Cloud / MLOps / production** | Parts 8-10, 13 — Docker, kind, Helm, Terraform, Jenkins CI/CD, two real EKS sessions | `git log --oneline` — real commit history, real infra code in `terraform/` and `k8s/` |
| **Production adoption & iteration** | Part 12's feedback loop (thumbs up/down → human review → golden set growth) | `docs/demo_script.md` or `evals/golden.jsonl` — look for `type: "judged"` entries added from real feedback |

## Partial — built, but narrower than the full requirement

| Requirement | What's built | What's missing |
|---|---|---|
| **Orchestration frameworks (LangChain/LangGraph/LlamaIndex)** | A custom, lightweight agent runtime (`gateway/app/agents/runtime.py`) — deliberately framework-free, by design (ADR-worthy reasoning: full auditability, no framework magic) | Zero hands-on time with the actual named frameworks. If a job specifically wants LangGraph experience, this project proves the *concepts* (tool registry, step limits, planning) but not that exact tool. Worth a focused 1-2 day side exercise porting the Analyst Agent to LangGraph, just to be able to speak to it. |
| **Full-stack / TypeScript / React** | Real TypeScript exists (`worker/src/index.ts`, the Cloudflare Worker) and a server-rendered HTML playground (`/playground`) | No React/Node.js frontend anywhere — the Worker is edge logic, not a UI. If a role leans frontend-heavy, this is a real gap, not just thin coverage. |
| **Agent self-correction / retries within a single agent run** | Provider-level fallback/retry exists (Part 4, circuit breakers) and the Analyst/Incident Agents have step limits | Neither agent currently retries its own failed step with a corrected approach (e.g., "SQL failed validation, let the LLM see the error and try again") — they fail cleanly instead. This is a real, nameable gap: your agents are safe, but not self-healing. |

## Clean gaps — not touched, and worth saying so plainly

| Requirement | Status |
|---|---|
| **Fine-tuning / model adaptation** | Not built at all. Zero mentions anywhere in this project's 14 parts. The brief itself frames this correctly — "train or fine-tune when it's actually required, not as a default" — so the honest interview answer is "every problem this project hit was solvable without fine-tuning, which is itself consistent with the role's own stated philosophy," not "I haven't done it." But if asked to *demonstrate* fine-tuning specifically, there's nothing to point to yet. |
| **Specific AWS services named in postings (SageMaker, Lambda, S3, EventBridge, Step Functions)** | Not used. This project's AWS footprint is EKS, RDS, ECR, IAM, Secrets Manager, VPC — a Kubernetes-centric stack, not a serverless/ML-platform one. If a specific posting leans heavily on SageMaker or Step Functions, this project doesn't speak to those tools directly, though the underlying skills (IAM least-privilege, cost-bounded real deployments, monitoring) transfer. |
| **Stage 1's formal stakeholder-interview process** | This project's "stakeholder" was always a single-sentence framing device at the start of each part (CTO/CFO/CISO/etc.), not a real interview, workflow-mapping, or KPI-definition exercise with an actual business user. The *mechanism* (root-cause diagnosis, baseline-before-optimizing, evidence-based decisions) is real and repeatedly proven; the *discovery* half of the role (sitting with an ambiguous stakeholder and extracting the actual problem) was simulated, not practiced live. |

## How to use this for self-testing

1. Start with the "Solid" table — for each row, actually run the command yourself (don't just
   read that it worked). If something doesn't work the way `PROGRESS.md` describes, that's a real
   finding, not a failure — note it and we can investigate.
2. For the "Partial" rows, decide if they matter for the specific roles you're targeting. If a
   posting explicitly names LangGraph or React, that's worth a short dedicated exercise before
   relying on this project alone to cover it.
3. For the "Clean gaps," practice saying them out loud the way the roadmap itself recommends
   (section 4): not "I can't do that," but "that wasn't required by anything this project hit, and
   here's the reasoning for when I would reach for it" — fine-tuning and fixed-model-adaptation
   questions especially reward that framing over false confidence.
