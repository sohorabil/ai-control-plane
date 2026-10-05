# Runbook: Diagnosing a Bad Deploy

Use this when the gateway's error rate or latency spikes shortly after a
deploy. Deploy-caused incidents share a recognizable pattern: the problem
starts right around when a new image went live, not gradually.

## Symptoms that point to a bad deploy (not a provider outage or traffic spike)

- Error rate jumped sharply at a specific point in time, rather than rising
  gradually.
- The jump in error rate lines up closely with a recent deployment
  timestamp (check recent deploy history — a new image revision becoming
  active).
- Pod logs show a Python traceback, `ImportError`, `KeyError`, or a
  stack trace immediately after the new pod started — not a provider-side
  error message (e.g. "429 Too Many Requests" from an actual AI provider
  looks different from the application's own code crashing).
- Only ONE provider's requests are failing, consistent across the error
  logs — often means a new deploy introduced a bug specific to how that
  provider is called (a renamed field, a broken conditional), rather than
  that provider itself being down externally.

## What this does NOT look like

- A provider-specific outage affects requests to that provider regardless
  of which app version is running, and typically correlates with that
  provider's own status page, not a deploy timestamp.
- A traffic spike raises latency and request volume together, gradually,
  without necessarily raising the error rate.

## Recommended action

1. Confirm the timing correlation: error rate increase timestamp vs. most
   recent deploy's `created_at` timestamp — if they're within a minute or
   two of each other, treat the new deploy as the primary suspect.
2. Check the new deploy's pod logs for a clear application-level error
   (traceback, exception) as supporting evidence, not just the error rate
   number alone.
3. If confirmed, the standard fix is a ROLLBACK to the immediately
   preceding deploy revision — not a forward-fix — to restore service
   quickly. A forward-fix can happen afterward once the bad deploy's root
   cause is understood.
4. A rollback should only be executed after a human approves it. Never
   roll back (or take any other corrective action) automatically without
   that approval, even when the evidence looks clear-cut.
