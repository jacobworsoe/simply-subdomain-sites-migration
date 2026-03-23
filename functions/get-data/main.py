import functions_framework
from google.cloud import bigquery
import json

PROJECT = "python-api-246309"
DATASET = "size_monitor"
TABLE_MONITORS = f"{PROJECT}.{DATASET}.monitors"
TABLE_MEASUREMENTS = f"{PROJECT}.{DATASET}.measurements"

client = bigquery.Client(project=PROJECT)


@functions_framework.http
def get_data(request):
    """HTTP Cloud Function: read monitors and measurements.

    Query params:
      - (none)      → returns all monitors with their latest measurement
      - url=<url>   → returns all measurements for that URL
    """
    if request.method == "OPTIONS":
        return _cors_preflight()

    url = request.args.get("url")

    if url:
        return _measurements_for_url(url)
    return _all_monitors()


def _all_monitors():
    query = f"""
        SELECT m.url, m.name, m.created_at,
               latest.size_bytes AS latest_size_bytes,
               latest.measured_at AS latest_measured_at
        FROM `{TABLE_MONITORS}` m
        LEFT JOIN (
            SELECT url,
                   size_bytes,
                   measured_at,
                   ROW_NUMBER() OVER (PARTITION BY url ORDER BY measured_at DESC) AS rn
            FROM `{TABLE_MEASUREMENTS}`
        ) latest ON latest.url = m.url AND latest.rn = 1
        ORDER BY m.name
    """
    rows = [dict(row) for row in client.query(query).result()]
    for row in rows:
        _serialise_datetimes(row)
    return _json(rows)


def _measurements_for_url(url):
    query = f"""
        SELECT url, name, measured_at, size_bytes, execution_time_seconds
        FROM `{TABLE_MEASUREMENTS}`
        WHERE url = @url
        ORDER BY measured_at
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("url", "STRING", url)]
    )
    rows = [dict(row) for row in client.query(query, job_config=job_config).result()]
    for row in rows:
        _serialise_datetimes(row)
    return _json(rows)


def _serialise_datetimes(row):
    for key, val in row.items():
        if hasattr(val, "isoformat"):
            row[key] = val.isoformat()


def _json(data, status=200):
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    return (json.dumps(data, default=str), status, headers)


def _cors_preflight():
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "3600",
    }
    return ("", 204, headers)
