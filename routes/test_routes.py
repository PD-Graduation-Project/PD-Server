from typing import Any, cast

from flask import Blueprint, g, jsonify, request
from sqlalchemy.orm import selectinload

from middleware.authenticate import authenticate
from models.database import db
from models.test_models import TestGroup, TestSession
from schemas.test_schema import CreateTestSchema, TestListQuerySchema, TestSessionSchema
from utils.validation import get_json_body, get_query_params

test_bp = Blueprint("test", __name__, url_prefix="/api/tests")


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

    # Validate group ownership
    group = db.session.get(TestGroup, data["group_id"])
    if not group:
        return jsonify({"error": "Group not found"}), 404
    if group.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403
    if group.status == "completed":
        return jsonify({"error": "Group is already completed"}), 409

    test_type = data["test_type"]
    config = data.get("config", {})
    device = data.get("device")

    # Prevent duplicate test types within the same group
    existing_types = {t.test_type for t in group.tests}  # type: ignore[union-attr]
    if test_type in existing_types:
        return (
            jsonify(
                {
                    "error": f"A {test_type} test already exists in this group",
                }
            ),
            409,
        )

    if device:
        device_source = device
    else:
        device_source = "esp32" if test_type == "tremor" else "mobile"

    test_session = TestSession(
        user_id=g.user_id,
        group_id=group.id,
        test_type=test_type,
        status="pending",
        device_source=device_source,
        config=config,
    )

    db.session.add(test_session)

    # Advance group to in_progress on first test added
    if group.status == "pending":
        group.status = "in_progress"

    db.session.commit()

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

    query = TestSession.query.filter_by(user_id=g.user_id).options(
        selectinload(TestSession.inputs)  # type: ignore[arg-type]
    )

    if params.get("test_type"):
        query = query.filter_by(test_type=params["test_type"])

    if params.get("status"):
        query = query.filter_by(status=params["status"])

    if params.get("group_id"):
        query = query.filter_by(group_id=params["group_id"])

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
    test_session = db.session.get(TestSession, test_id)

    if not test_session:
        return jsonify({"error": "Test not found"}), 404

    if test_session.user_id != g.user_id:
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
