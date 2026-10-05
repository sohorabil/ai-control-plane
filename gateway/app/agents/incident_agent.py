"""Incident Agent — Part 13.

Investigates (gathers evidence from Prometheus, Kubernetes, deploy history,
and the runbook RAG system), proposes a root-cause hypothesis and an
action — but NEVER executes anything on its own. Every tool this agent uses
is read-only at the infrastructure level (see k8s_client.py's RBAC, Part
13 PROGRESS.md); the one action it CAN propose (rollback) requires a
separate, explicit human approval call before anything actually happens.

This mirrors the Analyst Agent's design principle from Part 12: safety is
enforced by code/infrastructure, never by trusting the model's own
judgment about whether an action is warranted.
"""
from dataclasses import dataclass, field

from app.agents import k8s_client, prometheus_client
from app.retrieval import hybrid_search


@dataclass
class Evidence:
    error_rate: float | None
    p95_latency: dict
    pods: list[dict]
    recent_events: list[dict]
    recent_deploys: list[dict]
    runbook_guidance: str
    pod_logs_by_name: dict = field(default_factory=dict)


@dataclass
class IncidentReport:
    evidence: Evidence
    hypothesis: str
    proposed_action: str | None
    proposed_rollback_revision: str | None
    status: str  # "investigated" | "no_issue_found" | "error"


async def _gather_evidence(environment: str = "prod") -> Evidence:
    error_rate = await prometheus_client.error_rate(environment=environment)
    p95 = await prometheus_client.p95_latency(environment=environment)
    pods = await k8s_client.list_pods()
    events = await k8s_client.list_recent_events(limit=15)
    deploys = await k8s_client.get_recent_deploys(limit=5)

    # Pull logs from the currently-active gateway pod — the most likely
    # place to see a fresh application-level error.
    pod_logs = {}
    gateway_pods = [p for p in pods if p["name"].startswith("gateway")]
    for pod in gateway_pods[:1]:
        try:
            pod_logs[pod["name"]] = await k8s_client.get_pod_logs(pod["name"], tail_lines=30)
        except Exception as exc:
            pod_logs[pod["name"]] = f"(could not fetch logs: {exc})"

    runbook_chunks = await hybrid_search(
        "how to diagnose if an incident was caused by a bad deploy", top_k=3
    )
    runbook_guidance = "\n\n".join(c["content"] for c in runbook_chunks)

    return Evidence(
        error_rate=error_rate,
        p95_latency=p95,
        pods=pods,
        recent_events=events,
        recent_deploys=deploys,
        runbook_guidance=runbook_guidance,
        pod_logs_by_name=pod_logs,
    )


async def _form_hypothesis(provider_module, evidence: Evidence) -> tuple[str, str | None, str | None]:
    """Asks the LLM to reason over the gathered evidence. Returns
    (hypothesis_text, proposed_action, proposed_rollback_revision).
    The LLM's job here is pattern-matching over evidence, same as a human
    on-call would do by reading the same dashboards/logs — it does NOT
    decide whether to act; it only drafts a recommendation a human reviews.
    """
    evidence_summary = (
        f"Error rate (prod, last 5m): {evidence.error_rate}\n"
        f"P95 latency by provider: {evidence.p95_latency}\n"
        f"Current pods: {evidence.pods}\n"
        f"Recent Kubernetes events: {evidence.recent_events}\n"
        f"Recent deploy history (newest first): {evidence.recent_deploys}\n"
        f"Recent gateway pod logs:\n{evidence.pod_logs_by_name}\n"
        f"Relevant runbook guidance:\n{evidence.runbook_guidance}\n"
    )

    prompt = (
        "You are an SRE incident investigation assistant. Given the evidence "
        "below, determine if there is an active incident, and if so, form a "
        "root-cause hypothesis backed by SPECIFIC evidence (cite the exact "
        "log line, event, or metric value that supports your conclusion — "
        "do not just assert a cause without pointing to the evidence for it). "
        "If the evidence points to a specific bad deploy, name which "
        "revision/image should be rolled back to. You are NOT authorized to "
        "take any action yourself — only propose one for a human to approve.\n\n"
        f"Evidence:\n{evidence_summary}\n\n"
        "Respond in this exact format:\n"
        "HYPOTHESIS: <your root-cause hypothesis with specific evidence cited, "
        "or 'No active incident detected' if evidence looks normal>\n"
        "PROPOSED_ACTION: <e.g. 'Roll back to revision N (image: ...)' or 'None'>\n"
    )

    result = await provider_module.chat(prompt)
    text = result.answer

    hypothesis = "Could not parse a hypothesis from the model's response."
    proposed_action = None
    for line in text.splitlines():
        if line.strip().upper().startswith("HYPOTHESIS:"):
            hypothesis = line.split(":", 1)[1].strip()
        elif line.strip().upper().startswith("PROPOSED_ACTION:"):
            proposed_action = line.split(":", 1)[1].strip()

    rollback_revision = None
    if proposed_action and "revision" in proposed_action.lower():
        import re
        match = re.search(r"revision\s+(\d+)", proposed_action, re.IGNORECASE)
        if match:
            rollback_revision = match.group(1)

    return hypothesis, proposed_action, rollback_revision


async def investigate(provider_module, environment: str = "prod") -> IncidentReport:
    try:
        evidence = await _gather_evidence(environment)
    except Exception as exc:
        return IncidentReport(
            evidence=None, hypothesis=f"Investigation failed: {exc}",
            proposed_action=None, proposed_rollback_revision=None, status="error",
        )

    hypothesis, proposed_action, rollback_revision = await _form_hypothesis(provider_module, evidence)

    status = "no_issue_found" if "no active incident" in hypothesis.lower() else "investigated"

    return IncidentReport(
        evidence=evidence,
        hypothesis=hypothesis,
        proposed_action=proposed_action,
        proposed_rollback_revision=rollback_revision,
        status=status,
    )
