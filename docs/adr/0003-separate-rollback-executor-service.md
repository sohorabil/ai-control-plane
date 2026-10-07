# ADR 0003 — A separate Rollback Executor service, not a write permission on the gateway's own identity

**Status**: Accepted
**Date**: 2026-10-05 (Part 13)

## Context

The Incident Copilot investigates production issues using read-only tools (Prometheus,
Kubernetes pods/logs/events/deploy history, runbook RAG) and proposes a rollback for a human to
approve. Once approved, something has to actually execute the `kubectl patch` that performs the
rollback. The simplest implementation would grant the gateway's own service account
(`eacp-gateway`) both the existing read permissions and a new `patch` permission on the
Deployment.

## Decision

Build a genuinely separate microservice (`rollback-executor/`) with its own `ServiceAccount` and
its own RBAC `Role`, scoped via `resourceNames: ["gateway"]` to patch *only* that one Deployment.
The gateway calls this service over HTTP after a human approval; the gateway process itself holds
no Kubernetes write credentials of any kind.

## Why

Granting write permission to the same service account used for read-only investigation would
defeat the RBAC-level separation in practice: any code path in that one pod — the investigation
logic, a future feature, a bug — could technically trigger a rollback, whether or not the human
approval step was actually honored by the application code. Code-level safety ("the handler
function won't call patch unless approved") is not the same guarantee as infrastructure-level
safety ("this identity cannot call patch, full stop") — this project's established pattern since
Part 12's SQL validator is to prefer the latter whenever the stakes justify the extra piece.

This was verified directly, not just asserted: `kubectl auth can-i patch deployments --as
system:serviceaccount:default:eacp-gateway` returns `no`, while the same check against
`rollback-executor`'s identity returns `yes` — and only for the named `gateway` Deployment, not
cluster-wide.

## Consequences

- Extra operational surface: a second Dockerfile, a second deployable service, a second set of
  manifests (`k8s/eacp-chart/templates/rollback-executor.yaml` locally,
  `k8s/eks-manifests/rollback-executor.yaml` on real EKS) to keep running and healthy.
- The gateway's `/v1/incident/approve-rollback` endpoint is now a thin HTTP proxy to the
  Rollback Executor rather than performing the action itself — one more network hop, and one
  more service whose `/health` must be monitored.
- This pattern (separate, narrowly-privileged executor service for the one write-capable action)
  is the template to reuse if this project ever adds a second kind of agent-proposed write action
  — the Incident Copilot's design should not be special-cased, it should be the default shape for
  "agent proposes, human approves, a *different* identity executes."
