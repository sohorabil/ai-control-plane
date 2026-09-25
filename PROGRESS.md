# PROGRESS

📍 Now: Part 2 of 14 — One API, four models — COMPLETE. Waiting for "next" to start Part 3.
✅ Done: Part 1 (edge front door + first AI answer); Part 2 (provider adapters for mock/Workers AI/Bedrock/Vertex/OpenAI, Postgres usage logging, playground)
⏭ Next: Part 3 — AI engineering toolkit (structured output, streaming/SSE, tool calling, prompt caching, prompt registry, multimodal document extraction)
💰 Spend so far: <$0.01 (estimated — one Vertex test call; Bedrock/OpenAI blocked before any billable call succeeded) · ☁️ Running now: local FastAPI gateway (port 8000), cloudflared quick tunnel, local Postgres via Docker Compose
🎓 Understanding checks: passed 2 / done 2 (skipped: none) — Part 1 Q3 needed one re-ask (tunnel direction); Part 2 Q1 needed one re-explanation (what Bedrock/Vertex actually are vs. wrangler)
⚠️ Open issues: quick tunnel URL is ephemeral (changes on restart) — wrangler.toml GATEWAY_URL must be updated + Worker redeployed if it restarts; Bedrock blocked on AWS payment method; OpenAI blocked on account credits — both to be retested once resolved (code already built for both)

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
