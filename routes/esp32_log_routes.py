from flask import Blueprint, g, jsonify, request
from loguru import logger

from middleware.authenticate import authenticate
from middleware.authenticate_esp32 import authenticate_esp32
from models.database import db
from models.test_models import ESP32Device, ESP32Log
from utils.log_storage import (
    is_allowed_log_file,
    read_log_content,
    save_log_file,
)
from utils.storage import get_expires_at

esp32_log_bp = Blueprint("esp32_log", __name__, url_prefix="/api/esp32/logs")


@esp32_log_bp.route("", methods=["POST"])
@authenticate_esp32
def upload_log():
    device_info = g.esp32_device_info
    device_id = device_info["device_id"]

    if "file" in request.files:
        file = request.files["file"]
        filename = file.filename or "upload.log"
        logger.info(f"ESP32 upload: multipart branch, filename={filename}")
    elif request.content_type == "application/octet-stream":
        raw = request.stream.read()
        logger.info(f"ESP32 upload: octet-stream branch, len={len(raw) if raw else 0}")
        if not raw:
            return jsonify({"error": "No file provided"}), 400
        from io import BytesIO
        from werkzeug.datastructures import FileStorage
        file = FileStorage(stream=BytesIO(raw), filename="upload.log", content_type="application/octet-stream")
        filename = "upload.log"
    else:
        logger.info(f"ESP32 upload: no-match branch, content_type={request.content_type}")
        return jsonify({"error": "No file provided"}), 400

    if not is_allowed_log_file(filename):
        return jsonify({"error": "Invalid file type. Only .log, .txt, .json, and .jsonl files allowed"}), 400

    log_type = request.form.get("log_type") or "unknown"

    try:
        file_path, file_size = save_log_file(file, device_id, filename, log_type)
    except Exception as e:
        logger.error(f"Log upload failed for device {device_id}: {e}")
        return jsonify({"error": "Failed to save log file"}), 500

    log_entry = ESP32Log(
        device_id=device_id,
        file_path=file_path,
        original_filename=filename,
        file_size=file_size,
        log_type=log_type,
        expires_at=get_expires_at(),
    )
    db.session.add(log_entry)
    db.session.commit()

    logger.info(f"ESP32 log uploaded: device={device_id} file={filename} size={file_size} type={log_type}")

    return (
        jsonify({
            "success": True,
            "data": {
                "id": log_entry.id,
                "file_size": file_size,
                "log_type": log_type,
            },
        }),
        201,
    )


@esp32_log_bp.route("", methods=["GET"])
@authenticate
def list_logs():
    device_id = request.args.get("device_id")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    if not device_id:
        return jsonify({"error": "device_id query parameter is required"}), 400

    device = ESP32Device.query.filter_by(device_id=device_id).first()
    if not device or device.user_id != g.user_id:
        return jsonify({"error": "Device not found"}), 404

    query = ESP32Log.query.filter_by(device_id=device_id).order_by(ESP32Log.uploaded_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return (
        jsonify({
            "success": True,
            "data": {
                "logs": [
                    {
                        "id": log.id,
                        "original_filename": log.original_filename,
                        "file_size": log.file_size,
                        "log_type": log.log_type,
                        "uploaded_at": log.uploaded_at.isoformat() if log.uploaded_at else None,
                    }
                    for log in pagination.items
                ],
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
            },
        }),
        200,
    )


@esp32_log_bp.route("/<int:log_id>/view", methods=["GET"])
@authenticate
def view_log(log_id):
    offset = max(0, request.args.get("offset", 0, type=int))
    limit = request.args.get("limit", 200, type=int)
    limit = min(limit, 1000)

    log_entry = db.session.get(ESP32Log, log_id)
    if not log_entry:
        return jsonify({"error": "Log not found"}), 404

    device = ESP32Device.query.filter_by(device_id=log_entry.device_id).first()
    if not device or device.user_id != g.user_id:
        return jsonify({"error": "Log not found"}), 404

    try:
        content = read_log_content(log_entry.file_path, offset=offset, limit=limit)
    except Exception as e:
        logger.error(f"Failed to read log {log_id}: {e}")
        return jsonify({"error": "Failed to read log content"}), 500

    return (
        jsonify({
            "success": True,
            "data": {
                "id": log_entry.id,
                "original_filename": log_entry.original_filename,
                "file_size": log_entry.file_size,
                "log_type": log_entry.log_type,
                "uploaded_at": log_entry.uploaded_at.isoformat() if log_entry.uploaded_at else None,
                **content,
            },
        }),
        200,
    )
