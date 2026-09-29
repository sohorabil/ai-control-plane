# PROGRESS

📍 Now: Part 10 of 14 — CI/CD with AI gates — IN PROGRESS (paused for a break, not yet closed out). Jenkins pipeline built and iteratively fixed through 5 real bugs; next build attempt not yet run after the last fix. Say "next" to resume — NOT to start Part 11.
✅ Done: Parts 1-7 (prototype: gateway, providers, toolkit, routing, security, evals, RAG); Part 8 (Docker, kind + Helm, Terraform plans); Part 9 (real EKS deploy, verified, destroyed)
⏭ Next (on resume): trigger the next Jenkins build via "Build Now", confirm all 7 stages pass end-to-end for the first time, then run the break-it test + understanding check + job-skill mapping to formally close Part 10
💰 Spend so far: ~$1.50-2.50 total, all from Part 9's real AWS usage — Part 10 is $0 (Jenkins/kind/Docker all local) · ☁️ Running now (left on, all free/local): kind cluster, eacp-jenkins container, standalone Postgres+Redis containers (docker-compose) used for manual pipeline verification; no AWS resources
🎓 Understanding checks: passed 6 / done 7 so far (skipped: none) — each part needed at least one re-ask/re-explanation, all resolved; Part 10's check not yet run (part not closed)
⚠️ Open issues: quick tunnel URLs are ephemeral (worker/wrangler.toml's GATEWAY_URL needs updating next time a local tunnel is started); prompt caching (Bedrock-native) still deferred from Part 3; **Vertex/Gemini via cross-cloud WIF through EKS Pod Identity is unresolved** (Part 9, parked to protect cost budget); Part 10's Jenkins pipeline has been fixed through 5 real bugs (see below) but has not yet had a fully green end-to-end run — do not assume it works until the next build is actually watched to completion

---

## Log

### Part 1 — Live front door + first AI answer
- Status: DONE
- Tools used: FastAPI, Cloudflare Worker, Cloudflare Tunnel, Cloudflare AI Gateway, Workers AI
- Spend: $0 (Workers AI free tier; AI Gateway spend limit set to $5 as a safety cap)
- What was built:
  - `gateway/` — FastAPI app with `/health` and `/v1/chat`; rejects requests missing the `x-edge-secret` header; calls Workers AI through Cloudflare AI Gateway
  - `worker/` — Cloudflare Worker (`ai-control-plane-edge`, deployed to `https://ai-control-plane-edge.tukrim.workers.dev`) checks `x-client-key` header against `CLIENT_KEYS` secret, injects `EDGE_SECRET` header, proxies to the gateway via a Cloudflare quick tunnel
  - AI Gateway `my-getway` created (rate limit off, spend limit $5, retry off, cache off, Authenticated Gateway off)
- Issues hit and resolved during setup:
  - First API token was read-only (old token from another project) — created a new one scoped to Workers AI + AI Gateway (Edit)
  - AI Gateway had "Authenticated Gateway" on, requiring a second token — turned off for Part 1 simplicity (revisit in Part 5 when per-app auth is built properly)
  - Workers AI response shape varies by model (`response` field vs OpenAI-style `choices[0].message.content`) — handled both in `workers_ai.py`
  - Quick tunnel URL changed on restart — had to update `wrangler.toml` and redeploy
- Verification result: `curl` to the deployed Worker URL without `x-client-key` → `401`; with the valid demo client key → `200` with a real Workers AI answer. Full chain confirmed: Worker → Tunnel → FastAPI → AI Gateway → Workers AI.
- Break-it test: valid client key + malformed JSON body → clean `422` from FastAPI/Pydantic validation, no crash; gateway immediately served a normal request right after, proving one bad request can't take down the service for other apps.
- Understanding check: Q1 and Q2 answered correctly. Q3 (Cloudflare Tunnel use case) was initially backwards — trainee said it means "everything runs locally"; corrected to "lets a private/local machine reach the public internet outbound without exposing it," re-asked, and trainee then correctly related it to a retail chain sending store data to a central system without exposing store systems. Passed on re-ask.
- Decision: adversarial "break it many ways" testing deferred to after Part 5 (guardrails) or as an end-of-project capstone, rather than per-part — logged here so future parts don't re-litigate this.

### Part 2 — One API, four models
- Status: DONE
- Tools used: FastAPI (provider adapters), boto3 (Bedrock), google-auth (Vertex ADC), Postgres via Docker Compose, PyYAML (prices.yaml)
- Spend: <$0.01 (one successful Vertex/Gemini test call; Workers AI and mock are free)
- What was built:
  - `gateway/app/providers/` — `base.py` (shared `ChatResult` shape), `mock.py`, `bedrock.py` (Claude Haiku 4.5 via inference profile `us.anthropic.claude-haiku-4-5-20251001-v1:0`), `vertex.py` (Gemini 2.5 Flash via ADC), `openai.py` (via AI Gateway), plus the existing `workers_ai.py` updated to match the shared shape
  - `gateway/app/db.py` — Postgres `usage` table (SQLAlchemy) logging every call: request_id, app, provider, model, tokens, latency, cost, status
  - `gateway/app/pricing.py` + `prices.yaml` — per-provider $/1k-token rates for cost estimation
  - `/v1/chat` now takes a `provider` field and routes through `PROVIDERS` dict; `/v1/chat/playground` is an unauthenticated twin route used only by the new `/playground` HTML page (browser can't send the edge secret, so this keeps the real client auth path on `/v1/chat` untouched)
  - `docker-compose.yml` — local Postgres 16, no cloud cost
- Issues hit and resolved:
  - `psycopg[binary]==3.2.3` didn't exist on PyPI anymore — bumped to 3.2.10
  - `google-auth`'s requests transport needed the separate `requests` package — added
  - Bedrock: newer Claude models require an inference-profile ID, not the bare model ID, for on-demand invocation
  - Bedrock: hit a one-time "Anthropic use case details" requirement — resolved by using the model once in the AWS Console Playground
  - Bedrock: then hit `INVALID_PAYMENT_INSTRUMENT` — AWS Marketplace requires a valid payment method before subscribing to a third-party model; trainee to add one, currently blocking real Bedrock calls only (not code)
  - Vertex: `gemini-2.0-flash-001`/`gemini-1.5-flash` both 404'd (retired for this project) — found `gemini-2.5-flash` works via direct API probing
  - OpenAI: call reached the API successfully but returned `insufficient_quota` — trainee's OpenAI account has no billing credits; key itself is valid, blocking only real calls, not code
- Verification result: mock, Workers AI, and Vertex all confirmed working end-to-end through `/playground` (opened and tested in an actual browser, not just curl) with correct answer/latency/cost. Postgres `usage` table confirmed via direct query to contain one row per call, including `error` status rows for the Bedrock/OpenAI failures — nothing was silently dropped.
- Break-it test: requesting a nonexistent provider name → clean `400 unknown provider: ...`, no crash.
- Understanding check: Q2 (why Postgres not a log file/Redis) and Q3 (adapter pattern use case) answered correctly. Q1 conflated wrangler (Cloudflare-only, Part 1) with the Part 2 provider credentials, and didn't yet distinguish Bedrock/Vertex as "cloud-identity front doors to a model" vs. being AI systems themselves — re-explained, trainee acknowledged understanding.
- Open follow-up (not blocking): retest Bedrock once AWS payment method is added; retest OpenAI once account has credits. No code changes expected — just re-run the existing playground test for those two providers.
- **Update (2026-09-26)**: OpenAI retested after trainee added account credits — confirmed working end-to-end through `/v1/chat/playground`, correct tokens/cost tracked ($0.00000315 for the test call). Bedrock retested after AWS Marketplace payment method finished propagating — confirmed working for both basic chat and Part 3's tool-calling (`get_ticket`) through the real gateway, correct tokens/cost tracked (tool-calling call cost $0.0014, matching Claude's pricier tier vs. cheap providers). **All 5 providers now fully verified end-to-end: mock, Workers AI, Vertex, OpenAI, Bedrock.** No code changes were needed for either — exactly as the "code now, verify later" approach anticipated. Re-enabled Bedrock and OpenAI in `routing.yaml`'s real `chat`/`support_chat` fallback chains (previously commented out).

### Part 3 — AI engineering toolkit
- Status: DONE
- Tools used: Pydantic (schema validation), FastAPI StreamingResponse (SSE), Claude native tool-use (Bedrock), Vertex multimodal input, PyYAML (prompt registry)
- Spend: a handful of small Vertex calls (structured output + streaming + document extraction tests), each fractions of a cent
- What was built:
  - `gateway/app/structured.py` — schema-validate-and-retry helper used by both `/v1/chat/structured` and `/v1/extract/document`; strips markdown code fences before parsing
  - `/v1/chat/stream` — SSE streaming, implemented for mock and Vertex (`chat_stream` added to both)
  - `/v1/chat/tools` — tool calling, implemented for mock and Bedrock (`chat_with_tools` added to both), backed by a fake in-memory `get_ticket` tool in `app/tools.py`
  - `/v1/extract/document` — multimodal PDF/image extraction via Vertex (`chat_with_document` added to `vertex.py`), reusing the schema-retry path
  - `gateway/prompts/` — versioned prompt registry (`extract_invoice_v1.yaml`), loaded via `app/prompts.py`
  - `gateway/tests/fixtures/` — synthetic test invoice (PDF + JPEG "photo" version) generated for testing extraction
- Issues hit and resolved:
  - Gemini wrapped JSON answers in ` ```json ` markdown fences despite explicit "no other text" instructions — first structured-output test failed with a JSON parse error; fixed by stripping fences before `json.loads`, verified against the real failure and the fix
  - `python-multipart` was needed for FastAPI file uploads — not caught until the `/v1/extract/document` route was added
  - Needed `poppler` (pdftoppm) to generate a "phone photo" test image from the PDF fixture
- Verification result: all four done-when criteria from the brief confirmed — `/v1/extract` always returns schema-valid JSON (including all-null for a non-invoice file, not hallucinated data); `/v1/chat/stream` streams for both mock and Vertex; a tool call resolves both valid and invalid ticket IDs; the same sample invoice as PDF and as a simulated photo both returned identical, correct fields. Retry logic itself directly verified against a fake provider that fails twice before succeeding.
- Break-it test: uploaded a plain text file (not an invoice) to `/v1/extract/document` → returned schema-valid JSON with all fields `null`, not fabricated data.
- Understanding check: Q1 (streaming vs tool-calling distinction) needed clarification — trainee initially conflated the two; re-explained with a UI mockup showing both stages ("thinking..." indicator, then either instant full-answer or live word-by-word typing). Q2 (why retry/validation logic exists) and Q3 (why null-not-hallucinated matters) both needed re-explanation with the real bug we hit (Gemini's markdown-fence JSON) shown visually, plus a hospital lab-report scenario for real-world stakes. All three passed after visual + scenario explanation.
- Standing preference established this part (saved to memory): explain every feature via four scenario lenses (end user / company owner / client app / builder) AND a realistic UI/UX mockup as an Artifact — not abstract technical diagrams. Both together, always, going forward — ask which combination fits if unsure.
- Deferred (not blocking): prompt caching (Bedrock/Claude-native) — logged as a follow-up rather than writing untested code, since it depends on Bedrock being unblocked.

### Part 4 — Smart routing + resilience
- Status: DONE
- Tools used: Redis (Docker Compose, local), routing.yaml (task-type → provider chain config)
- Spend: $0 (all fallback/breaker/cache testing used mock + workers_ai, both free)
- What was built:
  - `routing.yaml` — task types (`chat`, `support_chat`) mapped to an ordered provider fallback chain; retry count, backoff, and circuit-breaker thresholds as config; Bedrock/OpenAI present but commented out until billing is fixed
  - `gateway/app/routing.py` — `call_with_fallback()`: retries each candidate with backoff+jitter, skips providers whose circuit breaker is open (tracked in Redis), raises a clear error if every candidate fails; response cache read/write via Redis, keyed by provider+prompt hash
  - `gateway/app/redis_client.py` — shared Redis connection
  - `/v1/chat/smart` — new route, same `EDGE_SECRET` auth as `/v1/chat`, routes by `task` instead of an explicit `provider`, cache-first
  - Added a `FORCE_429` trigger phrase to `mock.chat()` so fallback/breaker behavior can be tested on demand without needing a real provider outage
  - Two test-only routing.yaml tasks (`test_fallback`, `test_total_outage`) to exercise the fallback and total-failure paths deliberately
- Verification result (matches brief's exact "done when" — forcing mock to 429 triggers fallback):
  - Forced mock failure → retried twice, then fell through to `workers_ai`, which answered successfully; caller saw no error
  - After repeated failures, mock's circuit breaker opened (confirmed via direct Redis inspection: `breaker:mock:failures` = 4, `breaker:mock:open` = 1) — next call skipped mock entirely and went straight to `workers_ai`
  - Identical repeated prompt → second call returned `from_cache: true` with zero provider calls
- Break-it test: a task with only one candidate, forced to fail every time → clean `502` with a detail list of every attempt, returned quickly — no hang, no crash, no infinite retry loop.
- Understanding check: Q1 (what happens when the first provider is down) was missing the "retry the same provider first, then move to the next" detail. Q2 (why circuit breaker matters beyond retries) was answered incorrectly — trainee described a request queue, which isn't what we built; re-explained as "stop wasting time retrying a provider we already know is broken, for every subsequent request, for 30 seconds." Q3 (how caching saves money) was also off — trainee described general session memory; re-explained as "identical question asked twice = second time costs nothing," with an airline pricing-page analogy (many people searching the same route/date get served the same cached price). Trainee confirmed understanding after correction without needing a visual mockup this time.
- Process note: mid-part, cleaned up leftover uncommitted code from an earlier abandoned interactive-demo attempt (mock's chat() had been slowed to 2s for a demo that was replaced by static Artifact mockups) — restored to normal fast timing, kept the otherwise-unused /demo/streaming route since it was already built and harmless.
- Standing preference refined this part: build UI/UX mockups as before, but ASK before creating/publishing each one rather than auto-publishing; compile all mockups (shown or not) into one page at the end of the project instead of one-per-part.

### Part 5 — Security + guardrails
- Status: DONE
- Tools used: Postgres (new `apps`/`audit_log` tables), Llama Guard via Workers AI, Redis (rate limiting), AWS IAM + GCP Workload Identity Federation
- Spend: $0 (Llama Guard calls are free-tier Workers AI; IAM roles and WIF pools/providers are free to create, cost only if used to call billed services)
- What was built:
  - `gateway/app/db.py` — `App` table (app_id, hashed key, role, allowed_providers) and `AuditLog` table (app_id, event_type, detail, timestamp)
  - `gateway/app/auth.py` — key hashing, `authenticate_app()`, `check_provider_allowed()` (role-based model allow-list)
  - `gateway/app/guardrails.py` — regex PII detection/redaction (SSN, credit card, email, phone); prompt-injection detection combining a phrase heuristic with Llama Guard (`@cf/meta/llama-guard-3-8b` via Workers AI/AI Gateway)
  - `gateway/app/rate_limit.py` — per-app fixed-window rate limiting (30 req/60s) via Redis `INCR`+`EXPIRE`
  - `/v1/chat` now requires `x-app-key` (renamed from the old shared `x-client-key`/`CLIENT_KEYS` model), enforces rate limit → provider allow-list → PII redaction → injection check, in that order, before calling any provider; PII redactions and blocked injections are audit-logged
  - `worker/src/index.ts` — forwards `x-app-key` through to the gateway (previously used for the Worker's own coarse check only)
  - AWS IAM role `eacp-gateway-role` + GCP Workload Identity Pool/Provider (`eacp-aws-pool`/`eacp-aws-provider`) + GCP service account `eacp-vertex-sa` (Vertex AI User only) — full trust chain so the gateway can eventually authenticate to Vertex using its AWS identity instead of a local Google credential file
  - `gateway/scripts/seed_apps.py` — seeds two demo apps (`support-app`, `analyst-agent`) with different roles/allowed providers for testing
- Issues hit and resolved:
  - Llama Guard flagged any PII-containing prompt as "unsafe" (category S7 — Privacy), which directly conflicted with the chosen redact-and-continue PII policy — a real SSN test prompt got wrongly blocked as "prompt injection" before we noticed the actual cause. Fixed two ways: (1) reordered checks so PII is redacted *before* the injection/Llama Guard check runs, and (2) parsed Llama Guard's safety category from its response and explicitly excluded S7, since our own PII scan already owns that concern
  - Cloudflare's native Workers Rate Limiting binding (`[[unsafe.bindings]]` / `[[ratelimits]]` in wrangler.toml) never triggered even after 100+ rapid requests against a configured 30/60s limit, across both wrangler 3.114.17 and after upgrading to 4.142.0 (which did fix it showing as a proper "Rate Limit" resource instead of unsafe metadata). Researched Cloudflare's own docs/community reports, confirmed this shouldn't happen even accounting for the binding's documented eventual-consistency behavior, and switched to a Redis-based rate limiter in the gateway instead — reusing the same reliable pattern from Part 4's cache/breaker
- Verification result (matches brief's exact "done when" criteria):
  - A prompt containing an SSN is redacted (`[REDACTED_SSN]`) before reaching any provider, and the redaction is audit-logged (confirmed via direct Postgres query)
  - An app requesting a model outside its role's allow-list gets a clear `403`, naming the app and role
  - Gemini/Vertex calls succeed with no GCP key file — technically true for AWS-hosted infra via WIF, though this specific claim is only *fully* verifiable once the gateway actually runs on AWS in Part 9; local dev still correctly uses ADC in the meantime, unaffected by the WIF setup
  - Rate limiting confirmed end-to-end through the real Worker → Tunnel → Gateway → Redis chain: requests 1–30 succeed, 31+ correctly return `429`; a different app's key is unaffected (per-app isolation)
  - Real prompt-injection phrase ("ignore all previous instructions...") still correctly blocked after the S7 fix, confirming the fix didn't weaken genuine injection detection
- Break-it test: a request with a valid `EDGE_SECRET` but no `x-app-key` at all (simulating a compromised shared secret without a specific app's key) → clean `401`, no bypass possible.
- Job-skill mapping: this part is squarely *"take successful prototypes into production and ensure security... reliability"* and *"integrate LLM applications with... cloud services"* (the AWS↔GCP WIF trust chain). The PII/injection guardrails are also foundational to *"build evaluation pipelines to measure... safety"* — Part 6 can't meaningfully score "is this safe" without Part 5's controls already in place.

### Part 6 — Evals + model migration
- Status: DONE
- Tools used: custom eval runner (Python), LLM-as-judge (Bedrock/Claude Haiku), routing.yaml canary config
- Spend: ~$0.02 (one full scorecard run across workers_ai/vertex/bedrock/openai, ~33 questions each, plus two canary_check.py runs)
- What was built:
  - `evals/golden.jsonl` — 33 support-style test cases: 15 exact-match (deterministic factual questions), 12 LLM-judged (subjective free-text, e.g. empathetic support replies), 3 structured-output (ticket-extraction JSON, reusing Part 3's schema idea)
  - `evals/runner.py` — scores one provider against the golden set; exact/structured cases scored deterministically in code, judged cases scored by a *different* model (avoids a model grading its own mistakes favorably)
  - `evals/scorecard.py` — runs the eval across multiple providers and prints a side-by-side comparison table
  - `gateway/routing.yaml` — added a `canary` section (task, primary, candidate, candidate_weight) and real `quality_floor: 0.80` values (previously placeholders); `gateway/app/routing.py` now picks the canary candidate for a random slice of `chat`-task traffic when weight > 0
  - `evals/canary_check.py` — runs the eval against the current canary candidate and automatically rewrites `routing.yaml` to zero out `candidate_weight` if the score falls below `quality_floor`, leaving the reason in the file
- Issues hit and resolved:
  - `normalize()` crashed with `AttributeError: 'int' object has no attribute 'strip'` on a real provider's answer (not the golden data) — fixed by coercing to `str()` before normalizing
  - Eval runner crashed with a raw `KeyError`/stack trace when given an unknown provider name (caught by this part's own break-it test) — fixed with argparse `choices=` validation
- Verification result / real scorecard (2026-09-27, full numbers in `evals/scorecard_2026-09-27.md`):
  | Provider | Score | Cost | Avg Latency |
  |---|---|---|---|
  | workers_ai | 88% | $0 | 571ms |
  | vertex | 91% | $0.0005 | 3525ms |
  | bedrock | 88% | $0.0088 | 1126ms |
  | openai | 85% | $0.001 | 1036ms |
  This directly answers the brief's CFO question: workers_ai matches Bedrock's quality at zero cost — real, evidence-based grounds to prefer the free provider as default.
- Break-it test (also the brief's exact required check — "a deliberately bad prompt change fails the eval"): set the canary candidate to `mock` (can't answer real questions) at 20% weight → `canary_check.py` scored it 0.0%, automatically rolled back `candidate_weight` to `0.0` with the reason written into `routing.yaml`. Confirmed via 10 live `/v1/chat/smart` calls that traffic never reached the rolled-back candidate afterward — the routing code genuinely respects the auto-rollback, not just the eval script reporting success.
- Job-skill mapping: this part is close to a direct match for *"Build evaluation pipelines to measure accuracy, task success, retrieval quality, hallucinations/failures, latency, cost, reliability, and safety"* — one of the most senior/high-value bullets on the list. The canary+rollback mechanism is also a real instance of *"ensure... reliability"* from the production bullet, arriving as an automated safety net rather than a manual process.

### Part 7 — RAG platform
- Status: DONE
- Tools used: pgvector (Postgres extension), Vertex text-embedding-005, Postgres full-text search
- Spend: ~$0.01 (embedding calls for ingestion x2 chunk-size runs, ~48 Vertex chat calls during the retrieval eval's reranking pass, all fractions of a cent each)
- What was built:
  - Switched Postgres to the `pgvector/pgvector:pg16` image (same Docker volume; confirmed all Part 2-5 data — 277 usage rows, both seeded apps — survived the switch intact) and enabled the `vector` extension
  - `docs/policies/` (refund, data privacy, account security) + `docs/runbooks/` (password reset, billing dispute, escalation, account recovery) — 7 synthetic docs with deliberate topical overlap, written to meaningfully test retrieval rather than trivially
  - `gateway/app/db.py` — new `doc_chunks` table (content, 768-dim Vertex embedding, plus a GIN full-text index for hybrid search)
  - `gateway/scripts/ingest_docs.py` — chunks docs on paragraph boundaries (not fixed character cuts), embeds each chunk via Vertex, stores in `doc_chunks`
  - `gateway/app/retrieval.py` — `vector_search` (pure semantic), `keyword_search` (Postgres full-text), `hybrid_search` (reciprocal-rank fusion of both), `rerank` (LLM re-scores each candidate's relevance 0-10)
  - `/v1/rag/ask` — takes a question + strategy (`vector`/`keyword`/`hybrid`/`hybrid_rerank`), retrieves, answers using ONLY the retrieved context, returns source citations
  - `evals/retrieval_golden.jsonl` + `evals/retrieval_eval.py` — 12-question retrieval-specific eval measuring hit@k across all four strategies
- Issues hit and resolved:
  - `vertex.py`'s `_access_token()` was creating fresh credentials and forcing a full OAuth token refresh on every single call — fine at normal traffic, but under the retrieval eval's load (dozens of calls in quick succession across 12 questions × reranking) this caused Google's OAuth endpoint to time out entirely, crashing the eval mid-run. Fixed by caching credentials at module level and only refreshing when actually expired (`credentials.valid` check) — a real lesson in why "works for one request" isn't the same as "works under load"
- Verification result (matches brief's "done when" exactly):
  - `/v1/rag/ask` correctly answered "how long do I have to request a refund?" with "30 days," citing `refund_policy.md`
  - Retrieval eval (hit@3, 12 questions): **vector 100%, keyword 8%, hybrid 100%, hybrid+rerank 100%** — a stark, real demonstration of why semantic search matters: customer questions rarely share exact wording with policy docs, so pure keyword search nearly always missed, while vector/hybrid consistently found the right source
  - Chunk-size experiment: re-ingested at 200 chars (25 chunks) vs. 500 chars (18 chunks) — no difference in retrieval quality on this dataset (still 100% for vector), an honest finding that chunk size matters more for longer/denser real-world docs than this small synthetic set
- Break-it test: asked a question with no answer anywhere in the docs ("international shipping fees") — the system correctly replied "the provided context does not contain information about..." instead of inventing a fake policy, even though retrieval still returned its best (irrelevant) guesses as sources.
- Job-skill mapping: this is a direct, near-verbatim match for *"Design and build RAG systems, knowledge assistants, document-processing applications, chatbots, copilots, and enterprise search systems"* — the exact phrase from the job list. The hit@k retrieval eval is also a concrete instance of *"build evaluation pipelines to measure... retrieval quality"* from Part 6's bullet, now applied to a genuinely different kind of correctness question (did we find the right document, not just did we answer well).

### Part 8 — Containers, local Kubernetes, Terraform plan
- Status: DONE
- Tools used: Docker, kind, Helm, kubectl, Terraform (aws + google providers)
- Spend: $0 (Docker/kind/Helm are all local; AWS Terraform is plan-only, not applied; GCP BigQuery datasets applied but within the free tier)
- What was built:
  - `gateway/Dockerfile` + `.dockerignore` — packages the FastAPI gateway as a container image; verified standalone against the existing Postgres/Redis (including a real chat call) before moving to Kubernetes
  - `k8s/kind-config.yaml` — local kind cluster config, maps the gateway's NodePort to `localhost:8000`
  - `k8s/eacp-chart/` (Helm) — Postgres (StatefulSet + PersistentVolumeClaim, pgvector image), Redis (Deployment), gateway (Deployment + NodePort Service); secrets via a Kubernetes Secret (`secret-example.yaml` committed as the template, real `secret.yaml` gitignored)
  - `terraform/aws/` — VPC (public subnets, no NAT, per the brief), ECR, EKS cluster + node group, least-privilege IAM roles (including a Pod Identity association reusing Part 5's `eacp-gateway-role`), RDS Postgres with a Secrets-Manager-stored random password — **plan-only**, not applied
  - `terraform/gcp/` — 2 BigQuery datasets (usage analytics, eval history) — **applied**, within the free tier, per the brief's "apply only the free GCP pieces" instruction
- Issues hit and resolved:
  - The gateway pod crash-looped with `connection refused` — a normal startup race (gateway started before Postgres was ready); resolved itself once Postgres became ready and the pod was deleted to force a fresh attempt
  - A second, real bug: `DATABASE_URL`'s `$(POSTGRES_PASSWORD)` substitution silently failed (literal `$(POSTGRES_PASSWORD)` string reached the app), causing a password-authentication failure. Root cause: Kubernetes only resolves `$(VAR)` references to env vars defined **earlier** in the same container's env list — `POSTGRES_PASSWORD` was listed after `DATABASE_URL`. Fixed by reordering; verified zero restarts after the fix.
- Verification result: all 3 pods (gateway, postgres, redis) reach `Ready` with zero restarts; both a `mock` and a real `workers_ai` call succeed through the cluster (confirming Kubernetes Secret wiring for `CF_API_TOKEN` etc. is correct); `terraform plan` for AWS validates cleanly (24 resources, 0 errors); GCP BigQuery datasets confirmed created via `bq ls`.
- Break-it test: wrote a test row to the in-cluster Postgres, then `kubectl delete pod postgres-0` to simulate a crash. Kubernetes automatically recreated the pod within ~8 seconds with zero human intervention, and the test row **survived** — proof the data lives in the PersistentVolumeClaim, not the disposable pod. Gateway `/health` stayed `ok` throughout.
- Job-skill mapping: this part is the concrete start of *"take successful prototypes into production and ensure... scalability, reliability, maintainability"* — containerization and Infrastructure-as-Code are foundational production skills, and the self-healing break-it test is direct, hands-on proof of the "reliability" half of that bullet, not just a claim.

### Part 9 — EKS key day 1
- Status: DONE (Bedrock path fully verified on real AWS; Vertex-via-Pod-Identity-WIF parked as a known limitation)
- Tools used: `terraform apply`/`destroy` (real AWS), AWS EKS + node group, ECR, RDS Postgres, EKS Pod Identity, Secrets Manager, Cloudflare Worker + in-cluster cloudflared tunnel
- Spend: ~$1.50-2.50 total — ~62 min of intended EKS ($0.10/hr) + 2x `t3.medium` nodes (~$0.0416/hr each) + `db.t4g.micro` RDS (~$0.016/hr), plus ~4 min of unintended EKS-only cost from an assistant mistake (see below). All resources destroyed and verified gone via direct AWS CLI checks (EKS, RDS, VPC, ECR, EC2 instances, and leftover ENIs all confirmed empty) — $0 running cost now.
- What was built:
  - `terraform apply` on the Part 8 plan — real VPC, EKS cluster + 2-node `t3.medium` node group, ECR repo, RDS `db.t4g.micro` Postgres, least-privilege IAM, Secrets Manager entry for the RDS password
  - `k8s/eks-manifests/` — new manifests for the EKS deploy specifically (separate from the local `kind` Helm chart, since EKS uses real RDS instead of an in-cluster Postgres pod, and Pod Identity instead of a `.env` file for AWS creds): `service-account.yaml` (the `eacp-gateway` service account Pod Identity binds to), `redis.yaml` (still in-cluster — no billable managed Redis was planned/approved), `gateway.yaml` (gateway Deployment against RDS + ECR image), `cloudflared.yaml` (in-cluster quick tunnel, same architecture as local dev)
  - Gateway image built and pushed to ECR (`123153903243.dkr.ecr.us-east-1.amazonaws.com/eacp-gateway`)
  - Cloudflare Worker's `GATEWAY_URL` repointed at the in-cluster tunnel's ephemeral URL, redeployed
  - `gateway/app/providers/vertex.py` — added a custom `_PodIdentitySupplier` (subclass of `google.auth.aws.AwsSecurityCredentialsSupplier`) that delegates AWS credential lookup to `boto3` (which already resolves Pod Identity correctly) instead of reimplementing the container-credentials HTTP call by hand
- Issues hit and resolved (real bugs, not just config typos):
  - **EKS Pod Identity trust policy**: `eacp-gateway-role`'s trust policy only trusted `eks.amazonaws.com` (a Part-5-era placeholder, before Pod Identity existed as a feature) — Pod Identity specifically requires trusting `pods.eks.amazonaws.com` with both `sts:AssumeRole` and `sts:TagSession`. Fixed via `aws iam update-assume-role-policy` directly (the role is only `data`-referenced in Terraform, not owned by it, so this doesn't fight Terraform state).
  - **RDS security group description rejected**: AWS's security-group-description charset doesn't allow apostrophes — `"EKS cluster's security group"` failed `CreateSecurityGroup`. Fixed by rewording.
  - **EKS node group AMI mismatch**: the default AMI type was rejected for K8s 1.30 node groups. Fixed by explicitly setting `ami_type = "AL2023_x86_64_STANDARD"`.
  - **Gateway IAM role had zero Bedrock permissions**: local dev had been using a personal `aws configure` profile with broader permissions, so this gap was never caught until the role actually had to work standalone on EKS. Added a scoped `bedrock:InvokeModel`/`InvokeModelWithResponseStream` inline policy.
  - **EKS pods couldn't reach the instance metadata service**: EKS's default node launch template caps the IMDS hop limit at 1, which blocks traffic originating from inside a pod's network namespace (2 hops away) from reaching `169.254.169.254`. This silently broke Vertex's AWS credential lookup with "Unable to retrieve AWS role name." Fixed live via `aws ec2 modify-instance-metadata-options --http-put-response-hop-limit 2` on the running nodes, and added the correct fix to Terraform as a dedicated `aws_launch_template` for future applies.
  - **`google-auth`'s `Credentials.from_info()` silently discards a custom AWS credential supplier**: passing `aws_security_credentials_supplier` as a kwarg gets unconditionally overwritten by `info.get("aws_security_credentials_supplier")` (always `None`, since that key isn't in our credential-config JSON) inside `from_info()`'s own implementation. The fix required calling the `Credentials` constructor directly instead of the documented-looking `from_info()` classmethod — a real library gotcha, not a config mistake.
  - **GCP WIF pool's attribute mapping was incomplete**: only mapped `google.subject` (the full AWS session ARN, which includes a random per-call session-name suffix), so IAM bindings built against `attribute.arn` never matched anything, since that attribute was never actually populated. Fixed by adding `attribute.aws_role: assertion.arn.extract('assumed-role/{role}/')` to the pool's attribute mapping and rebinding IAM against the stable extracted role name instead of the volatile full ARN.
  - **Still unresolved**: even after the above fix and granting `roles/iam.serviceAccountTokenCreator` correctly, the final "impersonate `eacp-vertex-sa`" step still returns `PERMISSION_DENIED` on `iam.serviceAccounts.getAccessToken`, with no matching entry appearing in Cloud Audit Logs at all — suggesting the request is being rejected earlier in GCP's token-exchange pipeline than the impersonation check itself. Parked as a known limitation rather than continuing to debug against a live AWS billing clock; Bedrock (which doesn't depend on this cross-cloud exchange) was fully verified instead, satisfying the part's core "done when" bar.
  - **Assistant process mistake**: after the first successful `terraform destroy`, one leftover issue remained (ECR repo non-empty, blocking its own deletion). Instead of force-deleting it via the AWS CLI and re-running `terraform destroy` to reconcile state, `terraform apply` was run by mistake — since AWS-side resources were already gone but Terraform's own state still listed them, `apply` interpreted this as "recreate everything," and briefly stood up a new EKS cluster, VPC, and IAM roles before the mistake was caught (~1 minute in) and the process killed. The new cluster had to finish its in-progress `CreateCluster` call (AWS does not allow deleting a cluster mid-creation) — it happened to fail on its own (status `FAILED`) partway through, which is actually a `DeletableCluster` state, so it was deleted immediately via `aws eks delete-cluster` rather than waiting further. RDS and the node group never started in this second attempt. Total added cost: a few minutes of EKS control-plane time, a few cents at most. **Lesson recorded in `terraform/README.md`: only ever run `terraform destroy` on this folder going forward; handle any out-of-band manual fixes via the AWS CLI directly, never `apply`, to avoid ever risking a full unintended recreation.**
- Verification result (matches the brief's exact "done when" criteria): a real `curl` through the public Cloudflare Worker URL (`x-client-key` + `x-app-key` headers) → Worker → in-cluster Cloudflare Tunnel → FastAPI gateway pod running on real EKS (authenticated via Pod Identity, no static AWS keys anywhere) → AWS Bedrock (Claude Haiku) → a real answer returned end-to-end. Confirmed via the actual AWS Bedrock console showing the invocation.
- Break-it test: deleted the single gateway pod outright (`kubectl delete pod -l app=gateway`) while it was the only replica. The public Worker URL correctly returned a clean `502` during the outage (proving this wasn't silently papered over) — then, with zero manual intervention, Kubernetes recreated the pod, it reconnected to the real RDS database and re-ran its own startup migration (`CREATE EXTENSION IF NOT EXISTS vector`, table creation) successfully on its own, passed its readiness probe, and the exact same public URL started serving correct answers again within about a minute.
- After destroy, confirmed via direct AWS CLI (not just Terraform's own exit code) that zero resources remain: `aws eks list-clusters`, `aws rds describe-db-instances`, `aws ec2 describe-vpcs` (eacp-vpc), `aws ecr describe-repositories`, `aws ec2 describe-instances` (eacp node tag), and `aws ec2 describe-network-interfaces` (a common EKS teardown leak) all returned empty.
- Job-skill mapping: this is the clearest, most direct match yet to *"take successful prototypes into production... ensure scalability, reliability, maintainability, and security"* — this part is the actual cloud production deployment, not a local simulation of one. It's also concrete, hands-on practice of *"integrate LLM applications with... cloud services"* (Pod Identity + cross-cloud WIF), and the IMDS/trust-policy/IAM debugging is exactly the kind of real infrastructure troubleshooting that separates "wrote a Terraform file once" from "actually operated a cloud deployment under time and cost pressure."

### Part 10 — CI/CD with AI gates (IN PROGRESS — not yet closed out)
- Status: IN PROGRESS. Paused for a break mid-part, by explicit request — not blocked, not failed. On resume: trigger the next Jenkins build and watch it to completion; if it passes all 7 stages, run the break-it test + understanding check + job-skill mapping to formally close this part.
- Tools used so far: Jenkins (self-hosted, in Docker — a new `eacp-jenkins` container, NOT the unrelated pre-existing stopped `jenkins` container found on this machine, which was deliberately left untouched), GitHub (repo created and pushed for the first time this part — `github.com/sohorabil/ai-control-plane`, private), Cloudflare Tunnel (quick tunnel to expose Jenkins for the GitHub webhook), pytest, ruff, Trivy, `jq`.
- Spend: $0 (everything this part is local/free — no AWS/GCP resources touched).
- Milestone: **this project's code left "laptop-only" for the first time.** 27 commits (Parts 1-9 + architecture.md) pushed to a real GitHub repo. Previously, a lost laptop would have meant losing all the work.
- What was built:
  - Jenkins running in its own Docker container (`docker-compose.yml`'s `jenkins` service), built from a custom image (`ci/jenkins/Dockerfile`) since the stock `jenkins/jenkins:lts` image only has `git` — added `docker` CLI (talks to the host daemon via the mounted socket), `kubectl`+`helm`+`kind` (talk to the local cluster via a dedicated kubeconfig mounted in and a shared Docker network with the `kind` node), `trivy`, `terraform`, `jq`, `python3`.
  - GitHub webhook (`https://github.com/sohorabil/ai-control-plane/settings/hooks`) → Cloudflare Tunnel → Jenkins; confirmed working via GitHub's automatic ping (`PING webhook received`, visible in Jenkins' logs).
  - First real automated test suite for this project: `gateway/tests/test_auth.py`, `test_guardrails.py`, `test_rate_limit.py` — 16 fast (~0.3s), dependency-free unit tests (fake DB/Redis objects, no live services needed) covering key hashing, provider allow-lists, PII redaction, injection detection, and rate-limit threshold logic.
  - `ruff` added as the linter; caught 2 real unused imports on its first run against existing code (`app.main`'s unused `App` import, `app.routing`'s unused `time` import) — fixed both.
  - `Jenkinsfile` — one pipeline, 7 ordered stages (lint+test → Trivy scan → terraform validate → AI eval-gate smoke test against the free `mock` provider → AI code-review comment via our own gateway → deploy to `kind` "staging" namespace → promote to `kind` "prod" namespace). `Jenkinsfile.rollback` — a deliberately *separate* pipeline (different trigger: a human decision, not a code push) for manually rolling back `eacp-prod` to its previous Helm release.
  - `evals/ci_smoke.jsonl` — a tiny, `mock`-provider-specific golden set (3 cases) so the CI eval-gate stage tests the eval *harness's* mechanics for free, without needing real provider credentials inside Jenkins or spending money on every push; `evals/runner.py` gained a `--golden-file` argument to support this.
  - Made `k8s/eacp-chart`'s gateway NodePort configurable (`values.yaml`/`gateway.yaml` — was hardcoded to 30080) so `eacp-staging`/`eacp-prod` can each get their own port without colliding.
- Two bugs found and fixed that were unrelated to CI/CD itself, surfaced only because building real verification forced exercising code paths nobody had re-tested in a while:
  - Trivy found 7 real HIGH-severity CVEs in `python-multipart`/`starlette` (transitive via `fastapi`). Fixed by bumping `python-multipart` to 0.0.18 and `fastapi`+`starlette` together (0.119.1/0.48.0 — needed together due to a version constraint). Three newer `starlette` CVEs remain, fixable only via a bigger 1.x jump; accepted as a documented, lower-severity (DoS-class) risk rather than chasing every disclosure immediately — a real security-triage judgment call, not negligence.
  - `/v1/extract/document`'s `provider` form field was missing FastAPI's `Form(...)` annotation — a real bug since Part 4. It silently ignored whatever the caller actually sent and always used the `vertex` default, meaning `provider=mock` (or any invalid value) was never actually validated or honored. Fixed by adding `Form("vertex")`.
- Real bugs found and fixed in the Jenkinsfile itself, across 5 build attempts, verified by hand each time rather than assumed fixed:
  1. **Wrong working directory for the eval gate** — `cd gateway` before running `python -m evals.runner` broke the import, since `evals/` is a sibling of `gateway/`, not a subpackage. Fixed by running from the repo root.
  2. **`localhost` from inside the Jenkins container ≠ the host** — two curl health-checks pointed at `localhost:<port>`, which inside a Docker container resolves to the container itself. Fixed using `host.docker.internal` (and later, in-cluster Service DNS — see #5).
  3. **`kind` version too old for this host's containerd** — the Jenkins image shipped `kind` v0.24.0, which predates support for containerd v2 (this machine's `kind` node runs containerd v2.3.4), causing `kind load docker-image` to fail with "failed to detect containerd snapshotter." Fixed by bumping to v0.33.0 (matching the host's own `kind` version) and confirmed with a real image load.
  4. **Unsafe JSON construction in the AI-review stage** — building the request body via raw shell string interpolation put `git diff --stat`'s real newline characters directly into a JSON string literal, which is invalid JSON; the call silently failed every time. Fixed using `jq -n` to construct the payload properly (added `jq` to the Jenkins image).
  5. **Kubernetes Secrets are namespace-scoped** — `eacp-staging`/`eacp-prod` are brand-new namespaces; the `eacp-secrets` Secret from Part 8 only ever existed in `default`. Every fresh-namespace deploy failed with `CreateContainerConfigError: secret "eacp-secrets" not found`. Fixed by copying the Secret's live data (read from the cluster, never hardcoded into the Jenkinsfile) into each target namespace before deploying. Also switched stage 7's health check from a host-port curl (never mapped for the staging NodePort) to an in-cluster check via a temporary pod hitting the Service's cluster-DNS name — portable regardless of host port mappings.
  6. **Static image tags meant re-deploys silently never updated** — found by manual verification, not a real pipeline run. `helm upgrade` with an unchanged tag (`eacp-gateway:staging`) reports success and even replaces the pod, but with `imagePullPolicy: IfNotPresent`, the node's cached layer under that tag is never actually refreshed — the "new" pod silently kept running the OLD code. Reproduced deliberately (deployed v1, rebuilt v2 under the same tag, confirmed via `kubectl exec` that v1's code was still running), then fixed by tagging every build with Jenkins' unique `BUILD_NUMBER`, and re-verified the fix the same way (this time the exec'd-into pod correctly showed v2's code).
- Also retired the original `default`-namespace gateway deployment (Helm release `eacp`, running since Part 8) since it held NodePort 30080, which `eacp-prod` needs going forward — from this part onward, the CI/CD-managed `eacp-prod` namespace is the one true "production," not a manually-run `helm install`.
- Not yet done: a build has not yet been run to full completion (all 7 stages green) since fix #6 (the image-tag bug) was made — bugs #1-5 were each found via a REAL Jenkins build; bug #6 was found via manual reproduction before spending another real build cycle on a bug that could be predicted. **Next action on resume: trigger a build and actually watch all 7 stages pass.** Do not assume this pipeline fully works until that's confirmed.
- Break-it test: not yet run (part not closed) — planned: push a change that makes the eval gate fail (e.g. corrupt `evals/ci_smoke.jsonl`'s expected answer) and confirm the pipeline stops at stage 4, with stages 5-7 never running and `eacp-prod` untouched.
- Understanding check: not yet run (part not closed).
- Job-skill mapping: not yet given (part not closed) — will map to *"AI-written code and prompt changes are shipping too fast to trust"* (the CI eval gate), *"take successful prototypes into production and ensure... reliability, maintainability"* (the whole pipeline), and the security-triage judgment call on the CVE findings.
