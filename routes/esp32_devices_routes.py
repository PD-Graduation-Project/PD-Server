from flask import Blueprint, g, jsonify, request

from middleware.authenticate import authenticate
from models.database import db
from models.test_models import ESP32Device

esp32_devices_bp = Blueprint("esp32_devices", __name__, url_prefix="/api/esp32-devices")


@esp32_devices_bp.route("/pair", methods=["POST"])
@authenticate
def pair_device():
    """
    Pair an ESP32 device to the current user.
    User provides device_id (from sticker on ESP32).
    """
    data = request.get_json()

    if not data or not data.get("device_id"):
        return jsonify({"error": "device_id is required"}), 400

    device_id = data["device_id"].strip()
    name = data.get("name", "").strip() or device_id

    # Look up device by device_id
    device = ESP32Device.query.filter_by(device_id=device_id).first()

    if not device:
        return (
            jsonify({"error": "Device not found. Check the device ID and try again"}),
            404,
        )

    # Check if device is already paired to another user
    if device.user_id and device.user_id != g.user_id:
        return jsonify({"error": "Device is already paired to another user"}), 409

    # Check if already paired to this user
    if device.user_id == g.user_id:
        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "id": device.id,
                        "device_id": device.device_id,
                        "name": device.name,
                        "is_connected": device.is_connected,
                        "created_at": (
                            device.created_at.isoformat() if device.created_at else None
                        ),
                    },
                    "message": "Device is already paired to your account",
                }
            ),
            200,
        )

    # Pair device to user
    device.user_id = g.user_id
    device.name = name
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "id": device.id,
                    "device_id": device.device_id,
                    "name": device.name,
                    "is_connected": device.is_connected,
                    "created_at": (
                        device.created_at.isoformat() if device.created_at else None
                    ),
                },
            }
        ),
        200,
    )


@esp32_devices_bp.route("", methods=["GET"])
@authenticate
def list_devices():
    """List all ESP32 devices paired to the current user."""
    devices = ESP32Device.query.filter_by(user_id=g.user_id).all()

    return (
        jsonify(
            {
                "success": True,
                "data": [
                    {
                        "id": d.id,
                        "device_id": d.device_id,
                        "name": d.name,
                        "is_connected": d.is_connected,
                        "last_seen_at": (
                            d.last_seen_at.isoformat() if d.last_seen_at else None
                        ),
                        "created_at": (
                            d.created_at.isoformat() if d.created_at else None
                        ),
                    }
                    for d in devices
                ],
            }
        ),
        200,
    )


@esp32_devices_bp.route("/<string:device_id>", methods=["DELETE"])
@authenticate
def unpair_device(device_id):
    """Unpair an ESP32 device from the current user."""
    device = ESP32Device.query.filter_by(device_id=device_id).first()

    if not device:
        return jsonify({"error": "Device not found"}), 404

    if device.user_id != g.user_id:
        return jsonify({"error": "Device not found"}), 404

    # Unpair: set user_id to None, clear name
    device.user_id = None
    device.name = None
    device.is_connected = False
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "message": "Device unpaired successfully",
            }
        ),
        200,
    )
