import datetime
import secrets
import uuid

import jwt
from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from models.database import db
from models.user import RefreshToken, User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

ACCESS_TOKEN_EXPIRY = datetime.timedelta(minutes=15)
REFRESH_TOKEN_EXPIRY = datetime.timedelta(days=30)


def generate_access_token(user_id):
    """Generate a short-lived access token"""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "user_id": user_id,
        "type": "access",
        "exp": now + ACCESS_TOKEN_EXPIRY,
        "iat": now,  # initilization time
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)


def generate_refresh_token(user_id, device_info=None, ip_address=None):
    """Generate a long-lived access token and store it in database"""

    # generate a crypto random token and hash it for storage
    token = secrets.token_urlsafe(64)
    token_hash = generate_password_hash(token)

    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.datetime.utcnow() + REFRESH_TOKEN_EXPIRY,
        device_info=device_info,
        ip_address=ip_address,
    )

    db.session.add(refresh_token)
    db.session.commit()

    return token


def verify_access_token(token):
    """Verify and decode access token"""
    try:
        payload = jwt.decode(
            token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM]
        )

        # Ensure it's an access token
        if payload.get("type") != "access":
            return None

        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def verify_refresh_token(token):
    """Verify refresh token against database"""
    try:
        # Query all non-revoked, non-expired refresh tokens
        valid_tokens = RefreshToken.query.filter(
            RefreshToken.revoked is False,
            RefreshToken.expires_at > datetime.datetime.utcnow(),
        ).all()

        # Check if provided token matches any stored token
        for db_token in valid_tokens:
            if check_password_hash(db_token.token_hash, token):
                return db_token.user_id, db_token

        return None, None
    except Exception as e:
        print(f"Error verifying refresh token: {e}")
        return None, None


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user and return access"""
    data = request.get_json()

    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password required"}), 400

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

    return (
        jsonify(
            {
                "message": "User registered successfully",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": int(ACCESS_TOKEN_EXPIRY.total_seconds()),
                "user": user.to_dict(),
            }
        ),
        201,
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=data["email"]).first()

    if not user or not user.check_password(data["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    # Generate both tokens
    access_token = generate_access_token(user.id)
    refresh_token = generate_refresh_token(
        user.id,
        device_info=request.headers.get("User-Agent"),
        ip_address=request.remote_addr,
    )

    return (
        jsonify(
            {
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": int(ACCESS_TOKEN_EXPIRY.total_seconds()),
                "user": user.to_dict(),
            }
        ),
        200,
    )


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """
    Use refresh token to get a new access token
    Request body should contain: { "refresh_token": "..." }
    """
    data = request.get_json()

    if not data or not data.get("refresh_token"):
        return jsonify({"error": "Refresh token required"}), 400

    refresh_token = data["refresh_token"]

    # Verify refresh token
    user_id, db_token = verify_refresh_token(refresh_token)

    if not user_id:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    # Generate new access token
    access_token = generate_access_token(user_id)

    # Optionally rotate refresh token
    # For now, we'll keep the same refresh token

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
def logout():
    """
    Logout user by revoking their refresh token
    Request body should contain: { "refresh_token": "..." }
    """
    data = request.get_json()

    if not data or not data.get("refresh_token"):
        return jsonify({"error": "Refresh token required"}), 400

    refresh_token = data["refresh_token"]

    # Verify and revoke refresh token
    user_id, db_token = verify_refresh_token(refresh_token)

    if db_token:
        db_token.revoked = True
        db.session.commit()
        return jsonify({"message": "Logged out successfully"}), 200

    return jsonify({"error": "Invalid refresh token"}), 401


@auth_bp.route("/logout-all", methods=["POST"])
def logout_all():
    """
    Logout from all devices by revoking all refresh tokens for the user
    Requires valid access token in Authorization header
    """
    # Get access token from header
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Access token required"}), 401

    access_token = auth_header.replace("Bearer ", "")
    user_id = verify_access_token(access_token)

    if not user_id:
        return jsonify({"error": "Invalid or expired access token"}), 401

    # Revoke all refresh tokens for this user
    RefreshToken.query.filter_by(user_id=user_id, revoked=False).update(
        {"revoked": True}
    )
    db.session.commit()

    return jsonify({"message": "Logged out from all devices successfully"}), 200


@auth_bp.route("/sessions", methods=["GET"])
def get_sessions():
    """
    Get all active sessions (refresh tokens) for the current user
    Requires valid access token in Authorization header
    """
    # Get access token from header
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Access token required"}), 401

    access_token = auth_header.replace("Bearer ", "")
    user_id = verify_access_token(access_token)

    if not user_id:
        return jsonify({"error": "Invalid or expired access token"}), 401

    # Get all active refresh tokens
    sessions = (
        RefreshToken.query.filter_by(user_id=user_id, revoked=False)
        .filter(RefreshToken.expires_at > datetime.datetime.utcnow())
        .all()
    )

    return (
        jsonify(
            {
                "sessions": [
                    {
                        "id": session.id,
                        "device_info": session.device_info,
                        "ip_address": session.ip_address,
                        "created_at": (
                            session.created_at.isoformat()
                            if session.created_at
                            else None
                        ),
                        "expires_at": (
                            session.expires_at.isoformat()
                            if session.expires_at
                            else None
                        ),
                    }
                    for session in sessions
                ]
            }
        ),
        200,
    )
