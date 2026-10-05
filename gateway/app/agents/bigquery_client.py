"""Minimal BigQuery REST client — Part 12's Analyst Agent.

Raw httpx + the shared Google OAuth token (app/gcp_auth.py), not the
google-cloud-bigquery SDK: that SDK's dependencies conflict with this
project's OpenTelemetry deps (confirmed in Part 11/12 development) and this
project already has a working, hardened auth path (reused from
app/providers/vertex.py) that would otherwise be duplicated.
"""
import httpx

from app.config import GCP_PROJECT_ID
from app.gcp_auth import get_access_token

QUERIES_URL = f"https://bigquery.googleapis.com/bigquery/v2/projects/{GCP_PROJECT_ID}/queries"


class BigQueryError(Exception):
    pass


async def dry_run(sql: str) -> int:
    """Returns the number of bytes this query would process, WITHOUT
    running it — BigQuery estimates this for free, letting us refuse an
    accidental huge scan before paying for it (not just before it's slow —
    before it costs money at all).
    """
    payload = {"query": sql, "useLegacySql": False, "dryRun": True}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            QUERIES_URL,
            headers={"Authorization": f"Bearer {get_access_token()}"},
            json=payload,
        )
    if resp.status_code != 200:
        raise BigQueryError(f"dry run failed: {resp.status_code} {resp.text}")
    return int(resp.json().get("totalBytesProcessed", 0))


async def execute(sql: str) -> dict:
    """Actually runs the (already-validated, already-dry-run-checked) query
    and returns {columns: [...], rows: [[...], ...]} — a plain, JSON-friendly
    shape instead of BigQuery's {f: [{v: ...}]} wire format.
    """
    payload = {"query": sql, "useLegacySql": False}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            QUERIES_URL,
            headers={"Authorization": f"Bearer {get_access_token()}"},
            json=payload,
        )
    if resp.status_code != 200:
        raise BigQueryError(f"query execution failed: {resp.status_code} {resp.text}")

    data = resp.json()
    columns = [f["name"] for f in data.get("schema", {}).get("fields", [])]
    rows = [[cell.get("v") for cell in row["f"]] for row in data.get("rows", [])]
    return {"columns": columns, "rows": rows, "total_rows": int(data.get("totalRows", 0))}
