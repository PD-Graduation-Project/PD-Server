import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

# Base upload directory
UPLOAD_DIR = Path("uploads")

# Allowed extensions per test type
ALLOWED_EXTENSIONS = {
    "tremor": {"txt"},
    "drawing": {"png", "jpg", "jpeg"},
    "voice": {"wav", "mp3", "m4a"},
}

# Maximum file sizes (in bytes)
MAX_FILE_SIZES = {
    "tremor": 10 * 1024 * 1024,  # 10MB
    "drawing": 30 * 1024 * 1024,  # 30MB
    "voice": 30 * 1024 * 1024,  # 30MB
}

# Data retention period
RETENTION_DAYS = 90


def get_file_extension(filename: str) -> str:
    """Extract file extension from filename."""
    if "." in filename:
        return filename.rsplit(".", 1)[1].lower()
    return ""


def is_allowed_file(filename: str, test_type: str) -> bool:
    """Check if file extension is allowed for the test type."""
    ext = get_file_extension(filename)
    allowed = ALLOWED_EXTENSIONS.get(test_type, set())
    return ext in allowed


def get_upload_path(test_type: str, test_id: int) -> Path:
    """Get the upload directory path for a test."""
    return UPLOAD_DIR / test_type / str(test_id)


def generate_tremor_filename(test_id: int, subtest: str, hand: str) -> str:
    """Generate filename for tremor gyro data."""
    return f"{test_id}_{subtest}_{hand}.txt"


def generate_drawing_filename(hand: str, extension: str) -> str:
    """Generate filename for spiral drawing."""
    return f"spiral_{hand}.{extension}"


def generate_voice_filename(extension: str) -> str:
    """Generate filename for voice recording."""
    return f"recording.{extension}"


def save_uploaded_file(
    file: FileStorage,
    test_type: str,
    test_id: int,
    filename: str,
) -> tuple[str, int]:
    """
    Save an uploaded file to the filesystem.

    Returns:
        tuple: (file_path, file_size)
    """
    upload_dir = get_upload_path(test_type, test_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = secure_filename(filename)
    file_path = upload_dir / safe_filename

    file.save(str(file_path))

    file_size = os.path.getsize(file_path)

    return str(file_path), file_size


def get_expires_at() -> datetime:
    """Calculate expiration date based on retention period."""
    return datetime.utcnow() + timedelta(days=RETENTION_DAYS)


def validate_file_size(file: FileStorage, test_type: str) -> tuple[bool, Optional[str]]:
    """
    Validate file size against maximum allowed.

    Returns:
        tuple: (is_valid, error_message)
    """
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning

    max_size = MAX_FILE_SIZES.get(test_type, 16 * 1024 * 1024)

    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"File size exceeds maximum allowed ({max_mb}MB)"

    return True, None


def validate_tremor_subtest(subtest: str) -> bool:
    """Validate that subtest is a valid tremor subtest name."""
    valid_subtests = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
    return subtest in valid_subtests


def validate_hand(hand: str) -> bool:
    """Validate hand value."""
    return hand in {"l", "r"}


def delete_file(file_path: str) -> bool:
    """Delete a file from the filesystem."""
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False
    except Exception:
        return False


def cleanup_test_directory(test_type: str, test_id: int) -> bool:
    """Remove the test directory and all its contents."""
    try:
        import shutil

        upload_dir = get_upload_path(test_type, test_id)
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
            return True
        return False
    except Exception:
        return False
