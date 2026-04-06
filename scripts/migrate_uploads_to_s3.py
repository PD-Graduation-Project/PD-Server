"""
Migration script to upload existing local files to MinIO
and update file_path in database.

Usage:
    python scripts/migrate_uploads_to_s3.py

Prerequisites:
    - MinIO must be running and accessible
    - STORAGE_BACKEND should be set to "s3" in .env
    - Database must have existing TestInput records with local paths
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from models.database import db
from models.test_models import TestInput
from utils.s3_storage import get_storage
from utils.storage import UPLOAD_DIR


def migrate():
    app = create_app()
    with app.app_context():
        storage = get_storage()
        storage.create_bucket_if_not_exists()

        inputs = TestInput.query.filter(TestInput.file_path.isnot(None)).all()
        migrated = 0
        skipped = 0
        failed = 0

        for inp in inputs:
            local_path = inp.file_path

            # Normalize path: strip /app/ prefix if present
            if local_path.startswith("/app/"):
                local_path = local_path.replace("/app/", "")

            # Check if already migrated (no uploads/ prefix)
            if not local_path.startswith("uploads/"):
                skipped += 1
                continue

            s3_key = local_path.replace("uploads/", "")

            # Try multiple possible local paths
            possible_paths = [
                Path("/app") / local_path,
                Path(UPLOAD_DIR) / local_path.replace("uploads/", ""),
                Path(local_path),
            ]
            full_local_path = None
            for p in possible_paths:
                if p.exists():
                    full_local_path = p
                    break

            if not full_local_path:
                print(f"File not found: {possible_paths[0]}")
                failed += 1
                continue

            print(f"Uploading {local_path} -> {s3_key}...")
            success = storage.upload_file(str(full_local_path), s3_key)

            if success:
                inp.file_path = s3_key
                db.session.commit()
                print(f"Migrated: {local_path} -> {s3_key}")
                migrated += 1
            else:
                print(f"Failed to upload: {local_path}")
                failed += 1

        print(f"\nMigration complete:")
        print(f"  Migrated: {migrated}")
        print(f"  Skipped:  {skipped}")
        print(f"  Failed:   {failed}")


if __name__ == "__main__":
    migrate()
