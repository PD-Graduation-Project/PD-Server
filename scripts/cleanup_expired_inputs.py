#!/usr/bin/env python3
"""
Script to clean up expired test inputs and their files.

Deletes TestInputs where expires_at < now() and removes the associated files.

Usage:
    python scripts/cleanup_expired_inputs.py       # Dry run (shows what would be deleted)
    python scripts/cleanup_expired_inputs.py --run # Actually delete

Environment:
    Uses .env file from project root for database configuration.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask
from loguru import logger

import models.user  # noqa: F401 - needed to resolve User relationship
from config import Config
from models.database import db
from models.test_models import TestInput


def cleanup_expired_inputs(dry_run=True):
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        now = datetime.now(timezone.utc)
        expired = TestInput.query.filter(TestInput.expires_at < now).all()

        if not expired:
            logger.info("No expired inputs to clean up")
            return

        # Check storage backend
        use_s3 = Config.STORAGE_BACKEND == "s3"

        if use_s3:
            from utils.s3_storage import get_storage

            storage = get_storage()
            deleted_files = 0

            for inp in expired:
                if inp.file_path:
                    success = storage.delete_file(inp.file_path)
                    if success:
                        deleted_files += 1

            deleted_inputs = TestInput.query.filter(TestInput.expires_at < now).delete()
            db.session.commit()

            logger.success(
                f"Deleted {deleted_inputs} inputs and {deleted_files} files from S3"
            )
        else:
            # Local filesystem (existing code)
            files_to_delete = []
            total_size = 0

            for inp in expired:
                if inp.file_path:
                    fpath = Path(inp.file_path)
                    if fpath.exists():
                        size = fpath.stat().st_size
                        total_size += size
                        files_to_delete.append((fpath, size))
                    elif inp.file_path.startswith("/app/uploads/"):
                        fpath = Path("/app") / inp.file_path.lstrip("/")
                        if fpath.exists():
                            size = fpath.stat().st_size
                            total_size += size
                            files_to_delete.append((fpath, size))

            size_mb = total_size / (1024 * 1024)

            if dry_run:
                logger.info(f"Would delete {len(expired)} expired inputs:")
                logger.info(
                    f"Would remove {len(files_to_delete)} files ({size_mb:.2f} MB)"
                )
                for fpath, size in files_to_delete[:10]:
                    logger.info(f"  - {fpath} ({size / 1024:.1f} KB)")
                if len(files_to_delete) > 10:
                    logger.info(f"  ... and {len(files_to_delete) - 10} more")
                return

            logger.info(
                f"Deleting {len(expired)} expired inputs and {len(files_to_delete)} files..."
            )

            deleted_files = 0
            for fpath, _ in files_to_delete:
                try:
                    fpath.unlink()
                    deleted_files += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {fpath}: {e}")

            deleted_inputs = TestInput.query.filter(TestInput.expires_at < now).delete()
            db.session.commit()

            logger.success(
                f"Deleted {deleted_inputs} inputs and {deleted_files} files ({size_mb:.2f} MB freed)"
            )


def main():
    dry_run = "--run" not in sys.argv

    if dry_run:
        confirm = input("Dry run - no files will be deleted. Continue? [y/N]: ")
    else:
        confirm = input(
            f"This will permanently delete expired inputs and their files. Continue? [y/N]: "
        )

    if confirm.lower() != "y":
        print("Aborted")
        sys.exit(0)

    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    try:
        cleanup_expired_inputs(dry_run=dry_run)
    except Exception as e:
        logger.exception(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
