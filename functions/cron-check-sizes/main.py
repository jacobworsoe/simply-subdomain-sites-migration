import functions_framework
from google.cloud import bigquery
from datetime import datetime, timezone
import urllib.request
import time
import json

PROJECT = "python-api-246309"
DATASET = "size_monitor"
TABLE_MONITORS = f"{PROJECT}.{DATASET}.monitors"
TABLE_MEASUREMENTS = f"{PROJECT}.{DATASET}.measurements"

client = bigquery.Client(project=PROJECT)


@functions_framework.http
def cron_check_sizes(request):
    """HTTP Cloud Function triggered by Cloud Scheduler.

    Fetches every monitored URL, measures its byte size, and writes a
    row to the measurements table.
    """
    start = time.time()

    monitors = _get_monitors()
    rows = []
    errors = []

    for monitor in monitors:
        url = monitor["url"]
        name = monitor["name"]
        try:
            t0 = time.time()
            size_bytes = _fetch_size(url)
            elapsed = round(time.time() - t0, 6)
            rows.append(
                {
                    "url": url,
                    "name": name,
                    "measured_at": datetime.now(timezone.utc).isoformat(),
                    "size_bytes": size_bytes,
                    "execution_time_seconds": elapsed,
                }
            )
        except Exception as exc:
            errors.append({"url": url, "error": str(exc)})

    insert_errors = []
    if rows:
        insert_errors = client.insert_rows_json(TABLE_MEASUREMENTS, rows)

    total_elapsed = round(time.time() - start, 3)
    response = {
        "checked": len(rows),
        "errors": errors,
        "insert_errors": insert_errors,
        "elapsed_seconds": total_elapsed,
    }
    status = 200 if not errors and not insert_errors else 207
    return (json.dumps(response), status, {"Content-Type": "application/json"})


def _get_monitors():
    query = f"SELECT url, name FROM `{TABLE_MONITORS}`"
    return [{"url": row.url, "name": row.name} for row in client.query(query).result()]


def _fetch_size(url: str) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "size-monitor/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return len(resp.read())
