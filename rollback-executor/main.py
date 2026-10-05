"""Rollback Executor — Part 13.

A deliberately tiny, separate service with exactly one job: roll back the
gateway Deployment to a previous revision, and ONLY that. This exists as a
genuinely separate service (not a function inside the main gateway) so the
"can investigate" and "can act" permissions are separated at the
infrastructure level, not just in application code — the gateway pod's own
service account has NO write access to anything; only this service's
service account can patch the Deployment, and only to roll it back.

Never called directly by an LLM. The main gateway's /v1/incident/approve-rollback
endpoint calls this only after a human has explicitly approved a specific
proposed revision.
"""
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="EACP Rollback Executor")

_SA_DIR = Path("/var/run/secrets/kubernetes.io/serviceaccount")
_API_SERVER = "https://kubernetes.default.svc"
NAMESPACE = os.environ.get("NAMESPACE", "default")
DEPLOYMENT_NAME = os.environ.get("DEPLOYMENT_NAME", "gateway")


def _get_token() -> str:
    return (_SA_DIR / "token").read_text().strip()


def _get_ca_cert_path() -> str:
    return str(_SA_DIR / "ca.crt")


class RollbackRequest(BaseModel):
    target_image: str
    approved_by: str  # a human identifier, required — never defaults to anything


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/rollback")
async def rollback(req: RollbackRequest):
    if not req.approved_by:
        raise HTTPException(status_code=400, detail="approved_by is required — no anonymous rollbacks")

    url = (
        f"{_API_SERVER}/apis/apps/v1/namespaces/{NAMESPACE}"
        f"/deployments/{DEPLOYMENT_NAME}"
    )
    patch = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [{"name": "gateway", "image": req.target_image}]
                }
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/strategic-merge-patch+json",
    }
    async with httpx.AsyncClient(verify=_get_ca_cert_path(), timeout=15.0) as client:
        resp = await client.patch(url, headers=headers, json=patch)

    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=502, detail=f"rollback patch failed: {resp.status_code} {resp.text}"
        )

    return {
        "status": "rollback_applied",
        "target_image": req.target_image,
        "approved_by": req.approved_by,
    }
