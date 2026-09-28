# CLAUDE.md — house rules for this project

This project is built in 14 parts, one at a time, following the protocol in `project_breif.md`
and the toolbox in `tools.md`. `project.json` mirrors both in machine-readable form.

**Before working on auth, routing, or infra changes**, read `architecture.md` first — it
documents the real request path, the three separate trust chains (edge/app/cloud), and why
`k8s/eacp-chart` and `k8s/eks-manifests` are deliberately separate. It exists specifically
because Part 9's cross-cloud auth debugging would have been faster with this written down
beforehand instead of re-derived from code under a live AWS billing clock.

## Hard rules (apply to every part, no exceptions)

- **Secrets never in code or git.** Local secrets go in `.env` (gitignored). Cloudflare Worker
  secrets via `wrangler secret put`. AWS secrets via Secrets Manager. Jenkins via Jenkins
  credentials. GCP via Workload Identity Federation — never a downloaded key file.
- **Least privilege** for every IAM role, service account, and DB user. Explain every IAM
  change in plain English when it's made.
- **Ask before creating anything that costs money.** State the expected cost first. Spend cap
  for the whole project: $20.
- **Cheapest model tier per provider.** Prefer the mock provider for load tests and repeated
  testing.
- **Every AI call records telemetry**: request_id, app, provider, model, input_tokens,
  output_tokens, latency_ms, cost_usd, status, fallback.
- **Every service has a `/health` endpoint.** One provider failing must never break the others.
- **Build incrementally**: one part at a time, deploy, verify, wait for the trainee to say
  "next" before starting the next part.
- **Explain every new technical term** in one plain-English line when it's introduced.
- **Understanding check after every part**: ask what we built, why this tool (vs. the obvious
  alternative), and its use cases in this scenario — wait for answers before marking the part
  done. Trainee can say "skip check" (log it in PROGRESS.md) or "explain again".
- **Keep `PROGRESS.md` updated** after every part. Status questions ("where are we?", "status",
  "how far?") get answered ONLY in the 8-line summary format, read from `PROGRESS.md` and the
  repo — never from memory.

## Build protocol for each part (from `project_breif.md`)

1. Read current repo state first.
2. Restate the stakeholder's problem in one sentence.
3. Name the tool(s) and why (1 line each), plus why not the obvious alternative.
4. Show how the new piece connects to existing ones (who calls whom, auth, data shape).
5. State expected cost; ask before anything paid.
6. Explain new terms in plain English.
7. Build only that part; list changed files and exact commands to run.
8. Give a concrete verification test and expected result.
9. Give one "break it" experiment.
10. Run the understanding check; wait for answers; give feedback.
11. Update `PROGRESS.md`.
12. Stop and wait for "next". If a key/account isn't ready, stop and give the exact setup
    command instead of proceeding.

## Architecture (target end state)

```
client app -> Cloudflare Worker (edge: key check, rate limit, WAF)
  -> Cloudflare Tunnel -> AI Gateway service (Python/FastAPI: auth, policy, routing, telemetry)
  -> providers: Claude via Amazon Bedrock | Gemini via Vertex AI | OpenAI | Llama on Workers AI
```

Runs locally (Docker + kind) most days; on AWS EKS on Day 9 and Day 13 only.

See `tools.md` for the full toolbox (need → tool → secret/identity), `project_breif.md` for all
14 parts in detail, and `architecture.md` for how the pieces actually connect.
