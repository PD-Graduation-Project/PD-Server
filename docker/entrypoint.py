#!/usr/bin/env python3
"""
Cross-platform entrypoint for Flask app.
Runs migrations then starts the server.
"""

import subprocess
import sys


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
    import time

    print("Waiting for PostgreSQL to be ready...")

    max_retries = 30
    for i in range(max_retries):
        result = subprocess.run(
            [
                "psql",
                "-h",
                os.environ.get("POSTGRES_HOST", "localhost"),
                "-U",
                os.environ.get("POSTGRES_USER", "pduser"),
                "-d",
                os.environ.get("POSTGRES_DB", "pdserver"),
                "-c",
                "\\q",
            ],
            env={
                **os.environ,
                "PGPASSWORD": os.environ.get("POSTGRES_PASSWORD", "pdpassword"),
            },
            capture_output=True,
        )
        if result.returncode == 0:
            break
        print(f"PostgreSQL is unavailable - sleeping ({i + 1}/{max_retries})")
        time.sleep(1)
    else:
        print("ERROR: PostgreSQL not available after 30 seconds")
        sys.exit(1)

    print("PostgreSQL is up - running migrations...")
    run(["flask", "db", "upgrade"])

    print("Starting application...")
    cmd = (
        sys.argv[1:]
        if len(sys.argv) > 1
        else [
            "gunicorn",
            "--workers",
            "4",
            "--worker-class",
            "gevent",
            "--bind",
            "0.0.0.0:5000",
            "--preload",
            "app:create_app()",
        ]
    )
    run(cmd, check=False)


if __name__ == "__main__":
    main()
