# Runbook: Account Recovery (Suspected Compromise)

When a customer reports they believe their account has been accessed by
someone else, follow these steps:

1. Immediately offer to force-expire all active sessions for the account.
2. Ask the customer to reset their password using the "Forgot Password"
   flow once sessions are expired.
3. Recommend the customer enable two-factor authentication (2FA) if not
   already active.
4. Review recent account activity logs with the customer to identify any
   unauthorized changes (email address, payment method, shipping address).
5. If any unauthorized changes are found, revert them and flag the account
   for the security team to review, per the Escalation Runbook.
6. Document the incident, including what the customer reported and what
   actions were taken, in the ticket.

This is always treated as a security-related escalation — flag the on-call
security engineer per the Escalation Runbook, even if the issue seems minor.
