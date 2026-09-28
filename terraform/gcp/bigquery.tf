# BigQuery datasets for analytics/FinOps history (Part 13's "measurable
# business outcome" reporting). BigQuery has a genuinely free tier (1TB
# queries/mo, 10GB storage/mo) — safe to actually apply, unlike the AWS plan.

resource "google_bigquery_dataset" "usage_analytics" {
  dataset_id  = "eacp_usage_analytics"
  description = "Long-term usage/cost history, exported from the Postgres usage table"
  location    = "US"

  # Free tier keeps this at effectively $0 for this project's data volume;
  # no explicit table expiration set since this is intended as historical data.
}

resource "google_bigquery_dataset" "eval_history" {
  dataset_id  = "eacp_eval_history"
  description = "Historical eval scorecards, for tracking model quality over time"
  location    = "US"
}
