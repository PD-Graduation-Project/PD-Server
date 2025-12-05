import os
import uuid
import random
from datetime import datetime
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from models.database import db
from models.test_result import TestResult, TestStatus
from routes.auth import verify_token
from config import Config

tests_bp = Blueprint("tests", __name__, url_prefix="/api/test")


def allowed_file(filename, file_type):
    """Check if file extension is allowed."""
    if not filename or "." not in filename:
        return False

    ext = filename.rsplit(".", 1)[1].lower()
    return ext in Config.ALLOWED_EXTENSIONS.get(file_type, [])


def save_uploaded_file(file, file_type):
    """Save uploaded file and return filepath."""
    if not file:
        return None

    # Generate unique filename
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    filename = f"{uuid.uuid4()}.{ext}"

    # Create subdirectory for file type
    upload_dir = os.path.join(Config.UPLOAD_FOLDER, file_type)
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    return filepath


def process_ml_model(filepath, test_type):
    """Simulate ML model processing. Replace with actual ML models."""
    # Generate realistic scores based on test type
    if test_type == "tremor":
        # Tremor: higher score = more tremor = higher PD probability
        base_score = random.uniform(0.3, 0.9)
        confidence = random.uniform(0.8, 0.95)
        return {
            "score": round(base_score, 3),
            "confidence": round(confidence, 3),
            "frequency_hz": round(random.uniform(3.0, 7.0), 2),
            "amplitude": round(random.uniform(0.1, 0.5), 3),
            "regularity": round(random.uniform(0.4, 0.9), 3),
        }

    elif test_type == "drawing":
        # Drawing: higher score = worse drawing = higher PD probability
        base_score = random.uniform(0.2, 0.85)
        confidence = random.uniform(0.85, 0.98)
        return {
            "score": round(base_score, 3),
            "confidence": round(confidence, 3),
            "smoothness": round(random.uniform(0.3, 0.95), 3),
            "tremor_index": round(random.uniform(0.1, 0.8), 3),
            "spiral_deviation": round(random.uniform(0.05, 0.6), 3),
        }

    elif test_type == "speech":
        # Speech: higher score = worse speech = higher PD probability
        base_score = random.uniform(0.25, 0.8)
        confidence = random.uniform(0.75, 0.92)
        return {
            "score": round(base_score, 3),
            "confidence": round(confidence, 3),
            "pitch_variability": round(random.uniform(0.1, 0.7), 3),
            "voice_stability": round(random.uniform(0.3, 0.9), 3),
            "articulation": round(random.uniform(0.4, 0.95), 3),
        }

    return {"score": 0.5, "confidence": 0.5, "error": "Unknown test type"}


def calculate_overall_status(test_result):
    """Check if all tests are completed and update overall status."""
    completed_tests = 0
    total_tests = 3

    if test_result.tremor_score is not None:
        completed_tests += 1
    if test_result.drawing_score is not None:
        completed_tests += 1
    if test_result.speech_score is not None:
        completed_tests += 1

    # If all tests are done, mark as completed
    if completed_tests == total_tests:
        test_result.completed_at = datetime.utcnow()
        return True

    return False


@tests_bp.route("/", methods=["POST"])
def start_test():
    """Create a new test record and return its ID."""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token required"}), 401

    user_id = verify_token(token.replace("Bearer ", ""))
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Check if user already has an incomplete test
    existing_test = TestResult.query.filter_by(
        user_id=user_id, completed_at=None
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
    test = TestResult(user_id=user_id)

    db.session.add(test)
    db.session.commit()

    return jsonify(
        {
            "message": "Test started successfully",
            "test_id": test.id,
            "test": test.to_dict(),
        }
    ), 201


@tests_bp.route("/tremor", methods=["POST"])
def submit_tremor():
    """Submit tremor test data and update the test record."""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token required"}), 401

    user_id = verify_token(token.replace("Bearer ", ""))
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Get test_id from query params or request body
    test_id = request.args.get("test_id") or request.form.get("test_id")
    if not test_id:
        return jsonify({"error": "test_id is required"}), 400

    try:
        test_id = int(test_id)
    except ValueError:
        return jsonify({"error": "test_id must be an integer"}), 400

    # Find the test record
    test = TestResult.query.filter_by(id=test_id, user_id=user_id).first()
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

    # Store additional data in a separate column or table if needed
    # For now, we'll just update the score

    # Check if all tests are complete
    if calculate_overall_status(test):
        # Calculate overall PD probability (average of scores)
        scores = [
            s
            for s in [test.tremor_score, test.drawing_score, test.speech_score]
            if s is not None
        ]
        if scores:
            test.pd_probability = sum(scores) / len(scores)

    db.session.commit()

    return jsonify(
        {
            "message": "Tremor test submitted successfully",
            "test_id": test.id,
            "tremor_score": test.tremor_score,
            "ml_results": ml_results,
            "test": test.to_dict(),
        }
    ), 200


@tests_bp.route("/drawing", methods=["POST"])
def submit_drawing():
    """Submit drawing test data and update the test record."""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token required"}), 401

    user_id = verify_token(token.replace("Bearer ", ""))
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Get test_id
    test_id = request.args.get("test_id") or request.form.get("test_id")
    if not test_id:
        return jsonify({"error": "test_id is required"}), 400

    try:
        test_id = int(test_id)
    except ValueError:
        return jsonify({"error": "test_id must be an integer"}), 400

    # Find the test record
    test = TestResult.query.filter_by(id=test_id, user_id=user_id).first()
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
        # Calculate overall PD probability
        scores = [
            s
            for s in [test.tremor_score, test.drawing_score, test.speech_score]
            if s is not None
        ]
        if scores:
            test.pd_probability = sum(scores) / len(scores)

    db.session.commit()

    return jsonify(
        {
            "message": "Drawing test submitted successfully",
            "test_id": test.id,
            "drawing_score": test.drawing_score,
            "ml_results": ml_results,
            "test": test.to_dict(),
        }
    ), 200


@tests_bp.route("/speech", methods=["POST"])
def submit_speech():
    """Submit speech test data and update the test record."""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token required"}), 401

    user_id = verify_token(token.replace("Bearer ", ""))
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Get test_id
    test_id = request.args.get("test_id") or request.form.get("test_id")
    if not test_id:
        return jsonify({"error": "test_id is required"}), 400

    try:
        test_id = int(test_id)
    except ValueError:
        return jsonify({"error": "test_id must be an integer"}), 400

    # Find the test record
    test = TestResult.query.filter_by(id=test_id, user_id=user_id).first()
    if not test:
        return jsonify({"error": "Test not found"}), 404

    # Check if speech already submitted
    if test.speech_score is not None:
        return jsonify({"error": "Speech test already submitted for this test"}), 400

    # Check file upload
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename, "audio"):
        return jsonify({"error": "File type not allowed. Use .mp3, .wav, or .m4a"}), 400

    # Save file
    filepath = save_uploaded_file(file, "speech")

    # Process with ML model (simulated)
    ml_results = process_ml_model(filepath, "speech")

    # Update test record
    test.speech_score = ml_results["score"]

    # Check if all tests are complete
    if calculate_overall_status(test):
        # Calculate overall PD probability
        scores = [
            s
            for s in [test.tremor_score, test.drawing_score, test.speech_score]
            if s is not None
        ]
        if scores:
            test.pd_probability = sum(scores) / len(scores)

    db.session.commit()

    return jsonify(
        {
            "message": "Speech test submitted successfully",
            "test_id": test.id,
            "speech_score": test.speech_score,
            "ml_results": ml_results,
            "test": test.to_dict(),
        }
    ), 200


@tests_bp.route("/<int:test_id>", methods=["GET"])
def get_test_result(test_id):
    """Get a specific test result by ID."""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token required"}), 401

    user_id = verify_token(token.replace("Bearer ", ""))
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401

    test = TestResult.query.filter_by(id=test_id, user_id=user_id).first()

    if not test:
        return jsonify({"error": "Test not found"}), 404

    # Calculate progress
    completed_tests = 0
    if test.tremor_score is not None:
        completed_tests += 1
    if test.drawing_score is not None:
        completed_tests += 1
    if test.speech_score is not None:
        completed_tests += 1

    test_dict = test.to_dict()
    test_dict["progress"] = {
        "completed": completed_tests,
        "total": 3,
        "percentage": (completed_tests / 3) * 100 if completed_tests > 0 else 0,
    }

    # Add status indicator
    if test.completed_at:
        test_dict["status"] = "completed"
    elif completed_tests > 0:
        test_dict["status"] = "in_progress"
    else:
        test_dict["status"] = "not_started"

    return jsonify({"test": test_dict}), 200


@tests_bp.route("/current", methods=["GET"])
def get_current_test():
    """Get the user's current (incomplete) test."""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token required"}), 401

    user_id = verify_token(token.replace("Bearer ", ""))
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Find incomplete test (no completed_at timestamp)
    test = (
        TestResult.query.filter_by(user_id=user_id, completed_at=None)
        .order_by(TestResult.created_at.desc())
        .first()
    )

    if not test:
        return jsonify({"message": "No current test found"}), 404

    # Calculate progress
    completed_tests = 0
    if test.tremor_score is not None:
        completed_tests += 1
    if test.drawing_score is not None:
        completed_tests += 1
    if test.speech_score is not None:
        completed_tests += 1

    test_dict = test.to_dict()
    test_dict["progress"] = {
        "completed": completed_tests,
        "total": 3,
        "percentage": (completed_tests / 3) * 100 if completed_tests > 0 else 0,
    }

    test_dict["status"] = "in_progress" if completed_tests > 0 else "not_started"

    return jsonify({"test": test_dict}), 200


@tests_bp.route("/history", methods=["GET"])
def get_test_history():
    """Get all tests for the authenticated user."""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Authorization token required"}), 401

    user_id = verify_token(token.replace("Bearer ", ""))
    if not user_id:
        return jsonify({"error": "Invalid or expired token"}), 401

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    # Filter by completion status if specified
    completed = request.args.get("completed", type=str)
    query = TestResult.query.filter_by(user_id=user_id)

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

        # Calculate progress
        completed_tests = 0
        if test.tremor_score is not None:
            completed_tests += 1
        if test.drawing_score is not None:
            completed_tests += 1
        if test.speech_score is not None:
            completed_tests += 1

        test_dict["progress"] = {
            "completed": completed_tests,
            "total": 3,
            "percentage": (completed_tests / 3) * 100 if completed_tests > 0 else 0,
        }

        test_dict["status"] = "completed" if test.completed_at else "incomplete"
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
