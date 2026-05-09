import json
import os
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

from typing import Optional

from loguru import logger
from werkzeug.utils import secure_filename

from utils.storage import UPLOAD_DIR, _get_storage_backend, get_file_extension

ESP32_LOG_DIR = Path("/app/logs/esp32")

ALLOWED_LOG_EXTENSIONS = {"log", "txt", "json", "jsonl"}
MAX_LOG_FILE_SIZE = 16 * 1024 * 1024


def _get_s3_key(device_id: str, filename: str) -> str:
    return f"logs/{device_id}/{filename}"


def _get_local_path(device_id: str, filename: str) -> str:
    log_dir = UPLOAD_DIR / "logs" / device_id
    log_dir.mkdir(parents=True, exist_ok=True)
    return str(log_dir / filename)


def _get_promtail_path(device_id: str) -> Path:
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    device_dir = ESP32_LOG_DIR / device_id
    device_dir.mkdir(parents=True, exist_ok=True)
    return device_dir / f"{date_str}.log"


def is_allowed_log_file(filename: str) -> bool:
    return get_file_extension(filename) in ALLOWED_LOG_EXTENSIONS


def save_log_file(file, device_id: str, filename: str, log_type: Optional[str] = None) -> tuple[str, int]:
    unique_id = uuid.uuid4().hex[:12]
    safe_filename = f"{unique_id}_{secure_filename(filename)}"
    timestamp = datetime.utcnow().isoformat()

    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_LOG_FILE_SIZE:
        raise ValueError(f"File size exceeds maximum allowed ({MAX_LOG_FILE_SIZE // (1024*1024)}MB)")

    content = file.read()

    storage = _get_storage_backend()
    if storage:
        s3_key = _get_s3_key(device_id, safe_filename)
        file_obj = BytesIO(content)
        success, _ = storage.upload_fileobj(file_obj, s3_key, "text/plain", file_size)
        if not success:
            raise Exception("S3 upload failed")
        file_path = s3_key
    else:
        file_path = _get_local_path(device_id, safe_filename)
        Path(file_path).write_bytes(content)

    _append_to_promtail(content, device_id, timestamp, log_type)

    return file_path, file_size


def _parse_esp32_log_line(raw: str) -> Optional[dict]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {
        "ts": parsed.get("timestamp", ""),
        "level": parsed.get("level", "UNKNOWN"),
        "service": parsed.get("service", ""),
        "test_id": parsed.get("test_id"),
        "message": parsed.get("message", raw),
    }


def _append_to_promtail(content: bytes, device_id: str, upload_time: str, log_type: Optional[str] = None):
    try:
        promtail_path = _get_promtail_path(device_id)
        decoded = content.decode("utf-8", errors="replace")
        with open(promtail_path, "a", encoding="utf-8") as f:
            for raw_line in decoded.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue
                parsed = _parse_esp32_log_line(line)
                if parsed:
                    entry = {
                        "timestamp": parsed["ts"] or upload_time,
                        "device_id": device_id,
                        "level": parsed["level"],
                        "service": parsed["service"],
                        "test_id": parsed["test_id"],
                        "log_type": log_type or "unknown",
                        "message": parsed["message"],
                    }
                else:
                    entry = {
                        "timestamp": upload_time,
                        "device_id": device_id,
                        "level": "RAW",
                        "service": "",
                        "test_id": None,
                        "log_type": log_type or "unknown",
                        "message": line,
                    }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed to append to Promtail file for {device_id}: {e}")


def read_log_content(file_path: str, offset: int = 0, limit: int = 200) -> dict:
    storage = _get_storage_backend()

    if storage:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".log")
        try:
            tmp_path = tmp.name
            tmp.close()
            if not storage.download_file(file_path, tmp_path):
                raise Exception("Failed to download log from S3")
            with open(tmp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    total = len(lines)
    page = lines[offset:offset + limit]
    return {
        "lines": [line.rstrip("\n\r") for line in page],
        "total_lines": total,
        "offset": offset,
        "limit": limit,
    }
