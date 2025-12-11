from flask import request, jsonify, g
from routes.auth import verify_token

def authenticate(fn):
    def wrapper(*args, **kwargs):
        token = request.headers.get("Authorization")

        if not token:
            return jsonify({"error": "Authorization token required"}), 401

        if token.startswith("Bearer "):
            token = token.replace("Bearer ", "")

        user_id = verify_token(token)
        if not user_id:
            return jsonify({"error": "Invalid or expired token"}), 401

        g.user_id = user_id
        return fn(*args, **kwargs)

    wrapper.__name__ = fn.__name__
    return wrapper
