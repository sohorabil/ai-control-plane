# PROGRESS

📍 Now: Part 1 of 14 — Live front door + first AI answer — COMPLETE. Waiting for "next" to start Part 2.
✅ Done: Part 1 — repo init, CLAUDE.md, FastAPI gateway, Cloudflare Worker deployed, AI Gateway + Workers AI wired up, end-to-end + break-it verified, understanding check passed
⏭ Next: Part 2 — One API, four models (Bedrock, Vertex, OpenAI, Workers AI adapters + Postgres usage table + playground)
💰 Spend so far: ~$0 (estimated, Workers AI free tier) · ☁️ Running now: local FastAPI gateway (port 8000) + cloudflared quick tunnel, both needed for the Worker to reach the gateway
🎓 Understanding checks: passed 1 / done 1 (skipped: none) — Q3 needed one re-ask (tunnel direction was reversed), corrected and confirmed
⚠️ Open issues: quick tunnel URL is ephemeral (changes on restart) — wrangler.toml GATEWAY_URL must be updated + Worker redeployed if the tunnel restarts

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
