# PROGRESS

📍 Now: Part 5 of 14 — Security + guardrails — COMPLETE. Waiting for "next" to start Part 6.
✅ Done: Part 1 (edge front door); Part 2 (provider adapters, usage logging); Part 3 (structured output, streaming, tools, extraction); Part 4 (routing, fallback, circuit breaker, cache); Part 5 (per-app keys/roles, PII redaction, injection detection, audit log, rate limiting, Vertex WIF trust chain)
⏭ Next: Part 6 — Evals + model migration (golden dataset, eval runner, LLM-as-judge, scorecard, canary routing, automatic rollback)
💰 Spend so far: <$0.01 (small Vertex/OpenAI/Bedrock verification calls across all parts) · ☁️ Running now: local FastAPI gateway (port 8000), cloudflared quick tunnel, local Postgres + Redis via Docker Compose
🎓 Understanding checks: passed 4 / done 4 so far (skipped: none) — each part needed at least one re-ask/re-explanation, all resolved
⚠️ Open issues: quick tunnel URL is ephemeral (changes on restart); prompt caching (Bedrock-native) still deferred from Part 3, now unblocked, small follow-up whenever; Vertex WIF fully wired but only fully testable once running on real AWS (Part 9)

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
