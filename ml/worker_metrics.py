"""
Prometheus metrics endpoint for the RQ ML worker.

Started as a background process by worker-entrypoint.sh.
Reads RQ job stats from Redis and exposes them on port 6001 at /metrics.
"""

import os
import time
from datetime import datetime, timezone

from prometheus_client import Gauge, Histogram, start_http_server


def _redis():
    from redis import Redis

    return Redis.from_url(os.environ["REDIS_URL"])


# ── Metrics ───────────────────────────────────────────────────────────────────
ML_QUEUE_DEPTH = Gauge(
    "pd_ml_queue_depth",
    "Current number of jobs in the ML queue",
)
ML_QUEUE_OLDEST_SECONDS = Gauge(
    "pd_ml_queue_oldest_seconds",
    "Age in seconds of the oldest queued ML job",
)
ML_WORKER_JOBS_PROCESSED = Gauge(
    "pd_ml_worker_jobs_processed_total",
    "Total ML jobs processed (completed + failed)",
)
ML_WORKER_COMPLETED = Gauge(
    "pd_ml_worker_completed_total",
    "Total completed ML jobs",
)
ML_WORKER_FAILED = Gauge(
    "pd_ml_worker_failed_total",
    "Total failed ML jobs",
)
ML_WORKER_DURATION_AVG = Gauge(
    "pd_ml_worker_duration_avg_seconds",
    "Average ML inference job duration in seconds",
)
ML_WORKER_DURATION_SECONDS = Histogram(
    "pd_ml_worker_job_duration_seconds",
    "ML job duration in seconds",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)
ML_WORKER_RSS_BYTES = Gauge(
    "pd_ml_worker_rss_bytes",
    "Worker process RSS memory in bytes",
)
WORKER_UP = Gauge("pd_worker_up", "1 if the worker metrics endpoint is reachable")


def _get_rq_worker_pid():
    import subprocess

    try:
        pid = subprocess.check_output(
            ["pgrep", "-f", "rq worker ml"], timeout=5
        ).decode().strip().split("\n")[0]
        return int(pid) if pid else None
    except Exception:
        return None


def _read_proc_status(pid: int) -> dict:
    try:
        with open(f"/proc/{pid}/status") as f:
            raw = f.read()
        result = {}
        for line in raw.splitlines():
            parts = line.split(":\t", 1)
            if len(parts) == 2:
                result[parts[0].strip()] = parts[1].strip()
        return result
    except Exception:
        return {}


def collect_metrics() -> None:
    try:
        r = _redis()

        queue_depth = int(r.llen("rq:queue:ml"))
        ML_QUEUE_DEPTH.set(queue_depth)

        oldest_seconds = 0.0
        if queue_depth > 0:
            oldest_job_id = r.lindex("rq:queue:ml", -1)
            if oldest_job_id:
                if isinstance(oldest_job_id, bytes):
                    oldest_job_id = oldest_job_id.decode("utf-8")
                enqueued_at = r.hget(f"rq:job:{oldest_job_id}", "enqueued_at")
                if enqueued_at:
                    if isinstance(enqueued_at, bytes):
                        enqueued_at = enqueued_at.decode("utf-8")
                    enqueued_dt = datetime.fromisoformat(enqueued_at.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    oldest_seconds = max(0.0, (now - enqueued_dt).total_seconds())
        ML_QUEUE_OLDEST_SECONDS.set(oldest_seconds)

        completed = int(r.get("pd:ml:completed_total") or 0)
        failed = int(r.get("pd:ml:failed_total") or 0)
        ML_WORKER_COMPLETED.set(completed)
        ML_WORKER_FAILED.set(failed)
        ML_WORKER_JOBS_PROCESSED.set(completed + failed)

        duration_sum = float(r.get("pd:ml:duration_sum_seconds") or 0)
        duration_count = int(r.get("pd:ml:duration_count") or 0)
        ML_WORKER_DURATION_AVG.set(duration_sum / duration_count if duration_count > 0 else 0)

        r.close()
    except Exception as e:
        print(f"Redis metrics error: {e}")

    try:
        pid = _get_rq_worker_pid()
        if pid:
            status = _read_proc_status(pid)
            vm_rss_kb = status.get("VmRSS", "0").rstrip(" kB")
            ML_WORKER_RSS_BYTES.set(int(vm_rss_kb) * 1024 if vm_rss_kb.isdigit() else 0)
    except Exception as e:
        print(f"Process metrics error: {e}")

    WORKER_UP.set(1)


def main() -> None:
    port = int(os.environ.get("WORKER_METRICS_PORT", "6001"))
    start_http_server(port)
    print(f"Worker metrics server started on port {port}")

    while True:
        try:
            collect_metrics()
        except Exception as e:
            print(f"Metrics collection error: {e}")
        time.sleep(15)


if __name__ == "__main__":
    main()
