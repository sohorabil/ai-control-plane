# Project Brief
# PROJECT BRIEF — Enterprise AI Control Plane (14 parts)

> Claude: build this project in parts, using the toolbox I gave you (TOOLS.md). For each part,
> choose the right tool from that toolbox to meet the outcome.
>
> Build protocol — follow exactly, every part:
> 1. Read the current repository first.
> 2. Restate the stakeholder's problem in one sentence.
> 3. Name the tool(s) you'll use and why they fit (1 line each), plus "why not" the obvious alternative.
> 4. Show how the new piece connects to existing ones (who calls whom, auth, data shape).
> 5. State expected cloud/API cost. ASK before creating anything paid.
> 6. Explain each new term in one plain-English line.
> 7. Build ONLY this part. List changed files and the exact commands I must run.
> 8. Give me a concrete verification test (URL, command, metric or dashboard) and what I should see.
> 9. Give me one "break it" experiment for this part.
> 10. After I confirm the verification and break-it test, run the UNDERSTANDING CHECK (below).
> 11. Update PROGRESS.md (part done, what was built, tools used, spend so far, open issues).
> 12. STOP and wait for me to type "next". If a key/account isn't ready, stop and give the exact command.
>
> UNDERSTANDING CHECK — after every part, ask me these, one message, then wait for my answers:
>   Q1 What did we build in this part, in plain words, and how does it connect to what already existed?
>   Q2 Why did we use <tool> here — and why not <the obvious alternative>?
>   Q3 What are the use cases of <tool> in this project's scenario (which stakeholder problem does it solve)?
>       Give one more real-world use case of it at another company.
> Then: tell me what I got right, correct anything wrong or missing in simple language, and if a
> key idea was missed, re-ask that one question once. Don't lecture; keep it short and encouraging.
> I can say "explain again" or "skip check" (log skipped checks in PROGRESS.md).
>
> STATUS SUMMARY — whenever I ask "where are we?", "status", "how far?" or similar, reply ONLY with:
>   📍 Now: Part N of 14 — <title> — <current step>
>   ✅ Done: Parts … (one short phrase each)
>   ⏭ Next: <next 1–2 steps>
>   💰 Spend so far: ~$X (estimated) · ☁️ Running now: <anything billable, or "nothing">
>   🎓 Understanding checks: passed X / done Y (skipped: …)
>   ⚠️ Open issues: <max 2, or "none">
> Keep it under 8 lines. Read it from PROGRESS.md and the repo, not from memory.

Security rules: never hard-code secrets; never commit .env; least privilege; explain IAM changes;
ask before paid resources; agents never get destructive actions without human approval.
Engineering rules: every service has /health; changes must be testable; every AI call emits
model/latency/token/cost telemetry; one provider failure must not crash others; staging before
production; a quality regression can block or roll back a release.

What we're building: a secure internal AI platform. Company apps call ONE API; the platform
authenticates them, applies policy, routes to the right model across Bedrock, Vertex AI, OpenAI and
Workers AI, falls back on failure, records cost/latency/quality, and hosts shared RAG and agents.
It is deployed, monitored, evaluated, migrated and rolled back like a production system.
Internal customers: Support app, Data team (Analyst Agent), SRE team (Incident Copilot), Engineering (CI).

PART 1 — Live front door + first AI answer
  Stakeholder (CTO): "Give me one URL our apps can call for AI — today."
  Outcome: repo + CLAUDE.md; FastAPI gateway with /health and /v1/chat answering via Workers AI
  through Cloudflare AI Gateway; exposed by Cloudflare Tunnel behind a Worker that requires a client
  key header and adds EDGE_SECRET; gateway rejects requests without EDGE_SECRET.
  Done when: curl to the workers.dev URL with a key returns an AI answer; without a key -> 401.

PART 2 — One API, four models
  Stakeholder (VP Eng): "Teams keep hard-coding providers. Hide them behind one interface."
  Outcome: provider adapters for Bedrock (Claude Haiku), Vertex (Gemini Flash), OpenAI (mini tier),
  Workers AI, optional Anthropic-direct, and a mock provider; one request/response shape; local
  Postgres (docker compose) usage table; prices.yaml price table; every call logged with tokens,
  latency and cost; /playground page to send one prompt to all models side by side.
  Done when: playground shows all providers' answers with latency + cost; usage rows accumulate.

PART 3 — AI engineering toolkit
  Stakeholder (Product lead): "Our support app needs reliable JSON, live typing, and ticket lookups."
  Outcome: structured output validated against a schema (retry on invalid); streaming endpoint (SSE);
  tool calling with a demo get_ticket tool; prompt caching where the provider supports it;
  versioned prompt registry in prompts/; multimodal: /v1/extract/document pulls the same schema-style
  fields out of an invoice PDF or photo.
  Done when: /v1/extract always returns schema-valid JSON; /v1/chat/stream streams; a tool call works;
  a sample invoice PDF and a phone photo of it both return correct fields.

PART 4 — Smart routing + resilience
  Stakeholder (CFO): "Stop using the most expensive model for everything — without hurting quality."
  Outcome: routing.yaml (task type -> ordered candidates, quality floor, latency budget); timeouts,
  retries with backoff+jitter, fallback chain, circuit breaker; Redis for response cache, per-app quota
  and breaker state.
  Done when: forcing the mock provider to return 429 triggers fallback; repeat prompt hits cache.

PART 5 — Security + guardrails
  Stakeholder (CISO): "Who sent what data to which model? And stop PII leaking."
  Outcome: per-app API keys (hashed) with roles and allowed models; PII detection (redact or block per
  policy); prompt-injection check (heuristics + Llama Guard on Workers AI); audit log table; edge rate
  limit; Vertex access switched from local ADC to Workload Identity Federation from an AWS role.
  Done when: a prompt containing an SSN is redacted/blocked and audited; an app can't use a model it
  isn't allowed; Gemini calls succeed with no GCP key file anywhere.

PART 6 — Evals + model migration
  Stakeholder (CFO): "We pay a lot for AI. We can't stop teams using it — can we move work to a cheaper
  company's model without answers getting worse?"
  Outcome: evals/golden.jsonl (~30 cases); eval runner (exact checks + LLM-as-judge with a different
  model); scorecard of quality, latency, cost per model; canary weights in routing.yaml; automatic
  rollback if the candidate's score drops below threshold.
  Done when: a scorecard compares current vs candidate; a deliberately bad prompt change fails the eval.

PART 7 — RAG platform
  Stakeholder (Support manager): "Answer from OUR docs, with sources."
  Outcome: docs/runbooks + docs/policies (synthetic, written with Claude); ingestion (chunk ->
  Vertex embeddings -> pgvector); /v1/rag/ask with citations; chunk-size experiment; retrieval eval (hit@k);
  hybrid search (Postgres full-text keyword search + vector search, merged) and a reranker model.
  Done when: answers cite the right doc; retrieval eval compares vector-only vs hybrid vs hybrid+rerank.

PART 8 — Containers, local Kubernetes, Terraform plan
  Stakeholder (Platform lead): "It works on your laptop. Make it deployable."
  Outcome: Dockerfiles; kind cluster; manifests/Helm for gateway, Redis, Postgres, cloudflared; probes;
  Terraform for AWS (VPC public subnets/no NAT, ECR, EKS, RDS, IAM, Secrets Manager) and GCP
  (BigQuery datasets, WIF pool); `terraform plan` only for AWS; apply only the free GCP pieces.
  Done when: platform runs in kind reachable via Tunnel; terraform plan output explained in plain English.

PART 9 — EKS key day 1
  Stakeholder (CTO): "Show me it running on real cloud — and show me it costs nothing overnight."
  Outcome: ASK first, then terraform apply; push image to ECR; deploy to EKS with Pod Identity
  (Bedrock + WIF) and External Secrets; cloudflared in-cluster; verify through the Worker; terraform destroy.
  Done when: the Worker URL answers from EKS; after destroy, AWS shows no EKS/RDS/ENIs left.

PART 10 — CI/CD with AI gates
  Stakeholder (VP Eng): "AI-written code and prompt changes are shipping too fast to trust."
  Outcome: Jenkins in Docker; GitHub webhook via Tunnel; pipeline: lint+tests (sqa-check) -> Trivy ->
  terraform validate -> ai-breakage-check (golden subset) -> AI code review comment on the PR via our
  own gateway -> deploy to kind staging -> promote-staging-to-live (kind prod namespace) -> rollback job.
  Done when: a PR with a broken prompt is blocked by the eval gate; a good PR promotes.

PART 11 — Observability + AI FinOps
  Stakeholder (CFO): "AI spend doubled. Which team, which model, and why?"
  Outcome: OpenTelemetry traces edge->gateway->provider; Prometheus metrics (P50/P95 per model, tokens,
  cost, fallback rate, cache hit rate); Grafana dashboards; daily batch export of usage to BigQuery;
  cost-by-team query. VENDOR-SWITCH DRILL: find the most expensive workload, eval two cheaper models from
  other providers, canary the winner, switch, show before/after cost.
  Done when: Grafana shows cost by app/model; a cost spike is traced to its cause; one workload is moved to
  a cheaper provider with eval-proven quality and a measured saving.

PART 12 — Agent platform + Data Analyst Agent
  Stakeholder (Head of Data): "Execs keep asking analysts simple questions. Make it self-serve — safely."
  Outcome: reusable agent runtime (loop, tool registry, MCP tools, step limits, telemetry, approval hook);
  Analyst Agent: schema RAG -> SQL generation -> SQL validator (SELECT only, allowed tables, LIMIT) ->
  BigQuery dry run (bytes cap) -> read-only execution -> plain-English answer. Feedback loop: thumbs
  up/down on answers (playground + agents) -> feedback table -> I review thumbs-down cases -> script adds
  approved ones to evals/golden.jsonl.
  Done when: "top 5 teams by AI cost last week" is answered; a DELETE or huge scan is refused; a
  thumbs-down answer becomes a new golden case after my review.

PART 13 — SRE Incident Copilot + production demo (EKS key day 2)
  Stakeholder (SRE lead): "When prod breaks at 2am, give on-call a head start."
  Outcome: Incident Agent on the agent runtime with read-only tools (Prometheus, kubectl events/logs,
  recent deploys, runbook RAG) -> root-cause hypotheses -> proposed action -> HUMAN APPROVAL -> rollback.
  ASK first, then EKS up via Terraform + Jenkins deploy; k6 demo traffic (mock mode mostly, one short real
  run); inject a bad deploy; copilot investigates; approved rollback; verify recovery; terraform destroy.
  Done when: copilot names the bad deploy with evidence, rollback is approved and recovery verified.

PART 14 — Capstone
  Stakeholder (CEO): "One page: what did we build, what does it cost, what should we do next?"
  Outcome: README, Mermaid architecture diagram, ADRs, runbooks, incident report from Day 13,
  REPORT.md (cost/latency/quality per model + recommendation), demo script, interview story per role.
  Done when: a stranger can understand, run and demo the platform from the repo alone.