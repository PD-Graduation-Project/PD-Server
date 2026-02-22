import queue
import secrets
from datetime import datetime

from flask import Blueprint, Response, g, jsonify, request, stream_with_context

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
        return jsonify({"error": "Invalid factory key"}), 401

    # Look up existing device
    device = ESP32Device.query.filter_by(device_id=device_id).first()

    if device:
        if device.api_key:
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
        device = ESP32Device(
            device_id=device_id,
            factory_api_key=g.factory_key,
        )
        db.session.add(device)

    # Generate production API key
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
    """
    device = g.esp32_device
    user_id = device.user_id

    # Create a message queue for this connection
    msg_queue = queue.Queue(maxsize=100)

    # Register connection
    connection_manager.add(user_id, device.device_id, msg_queue)

    # Update device status
    device.is_connected = True
    device.last_seen_at = datetime.utcnow()
    db.session.commit()

    # Store device_id for cleanup (avoid referencing ORM object in generator)
    device_id = device.id

    def event_stream():
        try:
            # Send initial connected event
            yield format_sse(event="connected", data={"device_id": device.device_id})

            while True:
                try:
                    # Wait for messages with timeout for keep-alive
                    msg = msg_queue.get(timeout=SSE_HEARTBEAT_INTERVAL)
                    yield format_sse(event=msg["event"], data=msg["data"])
                except queue.Empty:
                    # Send heartbeat to keep connection alive
                    yield format_sse(
                        event="heartbeat",
                        data={"timestamp": datetime.utcnow().isoformat()},
                    )
        except GeneratorExit:
            pass
        finally:
            # Cleanup on disconnect
            connection_manager.remove(user_id)
            try:
                dev = db.session.get(ESP32Device, device_id)
                if dev:
                    dev.is_connected = False
                    db.session.commit()
            except Exception:
                pass

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@esp32_bp.route("/heartbeat", methods=["POST"])
@authenticate_esp32
def heartbeat():
    """
    ESP32 heartbeat endpoint.
    Updates is_connected and last_seen_at.
    """
    device = g.esp32_device
    device.is_connected = True
    device.last_seen_at = datetime.utcnow()
    db.session.commit()

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
