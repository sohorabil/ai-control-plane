# ADR 0004 — Deploy history via ReplicaSets, not Helm release Secrets

**Status**: Accepted
**Date**: 2026-10-05 (Part 13)

## Context

The Incident Copilot needs to answer "what changed recently, and to what" as part of root-cause
investigation — specifically, a list of recent deploys (image, revision, timestamp) for the
gateway Deployment. Helm already tracks this as release history, stored as Kubernetes Secrets
(one per release revision). Reading that history would have been the most direct way to get
exactly what Helm itself considers the deploy timeline.

## Decision

Read deploy history from the Deployment's own ReplicaSets (`get_recent_deploys()` in
`k8s_client.py`) instead of Helm's release Secrets.

## Why

Reading Helm's release Secrets would require granting the Incident Agent's (read-only) RBAC role
`get`/`list` on Secrets in the namespace — a meaningfully broader permission than the task needs,
because `eacp-secrets` (the Secret holding real API keys: `EDGE_SECRET`, `CF_API_TOKEN`,
`OPENAI_API_KEY`, the RDS password on EKS) lives in that exact same resource category. RBAC in
Kubernetes can't easily scope "Secrets, but only the Helm-release ones, never the credential
ones" — granting Secret read access grants it to all Secrets in the namespace.

Kubernetes already keeps old ReplicaSets around after every rollout specifically to make deploy
history inspectable (`image`, revision annotation, creation timestamp, current replica count are
all on the ReplicaSet object itself) — this gives the Incident Agent the same "what changed and
when" signal without touching Secrets at all. The existing read-only Role (pods, pods/log,
events, deployments, replicasets — all `get`/`list`/`watch`) already covered this; no RBAC change
was needed.

## Consequences

- Deploy history shows image tags and revision numbers, not Helm's own release metadata (chart
  version, release notes) — sufficient for root-causing "which deploy broke this," but not a
  substitute for `helm history` if a human later wants the full Helm-level picture.
- This is the project's second instance of the same principle as ADR 0003: when a narrower
  permission achieves the same operational goal as a broader one, take the narrower one, even if
  it means slightly more specific code (reading ReplicaSets instead of a one-line `helm history`
  equivalent).
