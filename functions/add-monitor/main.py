import functions_framework
from google.cloud import bigquery
from datetime import datetime, timezone
import json

PROJECT = "python-api-246309"
DATASET = "size_monitor"
TABLE_MONITORS = f"{PROJECT}.{DATASET}.monitors"

client = bigquery.Client(project=PROJECT)


@functions_framework.http
def add_monitor(request):
    """HTTP Cloud Function: add a new URL to be monitored.

    Expects JSON body: {"url": "https://...", "name": "My File"}
    Returns 201 on success, 4xx on bad input, 409 if already exists.
    """
    if request.method == "OPTIONS":
        return _cors_preflight()

    if request.method != "POST":
        return _json({"error": "Method not allowed"}, 405)

    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    name = (body.get("name") or "").strip()

    if not url or not name:
        return _json({"error": "url and name are required"}, 400)

    # Check if URL already exists
    check_query = f"""
        SELECT COUNT(*) AS cnt
        FROM `{TABLE_MONITORS}`
        WHERE url = @url
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("url", "STRING", url)]
    )
    result = client.query(check_query, job_config=job_config).result()
    count = next(result).cnt
    if count > 0:
        return _json({"error": "URL already monitored"}, 409)

    # Insert into monitors table
    row = {
        "url": url,
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = client.insert_rows_json(TABLE_MONITORS, [row])
    if errors:
        return _json({"error": "Insert failed", "details": errors}, 500)

    return _json({"status": "ok", "url": url, "name": name}, 201)


def _json(data, status=200):
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    return (json.dumps(data), status, headers)


def _cors_preflight():
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "3600",
    }
    return ("", 204, headers)
