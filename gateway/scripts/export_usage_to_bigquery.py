"""Exports the Postgres usage table to BigQuery for long-term cost history
and finance queries — Part 11's answer to the CFO's "AI spend doubled,
which team, which model, why?" question.

Run daily (manually, or on a schedule via Jenkins/cron). Exports only rows
created since the last successful export (tracked by a local watermark
file) so re-running never double-counts a day's spend.

Usage: python -m scripts.export_usage_to_bigquery [--project-id ID] [--since ISO_DATE]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import bigquery

from app.db import App, SessionLocal, Usage

WATERMARK_FILE = Path(__file__).parent / ".last_export_watermark"
DATASET_ID = "eacp_usage_analytics"
TABLE_ID = "usage_daily"

SCHEMA = [
    bigquery.SchemaField("request_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("app", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("team", "STRING", mode="NULLABLE"),  # from apps.role
    bigquery.SchemaField("provider", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("model", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("input_tokens", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("output_tokens", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("latency_ms", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("cost_usd", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("fallback", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
]


def _read_watermark() -> datetime | None:
    if not WATERMARK_FILE.exists():
        return None
    return datetime.fromisoformat(WATERMARK_FILE.read_text().strip())


def _write_watermark(ts: datetime) -> None:
    WATERMARK_FILE.write_text(ts.isoformat())


def ensure_table(client: bigquery.Client, project_id: str) -> str:
    table_ref = f"{project_id}.{DATASET_ID}.{TABLE_ID}"
    try:
        client.get_table(table_ref)
    except Exception:
        client.create_table(bigquery.Table(table_ref, schema=SCHEMA))
        print(f"Created table {table_ref}")
    return table_ref


def export(project_id: str, since: datetime | None) -> int:
    session = SessionLocal()
    try:
        query = session.query(Usage)
        if since:
            query = query.filter(Usage.created_at > since)
        rows = query.order_by(Usage.created_at).all()

        if not rows:
            return 0

        # team = the app's role (apps.role) — the closest existing concept
        # to "team" in this schema; every app belongs to exactly one role.
        app_roles = {a.app_id: a.role for a in session.query(App).all()}

        client = bigquery.Client(project=project_id)
        table_ref = ensure_table(client, project_id)

        payload = [
            {
                "request_id": r.request_id,
                "app": r.app,
                "team": app_roles.get(r.app),
                "provider": r.provider,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "latency_ms": r.latency_ms,
                "cost_usd": r.cost_usd,
                "status": r.status,
                "fallback": r.fallback,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

        errors = client.insert_rows_json(table_ref, payload)
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {json.dumps(errors)}")

        _write_watermark(rows[-1].created_at)
        return len(rows)
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default="pelagic-cycle-479717-h4")
    parser.add_argument(
        "--since",
        type=lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc),
        default=None,
        help="ISO date to export from (default: resume from the last export's watermark)",
    )
    args = parser.parse_args()

    since = args.since or _read_watermark()
    count = export(args.project_id, since)
    print(f"Exported {count} usage row(s) to {DATASET_ID}.{TABLE_ID}" + (f" (since {since})" if since else " (full history)"))
