"""General test routes for history and results."""
from flask import request, jsonify, g
from models.database import db
from models.test_result import TestResult
from . import tests_bp
from middleware.authenticate import authenticate
from .utils import calculate_progress, get_test_status


@tests_bp.route("/", methods=["POST"])
@authenticate
def start_test():
    """Create a new test record and return its ID."""
    # Check if user already has an incomplete test
    existing_test = TestResult.query.filter_by(
        user_id=g.user_id, completed_at=None
    ).first()

    if existing_test:
        return jsonify(
            {
                "message": "Existing test found",
                "test_id": existing_test.id,
                "test": existing_test.to_dict(),
            }
        ), 200

    # Create new test record
    test = TestResult(user_id=g.user_id)
    db.session.add(test)
    db.session.commit()

    return jsonify(
        {
            "message": "Test started successfully",
            "test_id": test.id,
            "test": test.to_dict(),
        }
    ), 201


@tests_bp.route("/<int:test_id>", methods=["GET"])
@authenticate
def get_test_result(test_id):
    """Get a specific test result by ID."""
    test = TestResult.query.filter_by(id=test_id, user_id=g.user_id).first()

    if not test:
        return jsonify({"error": "Test not found"}), 404

    test_dict = test.to_dict()
    test_dict["progress"] = calculate_progress(test)
    test_dict["status"] = get_test_status(test)

    return jsonify({"test": test_dict}), 200


@tests_bp.route("/current", methods=["GET"])
@authenticate
def get_current_test():
    """Get the user's current (incomplete) test."""
    # Find incomplete test (no completed_at timestamp)
    test = (
        TestResult.query.filter_by(user_id=g.user_id, completed_at=None)
        .order_by(TestResult.created_at.desc())
        .first()
    )

    if not test:
        return jsonify({"message": "No current test found"}), 404

    test_dict = test.to_dict()
    test_dict["progress"] = calculate_progress(test)
    test_dict["status"] = get_test_status(test)

    return jsonify({"test": test_dict}), 200


@tests_bp.route("/history", methods=["GET"])
@authenticate
def get_test_history():
    """Get all tests for the authenticated user."""
    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    # Filter by completion status if specified
    completed = request.args.get("completed", type=str)
    query = TestResult.query.filter_by(user_id=g.user_id)

    if completed == "true":
        query = query.filter(TestResult.completed_at.isnot(None))
    elif completed == "false":
        query = query.filter(TestResult.completed_at.is_(None))

    # Order by most recent first
    query = query.order_by(TestResult.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    tests = pagination.items

    # Format response
    test_list = []
    for test in tests:
        test_dict = test.to_dict()
        test_dict["progress"] = calculate_progress(test)
        test_dict["status"] = get_test_status(test)
        test_list.append(test_dict)

    return jsonify(
        {
            "tests": test_list,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_pages": pagination.pages,
                "total_items": pagination.total,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        }
    ), 200