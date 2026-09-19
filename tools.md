# Tools
# PROJECT TOOLBOX — read this first, then wait for the brief

> Claude: this file is the "sync". Read it fully and remember it. It tells you the whole
> toolbox for this project, which need each tool serves, and how the tools connect.
> After you've read it, DO NOT start building. Reply exactly:
> "toolbox loaded — paste the project brief when ready" and wait.
> When the brief arrives, map each outcome to the right tool below and say why.

Project: Enterprise AI Control Plane (EACP) — one secure internal API that gives company apps
access to several AI providers, with routing, fallback, guardrails, cost tracking, evals, RAG,
agents and production operations. Built by a trainee who directs you in plain English.

Request path (target):
client app -> Cloudflare Worker (edge: key check, rate limit, WAF)
  -> Cloudflare Tunnel -> AI Gateway service (Python/FastAPI: auth, policy, routing, telemetry)
  -> providers: Claude via Amazon Bedrock | Gemini via Vertex AI | OpenAI | Llama on Workers AI
     (OpenAI, Anthropic-direct and Workers AI calls go through Cloudflare AI Gateway;
      Bedrock and Vertex are called with cloud IAM identities, no API keys)
Runs locally (Docker + kind) most days; on AWS EKS on Day 9 and Day 13 only.

Hard rules (every part):
- Secrets never in code or git. Local: .env (in .gitignore). Worker: `wrangler secret put`.
  AWS: Secrets Manager. Jenkins: Jenkins credentials. GCP: Workload Identity Federation, no key files.
- Least privilege for every IAM role, service account and DB user. Explain every IAM change.
- ASK BEFORE creating anything that costs money. State the expected cost.
- Cheapest model tier per provider. Prefer the mock provider for load and repeated tests.
- Every AI call records: request_id, app, provider, model, input/output tokens, latency_ms, cost_usd, status, fallback.
- Every service has a /health endpoint. One provider failing must never break the others.
- Build incrementally: one part at a time; deploy; verify; wait for "next".
- Explain every new term in one plain-English line.
- UNDERSTANDING CHECK after every part (see brief): ask me what we did, why this tool, and its use
  cases in this scenario — wait for my answers before the part counts as done.
- Keep PROGRESS.md updated after every part. When I ask "where are we?", "status" or "how far?",
  answer with the short status summary format from the brief (max 8 lines), read from PROGRESS.md.

The toolbox — need -> tool -> secret / identity:
| Need (outcome)                              | Tool                              | Secret / identity                         |
| AI engineering copilot                      | Claude Code in VS Code            | CLAUDE.md house rules                     |
| public front door, key check, rate limit    | Cloudflare Worker + WAF           | wrangler login; secret EDGE_SECRET        |
| reach laptop / cluster with no public IP    | Cloudflare Tunnel (cloudflared)   | tunnel token (secret TUNNEL_TOKEN)        |
| provider call logs, caching, analytics      | Cloudflare AI Gateway             | CF_ACCOUNT_ID, CF_AIG_NAME                |
| cheap open model + safety classifier        | Workers AI (Llama, Llama Guard)   | CF_API_TOKEN                              |
| core API: auth, policy, routing, telemetry  | Python + FastAPI ("gateway")      | —                                         |
| Claude (production path)                    | Amazon Bedrock (Claude Haiku)     | AWS IAM role/profile — no key             |
| Claude (comparison path, optional)          | Anthropic API via AI Gateway      | ANTHROPIC_API_KEY                         |
| GPT models                                  | OpenAI API via AI Gateway         | OPENAI_API_KEY                            |
| Gemini + text embeddings                    | Vertex AI                         | ADC locally, then Workload Identity Fed.  |
| usage records, app keys, audit, vectors     | Postgres + pgvector (RDS on EKS)  | DATABASE_URL                              |
| cache, quotas, circuit-breaker state        | Redis                             | REDIS_URL                                 |
| analytics warehouse, FinOps history         | BigQuery                          | read-only service account via WIF         |
| packaging                                   | Docker + Docker Compose           | —                                         |
| local Kubernetes                            | kind + kubectl + Helm             | —                                         |
| production Kubernetes                       | Amazon EKS (+ EKS Pod Identity)   | Pod Identity role                         |
| container registry                          | Amazon ECR                        | IAM                                       |
| production secrets                          | AWS Secrets Manager + External Secrets Operator | IAM                         |
| infrastructure as code                      | Terraform (aws + google providers)| AWS profile, gcloud ADC                   |
| source control + PRs                        | GitHub (+ gh CLI)                 | GH token (Jenkins credential)             |
| CI/CD + quality gates                       | Jenkins (in Docker)               | Jenkins credentials                       |
| image / dependency scanning                 | Trivy                             | —                                         |
| traces + metrics + dashboards               | OpenTelemetry, Prometheus, Grafana| —                                         |
| load / demo traffic                         | k6                                | client key for a demo app                 |
| docs, runbooks, ADRs, diagrams              | Markdown + Mermaid                | —                                         |

Cloud split (why each cloud is here):
- Cloudflare = edge + AI edge. AWS = platform runtime + Claude via Bedrock. GCP = Gemini + data (BigQuery).
- One Kubernetes only (EKS). No GKE, no Cloud Run, no Vertex Vector Search (always-on cost).

Pick by shape when two tools fit:
- structured records + vectors -> Postgres/pgvector; big analytical history -> BigQuery;
  hot/tiny/instant (cache, counter, quota, breaker) -> Redis.
- cheap/simple task -> Workers AI or Flash/mini tier; hard reasoning -> Claude Haiku first, escalate only if evals say so.
