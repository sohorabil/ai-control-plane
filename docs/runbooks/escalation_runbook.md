# Runbook: Escalation Procedure

Escalate a support ticket to Tier 2 when any of the following apply:

- The customer has contacted support 3 or more times about the same
  unresolved issue.
- The issue involves a potential security incident (suspected account
  compromise, phishing report, data exposure concern).
- The customer explicitly requests to speak with a manager.
- The refund amount requested exceeds $500 and requires manager approval.
- The issue requires access to systems or data the Tier 1 agent does not
  have permission to view.

To escalate: tag the ticket with `escalated`, write a summary of what's been
tried so far, and assign it to the Tier 2 queue. Do not close the original
ticket — Tier 2 will continue in the same thread so the customer doesn't
have to repeat themselves.

Security-related escalations should also be flagged to the on-call security
engineer immediately, in addition to the normal Tier 2 queue.
