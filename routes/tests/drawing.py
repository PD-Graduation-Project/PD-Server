"""Drawing test routes."""
from flask import request, jsonify, g
from models.database import db
from models.test_result import TestResult
from . import tests_bp
from middleware.authenticate import authenticate
from .utils import (
    allowed_file,
    save_uploaded_file,
    process_ml_model,
    calculate_overall_status,
    calculate_progress,
    get_test_status,
    update_pd_probability
)


@tests_bp.route("/drawing/start", methods=["POST"])
@authenticate
def start_drawing_test():
    """Start or get existing drawing test."""
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
                "progress": calculate_progress(existing_test),
                "status": get_test_status(existing_test)
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
            "progress": calculate_progress(test),
            "status": get_test_status(test)
        }
    ), 201


@tests_bp.route("/drawing/status", methods=["GET"])
@authenticate
def get_drawing_status():
    """Get drawing test status."""
    test_id = request.args.get("test_id", type=int)
    if not test_id:
        return jsonify({"error": "test_id is required"}), 400

    test = TestResult.query.filter_by(id=test_id, user_id=g.user_id).first()
    if not test:
        return jsonify({"error": "Test not found"}), 404

    test_dict = test.to_dict()
    test_dict["progress"] = calculate_progress(test)
    test_dict["status"] = get_test_status(test)
    test_dict["drawing_completed"] = test.drawing_score is not None

    return jsonify({"test": test_dict}), 200


@tests_bp.route("/drawing/submit", methods=["POST"])
@authenticate
def submit_drawing():
    """Submit drawing test data and update the test record."""
    # Get test_id
    test_id = request.args.get("test_id") or request.form.get("test_id")
    if not test_id:
        return jsonify({"error": "test_id is required"}), 400

    try:
        test_id = int(test_id)
    except ValueError:
        return jsonify({"error": "test_id must be an integer"}), 400

    # Find the test record
    test = TestResult.query.filter_by(id=test_id, user_id=g.user_id).first()
    if not test:
        return jsonify({"error": "Test not found"}), 404

    # Check if drawing already submitted
    if test.drawing_score is not None:
        return jsonify({"error": "Drawing test already submitted for this test"}), 400

    # Check file upload
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename, "image"):
        return jsonify(
            {"error": "File type not allowed. Use .png, .jpg, or .jpeg"}
        ), 400

    # Save file
    filepath = save_uploaded_file(file, "drawing")

    # Process with ML model (simulated)
    ml_results = process_ml_model(filepath, "drawing")

    # Update test record
    test.drawing_score = ml_results["score"]

    # Check if all tests are complete
    if calculate_overall_status(test):
        update_pd_probability(test)

    db.session.commit()

    test_dict = test.to_dict()
    test_dict["progress"] = calculate_progress(test)
    test_dict["status"] = get_test_status(test)

    return jsonify(
        {
            "message": "Drawing test submitted successfully",
            "test_id": test.id,
            "drawing_score": test.drawing_score,
            "ml_results": ml_results,
            "test": test_dict,
        }
    ), 200