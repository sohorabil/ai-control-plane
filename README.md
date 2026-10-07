# Enterprise AI Control Plane (EACP)

A secure internal AI gateway: company apps call **one API**, the platform authenticates them,
applies policy, routes across four model providers with automatic fallback, records cost and
quality, and hosts shared RAG and agent systems — deployed, monitored, evaluated, and rolled
back like a real production system.

Built in 14 parts over several real, mostly-local work sessions, with two short, deliberately
time-boxed real-AWS sessions (Parts 9 and 13) to prove the design against genuine cloud
infrastructure rather than just a local approximation of one.

## What problem this solves

Internal teams were hard-coding AI providers directly into their apps: no shared auth, no cost
visibility, no fallback when a provider has an outage, no safety review before a prompt change
ships, and no way for non-engineers to self-serve data questions or get help diagnosing a
production incident at 2am. This project is the platform that fixes all of that — one gateway,
four internal customers:

- **Support app** — chat, streaming, tool-calling, document extraction, RAG over company docs
- **Data team** — a SQL-generating Analyst Agent, safe by construction (code-enforced guardrails,
  not model judgment)
- **SRE team** — an Incident Copilot that investigates production issues and proposes (never
  executes without approval) a rollback
- **Engineering** — CI/CD with an AI-written-code quality gate, Trivy security scanning, and
  automated promotion/rollback

## Request path

```
client app
  -> Cloudflare Worker         (edge: checks x-client-key, injects EDGE_SECRET, proxies)
  -> Cloudflare Tunnel         (cloudflared — local process in dev, in-cluster pod on EKS)
  -> FastAPI gateway           (auth, guardrails, routing, telemetry)
  -> provider adapter          (uniform interface — swap providers without touching routing)
  -> AI provider               (Bedrock / Vertex / OpenAI / Workers AI / mock)
```

See [`architecture.md`](architecture.md) for the full request path, the three separate trust
chains (edge / app / cloud), and why local (`k8s/eacp-chart`) and real-AWS
(`k8s/eks-manifests`) deployments are deliberately separate manifests, not one parameterized
chart.

## What's actually running (real API surface)

| Endpoint | What it does |
|---|---|
| `GET /health` | liveness/readiness probe |
| `GET /metrics` | Prometheus scrape target |
| `POST /v1/chat` | the core authenticated chat endpoint, any provider |
| `POST /v1/chat/smart` | task-based routing with fallback, circuit breaker, caching |
| `POST /v1/chat/structured` | schema-validated JSON output, retries on invalid |
| `POST /v1/chat/stream` | SSE streaming |
| `POST /v1/chat/tools` | tool-calling (demo `get_ticket` tool) |
| `POST /v1/extract/document` | multimodal PDF/image field extraction |
| `POST /v1/rag/ask` | retrieval-augmented answers over `docs/`, with citations |
| `POST /v1/agent/analyst/ask` | natural-language question -> validated SQL -> BigQuery -> answer |
| `POST /v1/ask` | router: classifies a question as documents-vs-data, dispatches automatically |
| `POST /v1/feedback` | thumbs up/down, feeds the human-reviewed golden-set growth loop |
| `POST /v1/incident/investigate` | Incident Copilot: gathers evidence, proposes a root cause + action |
| `POST /v1/incident/approve-rollback` | the ONLY way a rollback executes — requires a named human approver |
| `GET /playground` | browser UI for manual testing against any provider |

## Run it locally

Everything below is free — no cloud account required.

```bash
# 1. Copy env template and fill in Cloudflare/OpenAI values (see .env.example)
cp .env.example .env

# 2. Build the gateway image and load it into a fresh local cluster
cd gateway && docker build -t eacp-gateway:local . && cd ..
kind create cluster --config k8s/kind-config.yaml
kind load docker-image eacp-gateway:local --name eacp-local

# 3. Deploy the full chart (Postgres, Redis, gateway all run in-cluster)
helm install eacp k8s/eacp-chart -f k8s/eacp-chart/values.yaml

# 4. Seed demo apps (support-app, analyst-agent) into Postgres
kubectl exec deploy/gateway -- python -m scripts.seed_apps

# 5. Port-forward and open the playground
kubectl port-forward svc/gateway 8000:8000
open http://localhost:8000/playground
```

For the observability stack (Prometheus/Grafana/Jaeger), CI/CD (Jenkins), and the real-AWS
deploy path, see the per-part build notes in [`PROGRESS.md`](PROGRESS.md) — each includes the
exact commands used.

## Real cloud, on purpose, twice

This project runs on free/local tools almost all the time. Real AWS (EKS + RDS) was stood up
**twice**, each time with an explicit cost estimate stated up front, verified end-to-end, and
torn down (`terraform destroy`) in the same session — never left running:

- **Part 9** — proved the full edge-to-provider path on real EKS, including cross-cloud identity
  (AWS Pod Identity for Bedrock; GCP Workload Identity Federation for Vertex, which surfaced a
  real unresolved permission issue, documented rather than hidden)
- **Part 13** — proved the Incident Copilot's investigate → human-approve → rollback → verify
  loop against a freshly-provisioned real cluster, finding and fixing three genuine
  production-environment gaps that a local `kind` cluster can't surface (see
  [`PROGRESS.md`](PROGRESS.md) Part 13 for the full list)

Total real-AWS spend across both sessions: **under $4**, well inside the project's $20 cap.

## Status

All 14 parts complete. See [`PROGRESS.md`](PROGRESS.md) for the full build log — what was built,
why each tool was chosen over the obvious alternative, every real bug found and fixed, every
verification result, and every understanding-check outcome, part by part.

- [`architecture.md`](architecture.md) — how the pieces are wired, trust boundaries, folder map
- [`docs/adr/`](docs/adr/) — why key decisions were made the way they were
- [`docs/runbooks/`](docs/runbooks/) — operational playbooks (also served live via RAG)
- [`docs/incidents/`](docs/incidents/) — real incident report from the Part 13 demo
- [`REPORT.md`](REPORT.md) — cost/latency/quality findings and recommendation
- [`CLAUDE.md`](CLAUDE.md) — house rules this project was built under (secrets, cost discipline, etc.)
