import json
import uuid

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from app.auth import authenticate_app, check_provider_allowed
from app.config import EDGE_SECRET
from app.db import App, AuditLog, SessionLocal, Usage, init_db
from app.guardrails import check_prompt_injection, redact_pii, scan_for_pii
from app.pricing import cost_usd
from app.prompts import load_prompt
from app.providers import bedrock, mock, openai, vertex, workers_ai
from app.rate_limit import check_rate_limit
from app.routing import AllProvidersFailedError, call_with_fallback, get_cached, set_cached
from app.structured import chat_structured, extract_structured_from_document

app = FastAPI(title="AI Control Plane Gateway")

PROVIDERS = {
    "mock": mock,
    "workers_ai": workers_ai,
    "bedrock": bedrock,
    "vertex": vertex,
    "openai": openai,
}

# Only providers with chat_stream() implemented so far.
STREAMING_PROVIDERS = {"mock": mock, "vertex": vertex}

# Only providers with chat_with_tools() implemented so far.
TOOL_PROVIDERS = {"mock": mock, "bedrock": bedrock}

MODEL_NAMES = {
    "mock": "mock-echo",
    "workers_ai": "llama-3.1-8b",
    "bedrock": "claude-haiku-4.5",
    "vertex": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
}


@app.on_event("startup")
async def on_startup():
    init_db()


class ChatRequest(BaseModel):
    prompt: str
    provider: str = "mock"
    app_name: str = "playground"


@app.get("/health")
async def health():
    return {"status": "ok"}


def _log_usage(request_id, app_name, provider, result, status, fallback=None):
    session = SessionLocal()
    try:
        session.add(
            Usage(
                request_id=request_id,
                app=app_name,
                provider=provider,
                model=MODEL_NAMES.get(provider, provider),
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                cost_usd=cost_usd(provider, result.input_tokens, result.output_tokens),
                status=status,
                fallback=fallback,
            )
        )
        session.commit()
    finally:
        session.close()


def _log_audit(app_id: str, event_type: str, detail: dict) -> None:
    session = SessionLocal()
    try:
        session.add(AuditLog(app_id=app_id, event_type=event_type, detail=detail))
        session.commit()
    finally:
        session.close()


async def _run_chat(req: ChatRequest) -> dict:
    """Shared logic: call the chosen provider, log usage, shape the response.

    Used by both the authenticated /v1/chat (real apps, via the Worker) and
    the unauthenticated /v1/chat/playground (local browser testing only).
    """
    if req.provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"unknown provider: {req.provider}")

    request_id = str(uuid.uuid4())
    try:
        result = await PROVIDERS[req.provider].chat(req.prompt)
    except Exception as exc:
        _log_usage(
            request_id,
            req.app_name,
            req.provider,
            type("R", (), {"input_tokens": 0, "output_tokens": 0, "latency_ms": 0})(),
            status="error",
        )
        raise HTTPException(status_code=502, detail=f"{req.provider} call failed: {exc}")

    _log_usage(request_id, req.app_name, req.provider, result, status="ok")

    return {
        "request_id": request_id,
        "provider": req.provider,
        "answer": result.answer,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "cost_usd": cost_usd(req.provider, result.input_tokens, result.output_tokens),
    }


@app.post("/v1/chat")
async def chat(
    req: ChatRequest,
    x_edge_secret: str | None = Header(default=None),
    x_app_key: str | None = Header(default=None),
):
    # The Worker injects this header after checking the client's key. If it's
    # missing or wrong, the request didn't really come through the edge front door.
    if not EDGE_SECRET or x_edge_secret != EDGE_SECRET:
        raise HTTPException(status_code=401, detail="missing or invalid edge secret")

    if not x_app_key:
        raise HTTPException(status_code=401, detail="missing x-app-key")
    app_record = authenticate_app(x_app_key)

    check_rate_limit(app_record.app_id)
    check_provider_allowed(app_record, req.provider)

    # Redact PII first so a safety classifier downstream (Llama Guard) never
    # sees the raw SSN/card number/etc. — it would otherwise flag "contains
    # PII" as unsafe on its own, which conflicts with our redact-and-continue
    # policy. Injection detection runs on the already-redacted text.
    pii_found = scan_for_pii(req.prompt)
    prompt_to_send = req.prompt
    if pii_found:
        prompt_to_send = redact_pii(req.prompt)
        _log_audit(app_record.app_id, "pii_redacted", {"types": list(pii_found.keys())})

    injection_result = await check_prompt_injection(prompt_to_send)
    if injection_result["flagged"]:
        _log_audit(app_record.app_id, "injection_blocked", injection_result)
        raise HTTPException(status_code=400, detail="request blocked: possible prompt injection")

    req_with_app = req.model_copy(update={"prompt": prompt_to_send, "app_name": app_record.app_id})
    return await _run_chat(req_with_app)


@app.post("/v1/chat/playground")
async def chat_playground(req: ChatRequest):
    # No edge-secret check: this route only exists so the browser-rendered
    # /playground page can call it directly for local, side-by-side testing.
    # It must never be used by real client apps — those go through /v1/chat.
    return await _run_chat(req)


class SmartChatRequest(BaseModel):
    prompt: str
    task: str = "chat"
    app_name: str = "playground"


@app.post("/v1/chat/smart")
async def chat_smart(req: SmartChatRequest, x_edge_secret: str | None = Header(default=None)):
    # Same auth as the real client-facing /v1/chat — this route is meant to
    # be a production path too, just routed by task type instead of an
    # explicit provider, with caching/retry/fallback/circuit-breaker built in.
    if not EDGE_SECRET or x_edge_secret != EDGE_SECRET:
        raise HTTPException(status_code=401, detail="missing or invalid edge secret")

    first_provider = "workers_ai"  # cache key uses the first candidate for simplicity
    cached = get_cached(first_provider, req.prompt)
    if cached:
        cached["from_cache"] = True
        return cached

    request_id = str(uuid.uuid4())
    try:
        provider_name, result, attempted = await call_with_fallback(
            PROVIDERS, req.task, req.prompt
        )
    except AllProvidersFailedError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    _log_usage(
        request_id,
        req.app_name,
        provider_name,
        result,
        status="ok",
        fallback=None if len(attempted) == 1 else json.dumps(attempted),
    )

    payload = {
        "request_id": request_id,
        "provider": provider_name,
        "answer": result.answer,
        "latency_ms": result.latency_ms,
        "cost_usd": cost_usd(provider_name, result.input_tokens, result.output_tokens),
        "attempted": attempted,
        "from_cache": False,
    }
    set_cached(first_provider, req.prompt, payload)
    return payload


class TicketLookup(BaseModel):
    ticket_id: str
    status: str
    subject: str


class StructuredChatRequest(BaseModel):
    prompt: str
    provider: str = "vertex"


@app.post("/v1/chat/structured")
async def chat_structured_route(req: StructuredChatRequest):
    if req.provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"unknown provider: {req.provider}")

    try:
        parsed, result = await chat_structured(PROVIDERS[req.provider], req.prompt, TicketLookup)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "provider": req.provider,
        "data": parsed.model_dump(),
        "latency_ms": result.latency_ms,
        "cost_usd": cost_usd(req.provider, result.input_tokens, result.output_tokens),
    }


class StreamChatRequest(BaseModel):
    prompt: str
    provider: str = "mock"


@app.post("/v1/chat/stream")
async def chat_stream_route(req: StreamChatRequest):
    if req.provider not in STREAMING_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"provider '{req.provider}' does not support streaming yet",
        )

    async def event_source():
        async for chunk in STREAMING_PROVIDERS[req.provider].chat_stream(req.prompt):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


class ToolChatRequest(BaseModel):
    prompt: str
    provider: str = "mock"
    app_name: str = "playground"


@app.post("/v1/chat/tools")
async def chat_tools_route(req: ToolChatRequest):
    if req.provider not in TOOL_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"provider '{req.provider}' does not support tool calling yet",
        )

    request_id = str(uuid.uuid4())
    try:
        result = await TOOL_PROVIDERS[req.provider].chat_with_tools(req.prompt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{req.provider} call failed: {exc}")

    _log_usage(request_id, req.app_name, req.provider, result, status="ok")

    return {
        "request_id": request_id,
        "provider": req.provider,
        "answer": result.answer,
        "latency_ms": result.latency_ms,
        "cost_usd": cost_usd(req.provider, result.input_tokens, result.output_tokens),
    }


class InvoiceFields(BaseModel):
    vendor_name: str | None
    invoice_number: str | None
    total_amount: str | None
    invoice_date: str | None


DOCUMENT_PROVIDERS = {"vertex": vertex}


@app.post("/v1/extract/document")
async def extract_document(file: UploadFile = File(...), provider: str = "vertex"):
    if provider not in DOCUMENT_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"provider '{provider}' does not support document extraction yet",
        )

    prompt_template = load_prompt("extract_invoice", 1)
    file_bytes = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    try:
        parsed, result = await extract_structured_from_document(
            DOCUMENT_PROVIDERS[provider],
            prompt_template["system"],
            file_bytes,
            mime_type,
            InvoiceFields,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "provider": provider,
        "data": parsed.model_dump(),
        "latency_ms": result.latency_ms,
        "cost_usd": cost_usd(provider, result.input_tokens, result.output_tokens),
    }


@app.get("/demo/streaming", response_class=HTMLResponse)
async def demo_streaming():
    return """
    <html>
    <head><title>Streaming vs Non-Streaming Demo</title></head>
    <body style="font-family: sans-serif; max-width: 700px; margin: 40px auto;">
      <h2>See the difference: streaming vs non-streaming</h2>
      <p>Same prompt, same provider (mock). Watch the timer on each side.</p>
      <button onclick="runBoth()" style="font-size: 16px; padding: 8px 16px;">Run comparison</button>
      <div style="display:flex; gap:20px; margin-top:20px;">
        <div style="flex:1; border:2px solid #ccc; padding:15px; border-radius:8px;">
          <h3>Non-streaming (/v1/chat)</h3>
          <div id="normal-timer" style="color:#888;">not started</div>
          <div id="normal-output" style="min-height:80px; margin-top:10px; font-size:18px;"></div>
        </div>
        <div style="flex:1; border:2px solid #4a90d9; padding:15px; border-radius:8px;">
          <h3>Streaming (/v1/chat/stream)</h3>
          <div id="stream-timer" style="color:#888;">not started</div>
          <div id="stream-output" style="min-height:80px; margin-top:10px; font-size:18px;"></div>
        </div>
      </div>
      <script>
        const prompt = "Explain in one short sentence why the sky is blue during the day.";
        // mock.chat() is intentionally fast (it's our free test provider used
        // everywhere else too) — this demo adds its own artificial wait on
        // the non-streaming side only, so the comparison stays visible
        // without slowing down mock for every other test in the project.
        const SIMULATED_THINKING_MS = 2000;

        async function runNormal() {
          const timerEl = document.getElementById("normal-timer");
          const outEl = document.getElementById("normal-output");
          outEl.innerText = "";
          const start = performance.now();
          timerEl.innerText = "waiting for the FULL answer...";
          const [resp] = await Promise.all([
            fetch("/v1/chat/playground", {
              method: "POST",
              headers: {"content-type": "application/json"},
              body: JSON.stringify({prompt, provider: "mock", app_name: "demo"})
            }),
            new Promise(r => setTimeout(r, SIMULATED_THINKING_MS))
          ]);
          const data = await resp.json();
          const elapsed = ((performance.now() - start) / 1000).toFixed(2);
          timerEl.innerText = "First text appeared after: " + elapsed + "s (all at once)";
          outEl.innerText = data.answer;
        }

        async function runStream() {
          const timerEl = document.getElementById("stream-timer");
          const outEl = document.getElementById("stream-output");
          outEl.innerText = "";
          const start = performance.now();
          timerEl.innerText = "waiting for first word...";
          const resp = await fetch("/v1/chat/stream", {
            method: "POST",
            headers: {"content-type": "application/json"},
            body: JSON.stringify({prompt, provider: "mock"})
          });
          const reader = resp.body.getReader();
          const decoder = new TextDecoder();
          let firstWordTime = null;
          while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value);
            for (const line of chunk.split("\\n")) {
              if (line.startsWith("data: ")) {
                const text = line.slice(6);
                if (text === "[DONE]") continue;
                if (firstWordTime === null) {
                  firstWordTime = ((performance.now() - start) / 1000).toFixed(2);
                  timerEl.innerText = "First word appeared after: " + firstWordTime + "s";
                }
                outEl.innerText += text;
              }
            }
          }
        }

        function runBoth() {
          runNormal();
          runStream();
        }
      </script>
    </body>
    </html>
    """


@app.get("/playground", response_class=HTMLResponse)
async def playground():
    return """
    <html>
    <head><title>AI Control Plane Playground</title></head>
    <body style="font-family: sans-serif; max-width: 900px; margin: 40px auto;">
      <h2>Playground — send one prompt to all providers</h2>
      <textarea id="prompt" rows="3" style="width:100%;" placeholder="Type a prompt..."></textarea>
      <br><br>
      <button onclick="runAll()">Send to all providers</button>
      <table id="results" style="width:100%; margin-top:20px; border-collapse: collapse;">
        <tr><th style="text-align:left;">Provider</th><th style="text-align:left;">Answer</th><th>Latency (ms)</th><th>Cost (USD)</th></tr>
      </table>
      <script>
        const providers = ["mock", "workers_ai", "bedrock", "vertex", "openai"];
        async function runAll() {
          const prompt = document.getElementById("prompt").value;
          const table = document.getElementById("results");
          table.querySelectorAll("tr.result").forEach(r => r.remove());
          for (const provider of providers) {
            const row = table.insertRow();
            row.className = "result";
            row.insertCell(0).innerText = provider;
            row.insertCell(1).innerText = "...";
            row.insertCell(2).innerText = "";
            row.insertCell(3).innerText = "";
            fetch("/v1/chat/playground", {
              method: "POST",
              headers: {"content-type": "application/json"},
              body: JSON.stringify({prompt, provider, app_name: "playground"})
            }).then(r => r.json()).then(data => {
              row.cells[1].innerText = data.answer || data.detail || "error";
              row.cells[2].innerText = data.latency_ms ?? "";
              row.cells[3].innerText = data.cost_usd !== undefined ? data.cost_usd.toFixed(6) : "";
            }).catch(err => {
              row.cells[1].innerText = "error: " + err;
            });
          }
        }
      </script>
    </body>
    </html>
    """
