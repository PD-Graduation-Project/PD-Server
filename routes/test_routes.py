import logging
from typing import Any, cast

from flask import Blueprint, g, jsonify, request
from sqlalchemy.orm import selectinload

from middleware.authenticate import authenticate
from models.database import db
from models.test_models import TestSession
from models.user import User
from schemas.test_schema import CreateTestSchema, TestListQuerySchema, TestSessionSchema
from utils.esp32_connection_manager import connection_manager
from utils.validation import get_json_body, get_query_params

test_bp = Blueprint("test", __name__, url_prefix="/api/tests")
logger = logging.getLogger(__name__)


@test_bp.route("", methods=["POST"])
@authenticate
def create_test():
    schema = CreateTestSchema()
    raw_body, error = get_json_body(request)
    if error:
        return error
    assert raw_body is not None

    try:
        data = cast(dict[str, Any], schema.load(raw_body))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    test_type = data["test_type"]
    config = data.get("config", {})
    device = data.get("device")

    if device:
        device_source = device
    else:
        device_source = "esp32" if test_type == "tremor" else "mobile"

    test_session = TestSession(
        user_id=current_user.id,
        test_type=test_type,
        status="pending",
        device_source=device_source,
        config=config,
    )

    db.session.add(test_session)
    db.session.commit()

    # If tremor test with ESP32, send SSE event to paired device
    if test_type == "tremor" and device_source == "esp32":
        logger.info(
            f"[TEST ROUTE] Sending test_started event for test {test_session.id} to user {current_user.id}"
        )
        success = connection_manager.send_event(
            current_user.id,
            "test_started",
            {
                "test_id": test_session.id,
                "test_type": test_type,
                "config": config,
            },
        )
        if success:
            logger.info(
                f"[TEST ROUTE] test_started event sent successfully to user {current_user.id}"
            )
        else:
            logger.warning(
                f"[TEST ROUTE] Failed to send test_started event to user {current_user.id}"
            )

    return (
        jsonify(
            {
                "success": True,
                "data": TestSessionSchema().dump(test_session),
            }
        ),
        201,
    )


@test_bp.route("", methods=["GET"])
@authenticate
def list_tests():
    schema = TestListQuerySchema()
    try:
        params = cast(dict[str, Any], schema.load(get_query_params(request)))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    query = TestSession.query.filter_by(user_id=current_user.id).options(
        selectinload(TestSession.inputs)  # type: ignore[arg-type]
    )

    if params.get("test_type"):
        query = query.filter_by(test_type=params["test_type"])

    if params.get("status"):
        query = query.filter_by(status=params["status"])

    total = query.count()
    page = params.get("page", 1)
    per_page = params.get("per_page", 20)

    tests = (
        query.order_by(TestSession.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    pages = (total + per_page - 1) // per_page

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "tests": TestSessionSchema(many=True).dump(tests),
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "pages": pages,
                },
            }
        ),
        200,
    )


@test_bp.route("/<int:test_id>", methods=["GET"])
@authenticate
def get_test(test_id):
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    test_session = db.session.get(TestSession, test_id)

    if not test_session:
        return jsonify({"error": "Test not found"}), 404

    if test_session.user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    return (
        jsonify(
            {
                "success": True,
                "data": TestSessionSchema().dump(test_session),
            }
        ),
        200,
    )
