from flask import Blueprint, g, jsonify, request

from middleware.authenticate import authenticate
from models.database import db
from models.user import User
from schemas.user_schema import UserDemographicsSchema

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
    try:
        schema = UserDemographicsSchema()
        data = schema.load(request.get_json())  # validate request data

        for key, value in data.items():
            setattr(current_user, key, value)

        db.session.commit()

        return jsonify({"success": True, "data": schema.dump(current_user)}), 200

    except Exception as e:
        return (
            jsonify(
                {"success": False, "error": "Validation failed", "message": str(e)}
            ),
            400,
        )


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
