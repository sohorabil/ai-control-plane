# ADR 0002 — Real SQL tokenizer (`sqlparse`), not regex, for the Analyst Agent's safety gate

**Status**: Accepted
**Date**: 2026-10-05 (Part 12)

## Context

The Analyst Agent lets an LLM generate SQL from a natural-language question, which then runs
against real BigQuery data. Before execution, generated SQL must be verified: exactly one
statement, SELECT-only, every referenced table on an explicit allow-list, a capped `LIMIT`. The
fast, obvious way to check "does this query reference only allowed tables" is a regex over the
SQL text.

## Decision

Use `sqlparse` (a real SQL tokenizer) to validate generated SQL, not regex pattern matching.

## Why

Regex-based SQL safety checks are a well-known bypass surface — SQL's grammar isn't regular
(nested subqueries, comments, string literals containing SQL-like text), so a regex that looks
right for simple cases misses adversarial or merely complex ones. A real tokenizer understands
SQL structure, so "does this reference `secret_table`" can be answered correctly regardless of
how deeply nested the reference is.

This wasn't a hypothetical concern — building this validator surfaced it directly, twice:

1. The first version's table-extraction logic walked `sqlparse`'s nested token tree and only
   saw a subquery's alias, not the table inside it: `SELECT * FROM (SELECT * FROM
   secret_dataset.hidden_table) AS sub` was wrongly **allowed**.
2. The same gap existed for tables referenced via `JOIN`.

Both were fixed by scanning the fully *flattened* token stream for every `FROM`/`JOIN` keyword,
regardless of nesting depth, rather than relying on the tree structure. Both are now permanent
regression tests (`test_rejects_disallowed_table_hidden_inside_subquery`,
`test_rejects_disallowed_table_in_join`) specifically because they were real bugs once, not
hypothetical ones.

## Consequences

- `sqlparse` is an extra dependency, and the validator logic (`flatten()` + keyword scanning) is
  less immediately readable than a one-line regex would have been — a deliberate tradeoff of
  clarity for correctness.
- This validator is the system's actual safety boundary, not the LLM's own judgment. This was
  directly proven, not just argued: a real prompt-injection attempt successfully got the model
  to generate a literal `DELETE` statement, and the validator — not the model changing its
  mind — is what refused it (`status: validation_refused`). See `docs/incidents/` and
  `PROGRESS.md` Part 12 for the full account.
- Any future tool that generates and executes structured output on the model's behalf (not just
  SQL) should default to this same pattern: a real parser-based validator between generation and
  execution, never a regex, and never trust in the model's stated intent alone.
