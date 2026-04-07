import queue
import secrets
from datetime import datetime

from flask import Blueprint, Response, g, jsonify, request, stream_with_context
from loguru import logger

from middleware.authenticate_esp32 import authenticate_esp32, authenticate_esp32_factory
from models.database import db
from models.test_models import ESP32Device
from utils.esp32_connection_manager import connection_manager
from utils.factory_key import validate_device_id_format, verify_factory_key

esp32_bp = Blueprint("esp32", __name__, url_prefix="/api/esp32")

# Heartbeat interval for SSE keep-alive (seconds)
SSE_HEARTBEAT_INTERVAL = 30
# Device considered offline after this many seconds without heartbeat
DEVICE_TIMEOUT_SECONDS = 60


@esp32_bp.route("/register", methods=["POST"])
@authenticate_esp32_factory
def register_device():
    """
    ESP32 registration endpoint.
    Verifies factory_key via HMAC, creates device if not exists.
    Returns production API key for future authentication.
    """
    data = request.get_json() or {}
    device_id = data.get("device_id")

    if not device_id:
        return jsonify({"error": "device_id is required"}), 400

    device_id = device_id.upper()

    if not validate_device_id_format(device_id):
        return (
            jsonify({"error": "Invalid device_id format. Expected: ESP32-XXXXXX"}),
            400,
        )

    if not verify_factory_key(device_id, g.factory_key):
        logger.error(f"Invalid Factory Key in X-Device-API-Key")
        return jsonify({"error": "Invalid factory key"}), 401

    # Look up existing device
    device = ESP32Device.query.filter_by(device_id=device_id).first()

    if device:
        if device.api_key:
            logger.info(f"ESP32 device re-registered: {device_id}")
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {
                            "device_id": device.device_id,
                            "api_key": device.api_key,
                        },
                    }
                ),
                200,
            )
    else:
        # Create new device
        logger.info(f"New ESP32 device registered: {device_id}")
        device = ESP32Device(
            device_id=device_id,
            factory_api_key=g.factory_key,
        )
        db.session.add(device)
        db.session.flush()  # Get device.id before generating key

    # Generate production API key (always regenerate to ensure uniqueness)
    production_key = f"sk_live_{secrets.token_urlsafe(32)}"
    device.api_key = production_key
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "device_id": device.device_id,
                    "api_key": production_key,
                },
            }
        ),
        200,
    )


@esp32_bp.route("/stream", methods=["GET"])
@authenticate_esp32
def stream():
    """
    SSE endpoint for ESP32 devices.
    ESP32 connects and listens for test_started events.
    Connection stays open until device disconnects.
    Uses detached device info to avoid holding DB connection.
    """
    device_info = g.esp32_device_info
    user_id = device_info["user_id"]
    device_id = device_info["id"]
    device_id_str = device_info["device_id"]

    logger.info(f"ESP32 stream connected: device={device_id_str} user={user_id}")

    # Create a message queue for this connection
    msg_queue = queue.Queue(maxsize=100)

    # Register connection
    connection_manager.add(user_id, device_id_str, msg_queue)

    # Update device status, then commit to release the connection back to pool
    device = db.session.get(ESP32Device, device_id)
    if device:
        device.is_connected = True
        device.last_seen_at = datetime.utcnow()
        db.session.commit()
    # Expire all to detach objects - connection is returned to pool after commit
    db.session.expire_all()

    def event_stream():
        try:
            yield format_sse(event="connected", data={"device_id": device_id_str})

            while True:
                try:
                    msg = msg_queue.get(timeout=SSE_HEARTBEAT_INTERVAL)
                    logger.info(
                        f"ESP32 event forwarded: '{msg['event']}' to device={device_id_str}"
                    )
                    yield format_sse(event=msg["event"], data=msg["data"])
                except queue.Empty:
                    yield format_sse(
                        event="heartbeat",
                        data={"timestamp": datetime.utcnow().isoformat()},
                    )
        except GeneratorExit:
            pass
        finally:
            logger.info(f"ESP32 stream disconnected: device={device_id_str}")
            connection_manager.remove(user_id)
            try:
                dev = db.session.get(ESP32Device, device_id)
                if dev:
                    dev.is_connected = False
                    db.session.commit()
            except Exception:
                db.session.rollback()
            finally:
                db.session.expire_all()

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
            # Cloudflare-specific: disable buffering
            "CF-Cache-Status": "DYNAMIC",
        },
    )


@esp32_bp.route("/heartbeat", methods=["POST"])
@authenticate_esp32
def heartbeat():
    """
    ESP32 heartbeat endpoint.
    Updates is_connected and last_seen_at.
    Uses fresh session to avoid holding connection.
    """
    device_info = g.esp32_device_info

    device = db.session.get(ESP32Device, device_info["id"])
    if device:
        device.is_connected = True
        device.last_seen_at = datetime.utcnow()
        db.session.commit()
    db.session.expire_all()

    logger.debug(f"ESP32 heartbeat received: device_id={device_info['device_id']}")

    return (
        jsonify(
            {
                "success": True,
                "message": "Heartbeat received",
            }
        ),
        200,
    )


def format_sse(event, data):
    """Format data as SSE event string."""
    import json

    if isinstance(data, dict):
        data = json.dumps(data)
    return f"event: {event}\ndata: {data}\n\n"
