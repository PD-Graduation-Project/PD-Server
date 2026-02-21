import queue
import secrets
from datetime import datetime

from flask import Blueprint, Response, g, jsonify, stream_with_context

from middleware.authenticate_esp32 import authenticate_esp32, authenticate_esp32_factory
from models.database import db
from models.test_models import ESP32Device
from utils.esp32_connection_manager import connection_manager

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
    ESP32 calls this on first boot with factory API key and sends device_id in body.
    Returns a production API key for future authentication.
    """
    from flask import request

    data = request.get_json() or {}
    device_id = data.get("device_id")

    if not device_id:
        return jsonify({"error": "device_id is required in body"}), 400

    device = g.esp32_device

    if device.device_id and device.device_id != device_id:
        return jsonify({"error": "Device ID mismatch"}), 400

    device.device_id = device_id

    if device.api_key:
        db.session.commit()
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
                    "api_key": production_key,  # Should be saved inside the flash of the esp32
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
