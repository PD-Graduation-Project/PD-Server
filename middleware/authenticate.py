from flask import g, jsonify, request

from utils.token import verify_access_token


def authenticate(fn):
    """
    Middleware to authenticate requests using access tokens
    Expects Authorization header: Bearer <access_token>
    Sets g.user_id if authentication is successful
    """

    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "Authorization token required"}), 401

        # Extract token from "Bearer <token>" format
        if not auth_header.startswith("Bearer "):
            return (
                jsonify(
                    {
                        "error": "Invalid authorization header format. Use: Bearer <token>"
                    }
                ),
                401,
            )

        token = auth_header.replace("Bearer ", "")

        # Verify access token
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

        # Store user_id in Flask's g object for use in the route handler
        g.user_id = user_id

        return fn(*args, **kwargs)

    wrapper.__name__ = fn.__name__
    return wrapper
