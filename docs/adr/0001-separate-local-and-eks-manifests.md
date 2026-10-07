# ADR 0001 — Separate manifests for local (kind) and real EKS, not one parameterized chart

**Status**: Accepted
**Date**: 2026-09-28 (Part 8/9), reaffirmed 2026-10-06 (Part 13)

## Context

The gateway needs to run both locally (fast iteration, free, day-to-day) and on real AWS EKS
(Part 9's and Part 13's billed demo sessions). The obvious approach is one Helm chart with
environment-specific `values.yaml` overrides.

## Decision

Keep `k8s/eacp-chart/` (local kind) and `k8s/eks-manifests/` (real EKS) as genuinely separate
manifest sets, not one parameterized chart.

## Why

The two environments differ in ways that aren't just config values:

- **Local** runs Postgres and Redis as in-cluster pods; **EKS** uses real RDS, so the gateway's
  `DATABASE_URL` comes from a different source entirely (a Kubernetes Secret pointing at a
  cluster-local Service vs. one pointing at an RDS endpoint).
- **Local** has no cloud identity to configure; **EKS** requires Pod Identity (`eacp-gateway`
  service account bound to an IAM role) for Bedrock, which doesn't exist as a concept locally.
- EKS is only stood up for bounded, billed sessions (Part 9, Part 13) — it is not a day-to-day
  environment that needs to track local changes in lockstep.

Trying to force both into one parameterized chart would mean conditional logic sprinkled through
templates for differences that are structural, not cosmetic — harder to read than two small,
honest manifest sets.

## Consequences

- Real, accepted drift: Part 13's `k8s/eks-manifests/gateway.yaml` has `TRACING_ENABLED: "false"`
  and a `PROMETHEUS_URL` pointing at an in-cluster Prometheus that only exists on EKS — neither
  applies to local kind. This is documented inline in the manifest, not a bug to reconcile.
- A change to one (e.g. a new env var the gateway needs) must be manually mirrored to the other
  if it applies to both — there is no single source of truth enforcing consistency. Caught by
  running the local test suite + a real deploy before trusting either environment, not by
  tooling.
- If this project ever needed EKS as a persistent, always-on environment rather than bounded
  demo sessions, this decision should be revisited — at that point the duplication cost would
  likely outweigh the clarity benefit.
