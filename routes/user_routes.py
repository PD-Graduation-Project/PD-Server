from typing import Any, cast

from flask import Blueprint, g, jsonify, request

from middleware.authenticate import authenticate
from models.database import db
from models.user import User
from schemas.user_schema import UserDemographicsSchema
from utils.validation import get_json_body

user_bp = Blueprint("user", __name__, url_prefix="/api/user")


@user_bp.route("/", methods=["GET"])
@authenticate
def get_user():
    """Get current user's information"""
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404
    return (
        jsonify({"success": True, "data": UserDemographicsSchema().dump(current_user)}),
        200,
    )


@user_bp.route("/", methods=["PATCH"])
@authenticate
def update_user():
    """Update user demographics"""
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    schema = UserDemographicsSchema()
    raw_body, error = get_json_body(request)
    if error:
        return error
    assert raw_body is not None

    try:
        data = cast(dict[str, Any], schema.load(raw_body))
    except Exception as e:
        return (
            jsonify(
                {"success": False, "error": "Validation failed", "message": str(e)}
            ),
            400,
        )

    for key, value in data.items():
        setattr(current_user, key, value)

    db.session.commit()

    return jsonify({"success": True, "data": schema.dump(current_user)}), 200


@user_bp.route("/reset", methods=["POST"])
@authenticate
def reset_user_data():
    """Reset user data (replaces DELETE /data for semantic clarity)"""
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404
    try:
        current_user.age = None
        current_user.height = None
        current_user.weight = None
        current_user.gender = None
        current_user.pd_appearance_in_kinship = None
        current_user.pd_appearance_in_first_grade_kinship = None

        db.session.commit()
        return jsonify({"success": True, "message": "User data reset"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@user_bp.route("/", methods=["DELETE"])
@authenticate
def delete_user():
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404
    try:
        db.session.delete(current_user)
        db.session.commit()
        return jsonify({"success": True, "message": "Account deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@user_bp.route("/push-token", methods=["POST"])
@authenticate
def add_push_token():
    """Register Expo push token for the current user.

    Body: { "push_token": "ExponentPushToken-xxx" }
    """
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    raw_body, error = get_json_body(request)
    if error:
        return error
    assert raw_body is not None

    push_token = raw_body.get("push_token")
    if not push_token:
        return jsonify({"error": "push_token is required"}), 400

    if not isinstance(push_token, str):
        return jsonify({"error": "push_token must be a string"}), 400

    current_tokens = current_user.push_token or []

    if push_token not in current_tokens:
        new_tokens = current_tokens + [push_token]
        current_user.push_token = new_tokens
        db.session.commit()

    return jsonify({"success": True}), 200


@user_bp.route("/push-token", methods=["DELETE"])
@authenticate
def remove_push_token():
    """Remove Expo push token from the current user.

    Body: { "push_token": "ExponentPushToken-xxx" }
    """
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    raw_body, error = get_json_body(request)
    if error:
        return error
    assert raw_body is not None

    push_token = raw_body.get("push_token")
    if not push_token:
        return jsonify({"error": "push_token is required"}), 400

    current_tokens = current_user.push_token or []
    if push_token in current_tokens:
        new_tokens = [t for t in current_tokens if t != push_token]
        current_user.push_token = new_tokens if new_tokens else None
        db.session.commit()

    return jsonify({"success": True}), 200
# test reload
