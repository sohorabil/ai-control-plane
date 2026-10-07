# Incident report: deliberate bad-deploy demo on real EKS (Part 13)

**Date**: 2026-10-06
**Severity**: N/A — deliberately injected, controlled demo, not a real production incident
**Status**: Resolved (rollback executed and verified same session)
**Environment**: Real AWS EKS cluster (`eacp-cluster`, us-east-1), stood up specifically for this
demo and destroyed immediately after

## Summary

A bug was deliberately injected into the gateway's mock provider to prove the Incident Copilot's
full investigate → human-approve → rollback → verify loop against real cloud infrastructure, not
just a local `kind` simulation. The copilot correctly identified the exact bad revision from real
evidence (Prometheus error rate, deploy history, pod logs), a human approved the exact rollback
target, a separately-privileged service executed it, and recovery was verified — all in under two
minutes end-to-end once the bug was live.

This report also documents three genuine (non-deliberate) issues found while standing up the
demo environment itself, before the bug injection — real gaps in the Part 9 Terraform/manifests
that only surfaced by actually deploying to a fresh cluster.

## Timeline (all times 2026-10-06, EDT)

| Time | Event |
|---|---|
| ~11:04 | `terraform apply` started for a fresh EKS cluster + RDS |
| ~11:22 | Cluster/RDS up; gateway pod found crash-looping — **real gap #1**, see below |
| ~11:31 | Gap #1 fixed (Pod Identity Agent add-on installed); gateway healthy |
| ~15:38 | Baseline investigation run: `status: no_issue_found`, correct evidence cited |
| (mid-session) | Prometheus and Vertex-timeout gaps found and fixed — **gaps #2 and #3**, see below |
| 16:03:05 | **Bad deploy**: `kubectl set image` to `eacp-gateway:part13-aws-bad-deploy` (revision 7) — a deliberate `NameError` on every mock-provider call, reverted from source immediately after this demo |
| 16:03:05–16:04 | 5 real `/v1/chat` requests sent with `provider: mock`; all 5 failed with `"mock call failed: name 'undefined_config_variable' is not defined"` |
| ~16:04 | `POST /v1/incident/investigate` called |
| ~16:04 | Copilot reports `status: investigated`, cites a **100% real-Prometheus-measured error rate**, identifies **revision 7** (`part13-aws-bad-deploy`) as the regression, proposes rollback to **revision 6** (`part13-aws-v3`) |
| ~16:04 | `POST /v1/incident/approve-rollback` called with `target_image: part13-aws-v3`, `approved_by: "tk"` |
| ~16:05 | Rollback Executor patches the Deployment; new pod comes up running `part13-aws-v3` |
| ~16:05 | Recovery verified: a real `/v1/chat` call against the mock provider succeeds again |
| ~17:xx | Bug reverted from source (`git checkout`); `terraform destroy` run; all AWS resources independently confirmed gone via direct AWS CLI checks |

## Root cause (of the deliberately injected issue)

A single added line in `gateway/app/providers/mock.py`'s `chat()` function referenced an
undefined variable (`undefined_config_variable`), causing every call to the mock provider to
raise a `NameError`. This is the same class of bug a real bad deploy produces: code that imports
and starts cleanly (so health checks pass) but fails on the actual request path.

## Detection

The Incident Copilot's evidence gathering pulled from four real, independent sources and
correlated them:
- **Prometheus**: `error_rate(environment="prod")` returned `1.0` (100%) — a real PromQL query
  against real scraped metrics, not a mocked value.
- **Kubernetes deploy history** (via ReplicaSets, see ADR 0004): revision 7's creation timestamp
  (`2026-10-06T16:03:05Z`) was the most recent, correlating with the failure onset.
- **Pod logs**: the exact `NameError` traceback text, confirming an application-level failure
  rather than an infrastructure problem.
- **Runbook guidance**: `docs/runbooks/deploy_rollback_runbook.md`, retrieved via RAG, grounding
  the hypothesis in the documented pattern ("error rate spikes right around a new image going
  live, not gradually").

The hypothesis text cited all of the above explicitly, by name and value — not a vague assertion.

## Resolution

A human (`approved_by: "tk"`) reviewed the proposed rollback and explicitly specified the exact
target image (`eacp-gateway:part13-aws-v3`) to the approval endpoint — the endpoint requires this
field; it does not accept a bare "yes" against the agent's own suggestion. The Rollback Executor
— a separate service holding the only write-capable Kubernetes credential in this system (see
ADR 0003) — patched the Deployment. The gateway itself never held write credentials at any point.

## Impact

None — this was a controlled demo against infrastructure stood up specifically for it, using the
free `mock` provider, never exposed to real end users. Total real-AWS cost for the full session
(including the three gaps below, the demo itself, and teardown) was under $1.

## Real gaps found while standing up the environment (not the deliberate bug)

These are documented here because they were genuine production-environment issues, found and
fixed live, the same way an on-call engineer would find and fix them under time pressure —
exactly the texture Part 13 was meant to produce.

1. **EKS Pod Identity Agent add-on was never installed.** Terraform's
   `aws_eks_pod_identity_association` resource (from Part 9) only creates the IAM-role-to-
   service-account *mapping* — it does not install the in-cluster DaemonSet that actually serves
   credentials to pods. Every `boto3.client()` call (built eagerly at import time in
   `bedrock.py`) hung until `CredentialRetrievalError`, crash-looping the gateway pod. Fixed by
   installing the add-on and adding `aws_eks_addon.pod_identity_agent` to `terraform/aws/eks.tf`
   so future applies create it automatically.
2. **No Prometheus existed on real EKS.** Part 11's Prometheus is a local Docker container; it
   has no network path into a real AWS VPC. The Incident Agent's first tool call aborted the
   whole investigation with a DNS failure. Fixed by deploying a minimal in-cluster Prometheus
   (`k8s/eks-manifests/prometheus.yaml`), scraping the gateway's own Service DNS directly.
3. **Vertex's fixed 30-second HTTP timeout was too short** for the Incident Agent's large
   evidence-dump prompt, causing a real `httpcore.ReadTimeout` and a bare `500` on the first
   investigation attempt against real infrastructure. Fixed by bumping the timeout to 60s across
   all 4 of `vertex.py`'s HTTP call sites.

A fourth issue — two investigation responses that briefly appeared to show fabricated evidence
(wrong pod IPs, a nonexistent `postgres-0` pod) — was investigated thoroughly and found to be a
dead local `kubectl port-forward` serving stale data to `curl`, not a real agent bug. Confirmed
by querying the real Kubernetes API directly and cross-checking every field. Logged here as a
reminder: verify a surprising result's actual source before escalating it as a finding.

## Action items

- [x] Add the Pod Identity Agent add-on to Terraform (`eks.tf`) — done this session.
- [x] Add `TRACING_ENABLED` config flag so an environment without an OTel collector doesn't log
      noise that could be mistaken for a real incident — done this session.
- [ ] If EKS is ever used for a longer-lived (non-bounded-demo) session, consider whether
      Prometheus should be provisioned by Terraform/Helm rather than applied ad hoc.
- [ ] Revisit Vertex's HTTP timeout values generally — 60s fixed the immediate issue, but a
      request-size-aware timeout would be more robust long-term.
