"""Read-only Kubernetes client — Part 13's Incident Agent.

Talks to the Kubernetes API server directly over HTTPS using the pod's own
mounted service-account token (every pod gets one by default) — no kubectl
binary needed inside the image, no separate credentials to manage.

This client only ever calls GET-shaped Kubernetes API endpoints. The REAL
safety boundary is the RBAC Role (k8s/eacp-chart/templates/incident-agent-rbac.yaml)
bound to this pod's service account, which only grants get/list/watch on
pods, pods/log, events, deployments, replicasets — nothing else, no write
verbs. Even if this client had a bug and tried to call a write endpoint,
the Kubernetes API server itself would reject it with 403, independent of
anything this code does.
"""
from pathlib import Path

import httpx

_SA_DIR = Path("/var/run/secrets/kubernetes.io/serviceaccount")
_API_SERVER = "https://kubernetes.default.svc"


def _get_token() -> str:
    return (_SA_DIR / "token").read_text().strip()


def _get_namespace() -> str:
    return (_SA_DIR / "namespace").read_text().strip()


def _get_ca_cert_path() -> str:
    return str(_SA_DIR / "ca.crt")


async def _get(path: str) -> dict:
    url = f"{_API_SERVER}{path}"
    headers = {"Authorization": f"Bearer {_get_token()}"}
    async with httpx.AsyncClient(verify=_get_ca_cert_path(), timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def list_pods(namespace: str | None = None) -> list[dict]:
    ns = namespace or _get_namespace()
    data = await _get(f"/api/v1/namespaces/{ns}/pods")
    return [
        {
            "name": item["metadata"]["name"],
            "phase": item["status"].get("phase"),
            "ready": all(
                c.get("ready", False) for c in item["status"].get("containerStatuses", [])
            ) if item["status"].get("containerStatuses") else False,
            "restarts": sum(
                c.get("restartCount", 0) for c in item["status"].get("containerStatuses", [])
            ),
            "image": (
                item["spec"]["containers"][0]["image"] if item["spec"].get("containers") else None
            ),
            "created_at": item["metadata"].get("creationTimestamp"),
        }
        for item in data.get("items", [])
    ]


async def get_pod_logs(pod_name: str, namespace: str | None = None, tail_lines: int = 50) -> str:
    ns = namespace or _get_namespace()
    url = f"{_API_SERVER}/api/v1/namespaces/{ns}/pods/{pod_name}/log?tailLines={tail_lines}"
    headers = {"Authorization": f"Bearer {_get_token()}"}
    async with httpx.AsyncClient(verify=_get_ca_cert_path(), timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


async def list_recent_events(namespace: str | None = None, limit: int = 20) -> list[dict]:
    ns = namespace or _get_namespace()
    data = await _get(f"/api/v1/namespaces/{ns}/events")
    events = sorted(
        data.get("items", []),
        key=lambda e: e.get("lastTimestamp") or e.get("eventTime") or "",
        reverse=True,
    )
    return [
        {
            "type": e.get("type"),
            "reason": e.get("reason"),
            "message": e.get("message"),
            "involved_object": e.get("involvedObject", {}).get("name"),
            "last_seen": e.get("lastTimestamp") or e.get("eventTime"),
        }
        for e in events[:limit]
    ]


async def get_recent_deploys(name: str = "gateway", namespace: str | None = None, limit: int = 10) -> list[dict]:
    """Deploy history via the Deployment's ReplicaSets, each tagged with the
    image it ran and the revision number — Kubernetes keeps old ReplicaSets
    around after a rollout specifically for this. Deliberately NOT reading
    Helm's release history (stored as Secrets) to avoid granting the agent
    read access to Secrets, a meaningfully bigger permission than this
    tool needs (eacp-secrets, with real API keys, lives in that same
    category) — this gives the same "what changed and when" signal the
    agent actually needs without ever touching Secrets.
    """
    ns = namespace or _get_namespace()
    data = await _get(f"/apis/apps/v1/namespaces/{ns}/replicasets")
    items = [
        rs for rs in data.get("items", [])
        if rs["metadata"].get("labels", {}).get("app") == name
    ]
    deploys = [
        {
            "revision": rs["metadata"].get("annotations", {}).get(
                "deployment.kubernetes.io/revision"
            ),
            "image": rs["spec"]["template"]["spec"]["containers"][0]["image"],
            "created_at": rs["metadata"]["creationTimestamp"],
            "currently_active": rs["status"].get("replicas", 0) > 0,
        }
        for rs in items
    ]
    deploys.sort(key=lambda d: d["created_at"], reverse=True)
    return deploys[:limit]


async def get_deployment_status(name: str = "gateway", namespace: str | None = None) -> dict:
    ns = namespace or _get_namespace()
    data = await _get(f"/apis/apps/v1/namespaces/{ns}/deployments/{name}")
    spec = data.get("spec", {})
    status = data.get("status", {})
    return {
        "name": name,
        "image": spec["template"]["spec"]["containers"][0]["image"],
        "replicas_desired": spec.get("replicas"),
        "replicas_ready": status.get("readyReplicas", 0),
        "replicas_available": status.get("availableReplicas", 0),
        "updated_at": data.get("metadata", {}).get("annotations", {}).get(
            "deployment.kubernetes.io/revision"
        ),
    }
