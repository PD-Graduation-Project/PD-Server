#!/usr/bin/env python3
"""
Cross-platform entrypoint for Flask app.
Runs migrations then starts the server.
"""

import subprocess
import sys
import time


def run(cmd, check=True, **kwargs):
    """Run command, print output on failure."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if check and result.returncode != 0:
        print(f"ERROR: Command failed with code {result.returncode}")
        if result.stderr:
            print(
                result.stderr.decode()
                if isinstance(result.stderr, bytes)
                else result.stderr
            )
        sys.exit(result.returncode)
    return result


def main():
    import os

    print("Waiting for PostgreSQL to be ready...")

    max_retries = 30
    for i in range(max_retries):
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=os.environ.get("POSTGRES_HOST", "localhost"),
                user=os.environ.get("POSTGRES_USER", "pduser"),
                password=os.environ.get("POSTGRES_PASSWORD", "pdpassword"),
                dbname=os.environ.get("POSTGRES_DB", "pdserver"),
                connect_timeout=1,
            )
            conn.close()
            break
        except Exception:
            print(f"PostgreSQL is unavailable - sleeping ({i + 1}/{max_retries})")
            time.sleep(1)
    else:
        print("ERROR: PostgreSQL not available after 30 seconds")
        sys.exit(1)

    print("PostgreSQL is up - running migrations...")
    run(["flask", "db", "upgrade"])

    if os.environ.get("STORAGE_BACKEND") == "s3":
        print("Waiting for MinIO to be ready...")
        sys.path.insert(0, "/app")
        from utils.s3_storage import get_storage

        max_retries = int(os.environ.get("MINIO_WAIT_MAX_RETRIES", "60"))
        retry_delay = float(os.environ.get("MINIO_WAIT_RETRY_DELAY", "2"))
        last_error = None
        for i in range(max_retries):
            try:
                print(f"Creating S3 bucket if needed... ({i + 1}/{max_retries})")
                get_storage().create_bucket_if_not_exists()
                break
            except Exception as exc:
                last_error = exc
                print(f"MinIO is unavailable - sleeping ({i + 1}/{max_retries})")
                time.sleep(retry_delay)
        else:
            print("ERROR: MinIO not available in time")
            if last_error:
                print(last_error)
            sys.exit(1)

    print("Starting application...")
    workers = os.environ.get("GUNICORN_WORKERS", "4")
    cmd = (
        sys.argv[1:]
        if len(sys.argv) > 1
        else [
            "gunicorn",
            "--workers",
            workers,
            "--worker-class",
            "gevent",
            "--bind",
            "0.0.0.0:5000",
            "--preload",
            "app:create_app()",
        ]
    )
    result = run(cmd, check=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
