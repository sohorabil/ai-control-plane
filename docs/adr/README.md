# Architecture Decision Records

Each file here captures one significant, genuinely-contested technical decision made during this
project: what was decided, why, what the obvious alternative was, and why it was rejected. These
are not a record of every choice made — only the ones a new engineer would plausibly question or
accidentally undo without this context.

| ADR | Decision |
|---|---|
| [0001](0001-separate-local-and-eks-manifests.md) | Separate manifests for local (kind) and real EKS, not one parameterized chart |
| [0002](0002-sqlparse-over-regex-for-sql-safety.md) | Real SQL tokenizer (`sqlparse`), not regex, for the Analyst Agent's safety gate |
| [0003](0003-separate-rollback-executor-service.md) | A separate Rollback Executor service, not a write permission on the gateway's own identity |
| [0004](0004-replicaset-history-over-helm-secrets.md) | Deploy history via ReplicaSets, not Helm release Secrets |
| [0005](0005-workers-ai-over-bedrock-for-support-chat.md) | `workers_ai` promoted over `bedrock` as `support_chat`'s primary provider |

For the full build history behind each decision — including bugs found, verification results,
and understanding-check outcomes — see [`PROGRESS.md`](../../PROGRESS.md).
