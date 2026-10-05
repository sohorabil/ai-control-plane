"""Schema grounding for the Analyst Agent — Part 12's "schema RAG" step.

Real RAG (embed + vector search) would be overkill for one small, fixed
table — this project's actual schema at this point in the brief. Kept
explicit and small on purpose: this is the thing the LLM is grounded in
before writing SQL, so it never has to guess a column name. Scales
naturally (add an entry here) if more tables are added later; the
SQL validator's ALLOWED_TABLES would need the same addition, by design
(schema grounding and the safety allow-list are deliberately two separate,
independently-maintained lists — one wrong doesn't silently misconfigure
the other).
"""

SCHEMA_DESCRIPTION = """\
Table: eacp_usage_analytics.usage_daily
Columns:
  request_id    STRING    - unique ID per AI gateway request
  app           STRING    - which app made the request (e.g. "support-app", "analyst-agent")
  team          STRING    - the app's role/team (e.g. "support", "analyst") - may be NULL for test traffic
  provider      STRING    - which AI provider answered (e.g. "bedrock", "openai", "vertex", "workers_ai", "mock")
  model         STRING    - the specific model used (e.g. "claude-haiku-4.5", "gpt-4o-mini")
  input_tokens  INTEGER   - tokens sent to the model
  output_tokens INTEGER   - tokens the model returned
  latency_ms    INTEGER   - how long the request took, in milliseconds
  cost_usd      FLOAT     - real dollar cost of this one request
  status        STRING    - "ok" or "error"
  fallback      STRING    - JSON array of providers tried, if the first choice failed (NULL otherwise)
  created_at    TIMESTAMP - when the request happened
"""


def get_schema_context() -> str:
    return SCHEMA_DESCRIPTION
