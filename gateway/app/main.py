import uuid

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.config import EDGE_SECRET
from app.db import SessionLocal, Usage, init_db
from app.pricing import cost_usd
from app.providers import bedrock, mock, openai, vertex, workers_ai

app = FastAPI(title="AI Control Plane Gateway")

PROVIDERS = {
    "mock": mock,
    "workers_ai": workers_ai,
    "bedrock": bedrock,
    "vertex": vertex,
    "openai": openai,
}

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
async def chat(req: ChatRequest, x_edge_secret: str | None = Header(default=None)):
    # The Worker injects this header after checking the client's key. If it's
    # missing or wrong, the request didn't really come through the edge front door.
    if not EDGE_SECRET or x_edge_secret != EDGE_SECRET:
        raise HTTPException(status_code=401, detail="missing or invalid edge secret")

    return await _run_chat(req)


@app.post("/v1/chat/playground")
async def chat_playground(req: ChatRequest):
    # No edge-secret check: this route only exists so the browser-rendered
    # /playground page can call it directly for local, side-by-side testing.
    # It must never be used by real client apps — those go through /v1/chat.
    return await _run_chat(req)


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
