from functools import wraps

from flask import g, jsonify, request

from models.test_models import ESP32Device


def authenticate_esp32_factory(fn):
    """
    Middleware for /esp32/register endpoint.
    Extracts factory key from header and stores in g.factory_key.
    HMAC verification happens in the route (needs device_id from body).
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        factory_key = request.headers.get("X-Device-API-Key")

        if not factory_key:
            return jsonify({"error": "X-Device-API-Key header required"}), 401

        if not factory_key.startswith("fk_"):
            return jsonify({"error": "Invalid factory key format"}), 401

        g.factory_key = factory_key

        return fn(*args, **kwargs)

    return wrapper


def authenticate_esp32(fn):
    """
    Middleware to authenticate ESP32 requests using production API key.
    Used for /esp32/stream, /esp32/heartbeat, and upload routes.
    Sets g.esp32_device and g.user_id if authentication is successful.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get("X-Device-API-Key")

        if not api_key:
            return jsonify({"error": "X-Device-API-Key header required"}), 401

        device = ESP32Device.query.filter_by(api_key=api_key).first()

        if not device:
            return jsonify({"error": "Invalid API key"}), 401

        if not device.user_id:
            return jsonify({"error": "Device not paired to any user"}), 403

        g.esp32_device = device
        g.user_id = device.user_id

        return fn(*args, **kwargs)

    return wrapper


def authenticate_jwt_or_esp32(fn):
    """
    Middleware that accepts either JWT Bearer token or ESP32 API key.
    Used for routes that both mobile app and ESP32 can access
    (e.g., /tests/{id}/tremor, /tests/{id}/complete).
    Sets g.user_id in both cases.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get("X-Device-API-Key")
        auth_header = request.headers.get("Authorization")

        # Try ESP32 API key first
        if api_key:
            device = ESP32Device.query.filter_by(api_key=api_key).first()

            if not device:
                return jsonify({"error": "Invalid API key"}), 401

            if not device.user_id:
                return jsonify({"error": "Device not paired to any user"}), 403

            g.esp32_device = device
            g.user_id = device.user_id

            return fn(*args, **kwargs)

        # Fall back to JWT
        if auth_header:
            if not auth_header.startswith("Bearer "):
                return (
                    jsonify(
                        {
                            "error": "Invalid authorization header format. Use: Bearer <token>"
                        }
                    ),
                    401,
                )

            from utils.token import verify_access_token

            token = auth_header.replace("Bearer ", "")
            user_id = verify_access_token(token)

            if not user_id:
                return (
                    jsonify(
                        {
                            "error": "Invalid or expired access token",
                            "message": "Please refresh your access token using the /api/auth/refresh endpoint",
                        }
                    ),
                    401,
                )

            g.user_id = user_id

            return fn(*args, **kwargs)

        return (
            jsonify(
                {"error": "Authorization required (Bearer token or X-Device-API-Key)"}
            ),
            401,
        )

    return wrapper
