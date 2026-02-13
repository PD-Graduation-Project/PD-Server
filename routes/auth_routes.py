import datetime
import secrets
from datetime import timezone
from typing import Any, cast

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from middleware.authenticate import authenticate
from models.database import db
from models.user import RefreshToken, User
from schemas.auth_schema import (
    LoginSchema,
    RefreshSchema,
    RegisterSchema,
    SessionSchema,
)
from utils.token import generate_access_token
from utils.validation import get_json_body

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ACCESS_TOKEN_EXPIRY = datetime.timedelta(minutes=15)
REFRESH_TOKEN_EXPIRY = datetime.timedelta(days=30)


def _generate_auth_response(user, access_token, refresh_token, status_code=200):
    """Helper to avoid duplicating JSON response logic"""
    return (
        jsonify(
            {
                "message": "Success",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": int(ACCESS_TOKEN_EXPIRY.total_seconds()),
                "user": user.to_dict(),
            }
        ),
        status_code,
    )


def generate_refresh_token(user_id, device_info=None, ip_address=None):
    token = secrets.token_urlsafe(64)
    token_hash = generate_password_hash(token)

    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.datetime.now(timezone.utc) + REFRESH_TOKEN_EXPIRY,
        device_info=device_info,
        ip_address=ip_address,
    )

    db.session.add(refresh_token)
    db.session.commit()
    return token


def verify_refresh_token(token, user_id):
    """
    Optimized: Only queries tokens for the specific user_id.
    """
    try:
        # Only fetch tokens for THIS user that are still valid
        valid_tokens = RefreshToken.query.filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
            RefreshToken.expires_at > datetime.datetime.now(timezone.utc),
        ).all()

        for db_token in valid_tokens:
            if check_password_hash(db_token.token_hash, token):
                return db_token  # Return the whole token object
        return None
    except Exception as e:
        print(f"Error verifying refresh token: {e}")
        return None


@auth_bp.route("/register", methods=["POST"])
def register():
    schema = RegisterSchema()
    raw_body, error = get_json_body(request)
    if error:
        return error
    assert raw_body is not None

    try:
        data = cast(dict[str, Any], schema.load(raw_body))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    access_token = generate_access_token(user.id)
    refresh_token = generate_refresh_token(
        user.id,
        ip_address=request.remote_addr,
        device_info=request.headers.get("User-Agent"),
    )

    return _generate_auth_response(user, access_token, refresh_token, status_code=201)


@auth_bp.route("/login", methods=["POST"])
def login():
    schema = LoginSchema()
    raw_body, error = get_json_body(request)
    if error:
        return error
    assert raw_body is not None

    try:
        data = cast(dict[str, Any], schema.load(raw_body))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    user = User.query.filter_by(email=data["email"]).first()

    if not user or not user.check_password(data["password"]):
        # Use generic message for security
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = generate_access_token(user.id)
    refresh_token = generate_refresh_token(
        user.id,
        device_info=request.headers.get("User-Agent"),
        ip_address=request.remote_addr,
    )

    return _generate_auth_response(user, access_token, refresh_token, status_code=200)


@auth_bp.route("/refresh", methods=["POST"])
@authenticate
def refresh():
    schema = RefreshSchema()
    raw_body, error = get_json_body(request)
    if error:
        return error
    assert raw_body is not None

    try:
        data = cast(dict[str, Any], schema.load(raw_body))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # We pass g.user_id to optimize the query
    db_token = verify_refresh_token(data["refresh_token"], g.user_id)

    if not db_token:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    # Generate new access token
    access_token = generate_access_token(g.user_id)

    return (
        jsonify(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": int(ACCESS_TOKEN_EXPIRY.total_seconds()),
            }
        ),
        200,
    )


@auth_bp.route("/logout", methods=["POST"])
@authenticate
def logout():
    schema = RefreshSchema()
    raw_body, error = get_json_body(request)
    if error:
        return error
    assert raw_body is not None

    try:
        data = cast(dict[str, Any], schema.load(raw_body))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # We pass g.user_id to optimize the query
    db_token = verify_refresh_token(data["refresh_token"], g.user_id)

    if db_token:
        db_token.revoked = True
        db.session.commit()
        return jsonify({"message": "Logged out successfully"}), 200

    return jsonify({"error": "Invalid refresh token"}), 401


@auth_bp.route("/logout-all", methods=["POST"])
@authenticate
def logout_all():
    RefreshToken.query.filter_by(user_id=g.user_id, revoked=False).update(
        {"revoked": True}
    )
    db.session.commit()
    return jsonify({"message": "Logged out from all devices"}), 200


@auth_bp.route("/sessions", methods=["GET"])
@authenticate
def get_sessions():
    sessions = (
        RefreshToken.query.filter_by(user_id=g.user_id, revoked=False)
        .filter(RefreshToken.expires_at > datetime.datetime.now(timezone.utc))
        .all()
    )

    # Use Schema to dump the list (cleaner than list comprehension)
    return jsonify({"sessions": SessionSchema(many=True).dump(sessions)}), 200
