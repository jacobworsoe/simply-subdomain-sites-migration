import functions_framework
from google.cloud import bigquery
import json

PROJECT = "python-api-246309"
DATASET = "size_monitor"
TABLE_MONITORS = f"{PROJECT}.{DATASET}.monitors"
TABLE_MEASUREMENTS = f"{PROJECT}.{DATASET}.measurements"

client = bigquery.Client(project=PROJECT)


@functions_framework.http
def delete_monitor(request):
    """HTTP Cloud Function: remove a URL from monitors and its measurements.

    Expects JSON body: {"url": "https://..."}
    Returns 200 on success, 400 on bad input, 404 if not found.
    """
    if request.method == "OPTIONS":
        return _cors_preflight()

    if request.method != "DELETE" and request.method != "POST":
        return _json({"error": "Method not allowed"}, 405)

    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()

    if not url:
        return _json({"error": "url is required"}, 400)

    # Check it exists
    check = f"SELECT COUNT(*) AS cnt FROM `{TABLE_MONITORS}` WHERE url = @url"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("url", "STRING", url)]
    )
    count = next(client.query(check, job_config=job_config).result()).cnt
    if count == 0:
        return _json({"error": "URL not found"}, 404)

    # Delete from monitors
    del_monitors = f"DELETE FROM `{TABLE_MONITORS}` WHERE url = @url"
    client.query(del_monitors, job_config=job_config).result()

    # Delete measurements
    del_measurements = f"DELETE FROM `{TABLE_MEASUREMENTS}` WHERE url = @url"
    client.query(del_measurements, job_config=job_config).result()

    return _json({"status": "ok", "deleted_url": url})


def _json(data, status=200):
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    return (json.dumps(data), status, headers)


def _cors_preflight():
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "3600",
    }
    return ("", 204, headers)
