# Runbooks index

These aren't just reference documents sitting in the repo — four of the five are live content in
the production RAG system (`POST /v1/rag/ask`, Part 7), and the fifth is read directly by the
Incident Copilot (`POST /v1/incident/investigate`, Part 13) as grounding context for its
root-cause hypotheses.

## Support team (served via RAG, with citations)

| Runbook | When to use it |
|---|---|
| [`password_reset_runbook.md`](password_reset_runbook.md) | Customer can't log in, believes it's a password issue |
| [`billing_dispute_runbook.md`](billing_dispute_runbook.md) | Customer disputes a charge ("charged twice", "don't recognize this charge") |
| [`account_recovery_runbook.md`](account_recovery_runbook.md) | Customer believes their account was accessed by someone else |
| [`escalation_runbook.md`](escalation_runbook.md) | When to escalate a ticket to Tier 2 (repeat contacts, unresolved after N attempts, etc.) |

These are synthetic but deliberately written with realistic topical overlap (e.g. account
recovery and password reset both touch login issues) specifically to give Part 7's retrieval
eval something non-trivial to get right — see `evals/retrieval_golden.jsonl` and `PROGRESS.md`
Part 7 for the hit@k results across vector/keyword/hybrid search strategies.

## SRE team (read by the Incident Copilot)

| Runbook | When to use it |
|---|---|
| [`deploy_rollback_runbook.md`](deploy_rollback_runbook.md) | Diagnosing whether a production issue is a bad deploy, a provider outage, or a traffic spike |

Written for Part 13, this runbook describes the recognizable pattern of a deploy-caused incident
(error rate/latency spikes starting right around a new image going live, not gradually) and the
"rollback first, root-cause after" recommended action — explicitly requiring human approval
before any rollback executes. The Incident Agent retrieves this as grounding context when forming
its hypothesis; see [`docs/incidents/`](../incidents/) for a real incident where this pattern was
followed end-to-end.
