from typing import Any, cast

from flask import Blueprint, g, jsonify, request
from sqlalchemy.orm import selectinload

from middleware.authenticate import authenticate
from models.database import db
from models.test_models import TestGroup
from schemas.group_schema import GroupListQuerySchema, GroupSchema
from utils.validation import get_query_params

group_bp = Blueprint("groups", __name__, url_prefix="/api/groups")


@group_bp.route("", methods=["POST"])
@authenticate
def create_group():
    """
    Create a new test group.
    The mobile app calls this first, then uses the returned group_id
    when creating each of the three test sessions (tremor, drawing, voice).
    """
    # No required fields in the body — just create the group for the current user.
    group = TestGroup(user_id=g.user_id, status="pending")
    db.session.add(group)
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "data": GroupSchema().dump(group),
            }
        ),
        201,
    )


@group_bp.route("", methods=["GET"])
@authenticate
def list_groups():
    """
    List all test groups for the current user with optional status filter
    and pagination.
    """
    schema = GroupListQuerySchema()
    try:
        params = cast(dict[str, Any], schema.load(get_query_params(request)))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

    query = TestGroup.query.filter_by(user_id=g.user_id).options(
        selectinload(TestGroup.tests)
    )  # type: ignore[arg-type]

    if params.get("status"):
        query = query.filter_by(status=params["status"])

    total = query.count()
    page = params.get("page", 1)
    per_page = params.get("per_page", 20)

    groups = (
        query.order_by(TestGroup.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "groups": GroupSchema(many=True).dump(groups),
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                    "pages": pages,
                },
            }
        ),
        200,
    )


@group_bp.route("/<int:group_id>", methods=["GET"])
@authenticate
def get_group(group_id):
    """
    Get a single test group by ID, including all linked test sessions
    and their inputs.
    """
    group = (
        TestGroup.query.options(selectinload(TestGroup.tests))  # type: ignore[arg-type]
        .filter_by(id=group_id)
        .first()
    )

    if not group:
        return jsonify({"error": "Group not found"}), 404

    if group.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403

    return (
        jsonify(
            {
                "success": True,
                "data": GroupSchema().dump(group),
            }
        ),
        200,
    )
