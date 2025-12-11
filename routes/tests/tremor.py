"""Tremor test routes."""

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
    update_pd_probability,
)

# Default tremor protocol movements
DEFAULT_TREMOR_MOVEMENTS = [
    {
        "step": "1a",
        "duration_seconds": 20,
        "name": "Resting eyes closed",
    },
    {
        "step": "1b",
        "duration_seconds": 20,
        "name": "Resting with serial sevens",
    },
    {
        "step": "2",
        "duration_seconds": 10,
        "name": "Lift and extend arms",
    },
    {
        "step": "3",
        "duration_seconds": 10,
        "name": "Arms remain lifted",
    },
    {
        "step": "4",
        "duration_seconds": 10,
        "name": "Hold one kilogram weight",
    },
    {
        "step": "5",
        "duration_seconds": 10,
        "name": "Point index finger",
    },
    {
        "step": "6",
        "duration_seconds": 10,
        "name": "Drink from glass",
    },
    {
        "step": "7",
        "duration_seconds": 10,
        "name": "Cross and extend arms",
    },
    {
        "step": "8",
        "duration_seconds": 10,
        "name": "Touch index fingers together",
    },
    {
        "step": "9",
        "duration_seconds": 10,
        "name": "Tap nose with index finger",
    },
    {
        "step": "10",
        "duration_seconds": 20,
        "name": "Entrainment foot stomping",
    },
]


@tests_bp.route("/tremor/start", methods=["POST"])
@authenticate
def start_tremor_test():
    """
    Add tremor movements to an existing test.
    Does not create a new test - requires test_id to already exist.
    Can optionally accept custom movement steps in request body.

    Request body example:
    {
        "test_id": 123,
        "steps": ["1a", "1b", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    }
    """

    data = request.get_json() or {}

    # Get test_id from body
    test_id = data.get("test_id")
    if not test_id:
        return jsonify({"error": "test_id is required"}), 400

    try:
        test_id = int(test_id)
    except (ValueError, TypeError):
        return jsonify({"error": "test_id must be an integer"}), 400

    # Find the test record
    test = TestResult.query.filter_by(id=test_id, user_id=g.user_id).first()
    if not test:
        return jsonify({"error": "Test not found"}), 404

    # Check if tremor movements already set
    if test.tremor_movements is not None:
        return jsonify(
            {
                "message": "Tremor movements already configured for this test",
                "test_id": test.id,
                "tremor_movements": test.tremor_movements,
                "total_duration": sum(
                    m["duration_seconds"] for m in test.tremor_movements
                ),
            }
        ), 200

    # Get custom steps from request or use all default steps
    requested_steps = data.get("steps", None)

    # Build movements list based on requested steps
    if requested_steps is None:
        # No steps specified, use all default movements
        tremor_movements = DEFAULT_TREMOR_MOVEMENTS
    else:
        # Validate steps is a list
        if not isinstance(requested_steps, list):
            return jsonify({"error": "steps must be an array"}), 400

        # Filter default movements to include only requested steps
        tremor_movements = [
            movement
            for movement in DEFAULT_TREMOR_MOVEMENTS
            if movement["step"] in requested_steps
        ]

        # Check if any requested steps were not found
        found_steps = {m["step"] for m in tremor_movements}
        invalid_steps = set(requested_steps) - found_steps
        if invalid_steps:
            return jsonify(
                {
                    "error": f"Invalid steps: {', '.join(invalid_steps)}",
                    "valid_steps": [m["step"] for m in DEFAULT_TREMOR_MOVEMENTS],
                }
            ), 400

        # Ensure at least one movement
        if not tremor_movements:
            return jsonify({"error": "At least one valid step is required"}), 400

    # Update test with movements
    test.tremor_movements = tremor_movements
    db.session.commit()

    total_duration = sum(m["duration_seconds"] for m in tremor_movements)

    return jsonify(
        {
            "message": "Tremor movements configured successfully",
            "test_id": test.id,
            "tremor_movements": tremor_movements,
            "total_duration": total_duration,
            "test": test.to_dict(),
            "progress": calculate_progress(test),
            "status": get_test_status(test),
        }
    ), 200


@tests_bp.route("/tremor/status", methods=["GET"])
@authenticate
def get_tremor_status():
    """Get tremor test status for a specific test."""
    test_id = request.args.get("test_id", type=int)
    if not test_id:
        return jsonify({"error": "test_id is required"}), 400

    test = TestResult.query.filter_by(id=test_id, user_id=g.user_id).first()
    if not test:
        return jsonify({"error": "Test not found"}), 404

    return jsonify(
        {
            "test_id": test.id,
            "tremor_completed": test.tremor_score is not None,
            "tremor_score": test.tremor_score,
            "tremor_movements": test.tremor_movements,
            "status": get_test_status(test),
            "progress": calculate_progress(test),
        }
    ), 200


@tests_bp.route("/tremor/submit", methods=["POST"])
@authenticate
def submit_tremor():
    """Submit tremor test data and update the test record."""
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

    # Check if tremor already submitted
    if test.tremor_score is not None:
        return jsonify({"error": "Tremor test already submitted for this test"}), 400

    # Check file upload
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename, "text"):
        return jsonify(
            {"error": "File type not allowed. Use .txt, .csv, or .json"}
        ), 400

    # Save file
    filepath = save_uploaded_file(file, "tremor")

    # Process with ML model (simulated)
    ml_results = process_ml_model(filepath, "tremor")

    # Update test record
    test.tremor_score = ml_results["score"]

    # Check if all tests are complete
    if calculate_overall_status(test):
        update_pd_probability(test)

    db.session.commit()

    test_dict = test.to_dict()
    test_dict["progress"] = calculate_progress(test)
    test_dict["status"] = get_test_status(test)

    return jsonify(
        {
            "message": "Tremor test submitted successfully",
            "test_id": test.id,
            "tremor_score": test.tremor_score,
            "ml_results": ml_results,
            "test": test_dict,
        }
    ), 200
