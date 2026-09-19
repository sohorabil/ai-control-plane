from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.config import EDGE_SECRET
from app.providers import workers_ai

app = FastAPI(title="AI Control Plane Gateway")


class ChatRequest(BaseModel):
    prompt: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/chat")
async def chat(req: ChatRequest, x_edge_secret: str | None = Header(default=None)):
    # The Worker injects this header after checking the client's key. If it's
    # missing or wrong, the request didn't really come through the edge front door.
    if not EDGE_SECRET or x_edge_secret != EDGE_SECRET:
        raise HTTPException(status_code=401, detail="missing or invalid edge secret")

    answer = await workers_ai.chat(req.prompt)
    return {"answer": answer}
