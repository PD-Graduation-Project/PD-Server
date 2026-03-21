#!/usr/bin/env python3
"""
Script to clear test data and optionally uploads folder.

WARNING: This deletes all test data. Use with caution in development.

Usage:
    python scripts/clear_test_data.py          # DB only
    python scripts/clear_test_data.py --all     # DB + uploads

Environment:
    Uses .env file from project root for database configuration.
"""

import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask
from loguru import logger

import models.user  # noqa: F401 - needed to resolve User relationship
from config import Config
from models.database import db
from models.test_models import TestGroup

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"


def clear_test_data():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        group_count = TestGroup.query.delete()
        db.session.commit()

        if group_count == 0:
            logger.info("No test data to clear")
            return False

        logger.success(
            f"Cleared {group_count} test groups (cascaded to sessions and inputs)"
        )
        return True


def clear_uploads():
    if not UPLOADS_DIR.exists():
        logger.info("Uploads folder does not exist")
        return

    files = list(UPLOADS_DIR.rglob("*"))
    file_count = len([f for f in files if f.is_file()])
    dir_count = len([f for f in files if f.is_dir()])

    if file_count == 0:
        logger.info("Uploads folder is already empty")
        return

    shutil.rmtree(UPLOADS_DIR)
    UPLOADS_DIR.mkdir(exist_ok=True)

    logger.success(f"Cleared uploads folder ({file_count} files, {dir_count} dirs)")


def main():
    clear_all = "--all" in sys.argv

    if clear_all:
        confirm = input(
            "This will delete ALL test data (DB) AND uploads folder. Continue? [y/N]: "
        )
    else:
        confirm = input(
            "This will delete ALL test data (TestGroup, TestSession, TestInput). Continue? [y/N]: "
        )

    if confirm.lower() != "y":
        print("Aborted")
        sys.exit(0)

    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)

    try:
        db_cleared = clear_test_data()
        if clear_all:
            clear_uploads()
        logger.info("Done!")
    except Exception as e:
        logger.exception(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
