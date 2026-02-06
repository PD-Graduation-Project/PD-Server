from flask import Blueprint, g, jsonify, request

from middleware.authenticate import authenticate
from models.database import db
from models.user import User

questionnaire_bp = Blueprint("questionnaire", __name__, url_prefix="/api/questionnaire")

QUESTION_IDS = [f"Q{i:02d}" for i in range(1, 29)]


@questionnaire_bp.route("/", methods=["GET"])
@authenticate
def get_questionnaire():
    """Get all responses"""
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404
    responses = {qid: getattr(current_user, qid) for qid in QUESTION_IDS}
    return jsonify({"success": True, "data": responses}), 200


@questionnaire_bp.route("/", methods=["PATCH"])
@authenticate
def patch_questionnaire():
    """
    Partial update
    Can handle single question or multiple questions.
    Body: { "Q01": true, "Q05": false }
    """
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data"}), 400

        updated_fields = []

        for key, value in data.items():
            if key in QUESTION_IDS:
                if value is not None and not isinstance(value, bool):
                    return (
                        jsonify({"success": False, "error": f"{key} must be boolean"}),
                        400,
                    )
                setattr(current_user, key, value)
                updated_fields.append(key)

        if not updated_fields:
            return jsonify({"success": False, "error": "No valid fields provided"}), 400

        db.session.commit()
        return jsonify({"success": True, "updated": updated_fields}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
