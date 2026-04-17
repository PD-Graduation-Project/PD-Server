import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional

from loguru import logger
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from config import Config

UPLOAD_DIR = Path(Config.UPLOAD_FOLDER)

# Thread pool for async IMU file writes
# max_workers=4 handles up to 4 simultaneous writes (22 subtests/hand combos max)
_imu_write_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="imu_write")

# Estimated bytes per row in the output format: timestamp (12) + 6 floats (~20 each) + newline
_BYTES_PER_ROW = 140

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


def _get_storage_backend():
    """Get storage backend: 's3' or 'local'."""
    if Config.STORAGE_BACKEND == "s3":
        from utils.s3_storage import get_storage

        return get_storage()
    return None


def _get_s3_key(test_type: str, test_id: int, filename: str) -> str:
    """Generate S3 key from test type, test id, and filename."""
    safe_filename = secure_filename(filename)
    return f"{test_type}/{test_id}/{safe_filename}"


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
    Save an uploaded file to storage (local or S3).

    Returns:
        tuple: (file_path/s3_key, file_size)
    """
    storage = _get_storage_backend()

    if storage:
        # S3: upload directly from file object
        s3_key = _get_s3_key(test_type, test_id, filename)
        content_type = _get_content_type(test_type, filename)

        success, file_size = storage.upload_fileobj(file, s3_key, content_type)
        if not success:
            raise Exception("S3 upload failed")

        return s3_key, file_size
    else:
        # Local: existing code
        upload_dir = get_upload_path(test_type, test_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = secure_filename(filename)
        file_path = upload_dir / safe_filename

        file.save(str(file_path))

        file_size = os.path.getsize(file_path)

        return str(file_path), file_size


def _get_content_type(test_type: str, filename: str) -> str:
    """Get content type based on test type and file extension."""
    ext = get_file_extension(filename).lower()

    content_types = {
        "drawing": {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"},
        "voice": {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4"},
        "tremor": {"txt": "text/plain"},
    }

    return content_types.get(test_type, {}).get(ext, "application/octet-stream")


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
    """Delete a file from storage (local or S3)."""
    storage = _get_storage_backend()

    if storage:
        # S3: delete from S3
        return storage.delete_file(file_path)
    else:
        # Local: existing code
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                return True
            return False
        except Exception:
            return False


def _write_imu_data(file_path: Path, imu_data: dict, sample_rate: float) -> None:
    """
    Background worker that writes IMU data to disk.
    Runs in a thread pool — any exception is logged but not propagated.
    """
    ax = imu_data.get("ax", [])
    ay = imu_data.get("ay", [])
    az = imu_data.get("az", [])
    gx = imu_data.get("gx", [])
    gy = imu_data.get("gy", [])
    gz = imu_data.get("gz", [])

    num_samples = len(ax)
    dt = 1.0 / sample_rate

    try:
        with open(file_path, "w") as f:
            for i in range(num_samples):
                timestamp = i * dt
                f.write(
                    f"{timestamp:.10f},{ax[i]},{ay[i]},{az[i]},{gx[i]},{gy[i]},{gz[i]}\n"
                )
        logger.debug(f"Async IMU write completed: {file_path}")
    except Exception as e:
        logger.error(f"Async IMU write failed for {file_path}: {e}")


def save_imu_data(
    test_type: str,
    test_id: int,
    filename: str,
    imu_data: dict,
    sample_rate: float = 100.0,
) -> tuple[str, int]:
    """
    Save IMU data arrays to storage (local or S3).

    Format (no header, 7 float columns):
        timestamp,ax,ay,az,gx,gy,gz
        0.0000000000,ax0,ay0,az0,gx0,gy0,gz0
        ...

    Args:
        test_type: Type of test (tremor)
        test_id: Test session ID
        filename: Name of the file
        imu_data: Dict with keys ax, ay, az, gx, gy, gz (each a list of floats)
        sample_rate: Sampling rate in Hz used to compute timestamps (default 100 Hz)

    Returns:
        tuple: (file_path/s3_key, estimated_file_size)
    """
    storage = _get_storage_backend()

    ax = imu_data.get("ax", [])
    ay = imu_data.get("ay", [])
    az = imu_data.get("az", [])
    gx = imu_data.get("gx", [])
    gy = imu_data.get("gy", [])
    gz = imu_data.get("gz", [])

    if not (len(ay) == len(ax) == len(az) == len(gx) == len(gy) == len(gz)):
        raise ValueError("All IMU arrays must have the same length")

    # Build content as string for S3 upload
    content_lines = []
    dt = 1.0 / sample_rate
    for i in range(len(ax)):
        timestamp = i * dt
        content_lines.append(
            f"{timestamp:.10f},{ax[i]},{ay[i]},{az[i]},{gx[i]},{gy[i]},{gz[i]}\n"
        )
    content = "".join(content_lines)
    file_size = len(content.encode("utf-8"))

    if storage:
        # S3: upload from string buffer
        s3_key = _get_s3_key(test_type, test_id, filename)
        file_obj = BytesIO(content.encode("utf-8"))
        success, _ = storage.upload_fileobj(file_obj, s3_key, "text/plain", file_size)
        if not success:
            raise Exception("S3 upload failed")
        return s3_key, file_size
    else:
        # Local: existing code
        upload_dir = get_upload_path(test_type, test_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = secure_filename(filename)
        file_path = upload_dir / safe_filename

        _write_imu_data(file_path, imu_data, sample_rate)

        actual_size = file_path.stat().st_size if file_path.exists() else 0
        return str(file_path), actual_size


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
