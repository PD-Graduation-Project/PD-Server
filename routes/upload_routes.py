from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from loguru import logger
from redis import Redis
from rq import Queue

from config import Config
from middleware.authenticate import authenticate
from middleware.authenticate_esp32 import authenticate_jwt_or_esp32
from models.database import db
from models.test_models import TestGroup, TestInput, TestSession
from models.user import User
from utils.esp32_connection_manager import connection_manager
from utils.storage import (
    delete_file,
    generate_drawing_filename,
    generate_tremor_filename,
    generate_voice_filename,
    get_expires_at,
    get_file_extension,
    is_allowed_file,
    save_imu_data,
    save_uploaded_file,
    validate_file_size,
    validate_hand,
    validate_tremor_subtest,
)

upload_bp = Blueprint("upload", __name__, url_prefix="/api/tests")


def get_ml_queue():
    """Get the RQ queue for ML inference jobs."""
    return Queue("ml", connection=Redis.from_url(Config.REDIS_URL))


@upload_bp.route("/<int:test_id>/tremor", methods=["POST"])
@authenticate_jwt_or_esp32
def upload_tremor(test_id):
    """Upload gyro data for tremor test.

    Accepts either:
    - multipart/form-data with file upload
    - JSON body with IMU data arrays
    """
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    test_session = db.session.get(TestSession, test_id)
    if not test_session:
        return jsonify({"error": "Test not found"}), 404

    if test_session.user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    if test_session.test_type != "tremor":
        return jsonify({"error": "Test is not a tremor test"}), 400

    content_type = request.content_type or ""

    if "application/json" in content_type or request.get_json(silent=True):
        return _upload_tremor_json(test_id, test_session)
    else:
        return _upload_tremor_file(test_id, test_session)


def _upload_tremor_json(test_id, test_session):
    """Handle JSON body upload with IMU data arrays."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    subtest = data.get("subtest_id") or data.get("subtest")
    hand_raw = data.get("hand")
    imu_data = data.get("imu_data")

    if not subtest:
        return jsonify({"error": "subtest_id is required"}), 400

    if not hand_raw:
        return jsonify({"error": "hand is required"}), 400

    hand = (
        "l"
        if hand_raw.lower() in ("left", "l")
        else "r" if hand_raw.lower() in ("right", "r") else None
    )
    if not hand:
        return (
            jsonify({"error": "Invalid hand: must be 'left', 'right', 'l', or 'r'"}),
            400,
        )

    if not imu_data or not isinstance(imu_data, dict):
        return jsonify({"error": "imu_data is required and must be an object"}), 400

    required_keys = {"ax", "ay", "az", "gx", "gy", "gz"}
    if not required_keys.issubset(imu_data.keys()):
        missing = required_keys - imu_data.keys()
        return jsonify({"error": f"imu_data missing keys: {', '.join(missing)}"}), 400

    for key in required_keys:
        if not isinstance(imu_data[key], list):
            return jsonify({"error": f"imu_data.{key} must be an array"}), 400

    if not validate_tremor_subtest(str(subtest)):
        return jsonify({"error": f"Invalid subtest: {subtest}"}), 400

    config = test_session.config or {}
    step_key = str(subtest)
    if config and not config.get(step_key, True):
        return (
            jsonify({"error": f"Subtest {subtest} is not enabled for this test"}),
            400,
        )

    subtest_str = str(subtest)
    filename = generate_tremor_filename(test_id, subtest_str, hand)

    try:
        file_path, file_size = save_imu_data("tremor", test_id, filename, imu_data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    test_input = TestInput(
        test_session_id=test_id,
        input_type="tremor_gyro",
        file_path=file_path,
        original_filename=filename,
        mime_type="text/plain",
        file_size=file_size,
        expires_at=get_expires_at(),
    )
    db.session.add(test_input)

    if test_session.status == "pending":
        test_session.status = "in_progress"

    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "id": test_input.id,
                    "input_type": "tremor_gyro",
                    "subtest": subtest_str,
                    "hand": hand,
                    "file_path": file_path,
                },
            }
        ),
        200,
    )


def _upload_tremor_file(test_id, test_session):
    """Handle multipart/form-data file upload."""
    subtest = request.form.get("subtest")
    hand = request.form.get("hand")

    if not subtest or not hand:
        return jsonify({"error": "Missing subtest or hand parameter"}), 400

    if not validate_tremor_subtest(subtest):
        return jsonify({"error": f"Invalid subtest: {subtest}"}), 400

    if not validate_hand(hand):
        return jsonify({"error": "Invalid hand: must be 'l' or 'r'"}), 400

    config = test_session.config or {}
    step_key = str(subtest)
    if config and not config.get(step_key, True):
        return (
            jsonify({"error": f"Subtest {subtest} is not enabled for this test"}),
            400,
        )

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not is_allowed_file(file.filename, "tremor"):
        return jsonify({"error": "Invalid file type. Only TXT files allowed"}), 400

    is_valid, error_msg = validate_file_size(file, "tremor")
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    filename = generate_tremor_filename(test_id, subtest, hand)
    file_path, file_size = save_uploaded_file(file, "tremor", test_id, filename)

    test_input = TestInput(
        test_session_id=test_id,
        input_type="tremor_gyro",
        file_path=file_path,
        original_filename=file.filename,
        mime_type="text/plain",
        file_size=file_size,
        expires_at=get_expires_at(),
    )
    db.session.add(test_input)

    if test_session.status == "pending":
        test_session.status = "in_progress"

    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "id": test_input.id,
                    "input_type": "tremor_gyro",
                    "subtest": subtest,
                    "hand": hand,
                    "file_path": file_path,
                },
            }
        ),
        200,
    )


@upload_bp.route("/<int:test_id>/drawings", methods=["POST"])
@authenticate
def upload_drawings(test_id):
    """Upload spiral drawing images."""
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    test_session = db.session.get(TestSession, test_id)
    if not test_session:
        return jsonify({"error": "Test not found"}), 404

    if test_session.user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    if test_session.test_type != "drawing":
        return jsonify({"error": "Test is not a drawing test"}), 400

    if "spiral_left" not in request.files or "spiral_right" not in request.files:
        return (
            jsonify({"error": "Both spiral_left and spiral_right files required"}),
            400,
        )

    inputs = []
    for hand, field_name in [("l", "spiral_left"), ("r", "spiral_right")]:
        file = request.files[field_name]

        if not file.filename:
            return jsonify({"error": f"No file selected for {field_name}"}), 400

        if not is_allowed_file(file.filename, "drawing"):
            return (
                jsonify(
                    {
                        "error": f"Invalid file type for {field_name}. Only PNG/JPG allowed"
                    }
                ),
                400,
            )

        is_valid, error_msg = validate_file_size(file, "drawing")
        if not is_valid:
            return jsonify({"error": f"{field_name}: {error_msg}"}), 400

        ext = get_file_extension(file.filename)
        filename = generate_drawing_filename(hand, ext)
        file_path, file_size = save_uploaded_file(file, "drawing", test_id, filename)

        test_input = TestInput(
            test_session_id=test_id,
            input_type="drawing_spiral",
            file_path=file_path,
            original_filename=file.filename,
            mime_type=file.content_type or f"image/{ext}",
            file_size=file_size,
            expires_at=get_expires_at(),
        )
        db.session.add(test_input)
        db.session.flush()

        inputs.append(
            {
                "id": test_input.id,
                "input_type": "drawing_spiral",
                "hand": hand,
                "file_path": file_path,
            }
        )

    if test_session.status == "pending":
        test_session.status = "in_progress"

    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "data": {"inputs": inputs},
            }
        ),
        200,
    )


@upload_bp.route("/<int:test_id>/voice", methods=["POST"])
@authenticate
def upload_voice(test_id):
    """Upload voice recording."""
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    test_session = db.session.get(TestSession, test_id)
    if not test_session:
        return jsonify({"error": "Test not found"}), 404

    if test_session.user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    if test_session.test_type != "voice":
        return jsonify({"error": "Test is not a voice test"}), 400

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    file = request.files["audio"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not is_allowed_file(file.filename, "voice"):
        return jsonify({"error": "Invalid file type. Only WAV/MP3/M4A allowed"}), 400

    is_valid, error_msg = validate_file_size(file, "voice")
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    ext = get_file_extension(file.filename)
    filename = generate_voice_filename(ext)
    file_path, file_size = save_uploaded_file(file, "voice", test_id, filename)

    test_input = TestInput(
        test_session_id=test_id,
        input_type="voice_recording",
        file_path=file_path,
        original_filename=file.filename,
        mime_type=file.content_type or f"audio/{ext}",
        file_size=file_size,
        expires_at=get_expires_at(),
    )
    db.session.add(test_input)

    if test_session.status == "pending":
        test_session.status = "in_progress"

    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "id": test_input.id,
                    "input_type": "voice_recording",
                    "file_path": file_path,
                },
            }
        ),
        200,
    )


@upload_bp.route("/<int:test_id>/complete", methods=["POST"])
@authenticate_jwt_or_esp32
def complete_test(test_id):
    """Mark a test as completed."""
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    test_session = db.session.get(TestSession, test_id)
    if not test_session:
        return jsonify({"error": "Test not found"}), 404

    if test_session.user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    if test_session.status == "completed":
        return jsonify({"error": "Test is already completed"}), 400

    if test_session.status == "pending":
        return jsonify({"error": "Test has no uploads yet"}), 400

    uploaded_inputs = TestInput.query.filter_by(test_session_id=test_id).all()
    uploaded_count = len(uploaded_inputs)

    missing = []
    expected_count = 0

    if test_session.test_type == "tremor":
        config = test_session.config or {}
        uploaded_files = {inp.file_path.split("/")[-1] for inp in uploaded_inputs}

        for step in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]:
            step_key = str(step)
            if config.get(step_key, False):
                expected_count += 2
                for hand in ["l", "r"]:
                    expected_file = f"{test_id}_{step}_{hand}.txt"
                    if expected_file not in uploaded_files:
                        missing.append(f"{step}_{hand}")

    elif test_session.test_type == "drawing":
        expected_count = 2
        if uploaded_count < 2:
            missing.append("spiral drawings incomplete")

    elif test_session.test_type == "voice":
        expected_count = 1
        if uploaded_count < 1:
            missing.append("voice recording")

    if missing:
        return (
            jsonify(
                {
                    "error": "Missing required subtest uploads",
                    "missing": missing,
                    "expected_count": expected_count,
                    "uploaded_count": uploaded_count,
                }
            ),
            400,
        )

    test_session.status = "completed"
    test_session.completed_at = datetime.now(timezone.utc)

    from ml.tasks import run_inference

    test_session.ml_status = "processing"
    db.session.commit()

    ml_job_id = None
    ml_status = "processing"
    try:
        queue = get_ml_queue()
        job = queue.enqueue(run_inference, test_session.id, job_timeout="5m")
        test_session.ml_job_id = job.id
        ml_job_id = job.id
        db.session.commit()
    except Exception:
        logger.exception(
            f"Failed to enqueue ML inference for session {test_session.id}"
        )
        test_session.ml_status = "failed"
        test_session.ml_job_id = None
        ml_status = "failed"
        db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "message": "Test completed",
                    "status": "completed",
                    "ml_status": ml_status,
                    "ml_job_id": ml_job_id,
                    "uploaded_count": uploaded_count,
                    "expected_count": expected_count,
                    "missing": missing,
                },
            }
        ),
        202,
    )


@upload_bp.route("/<int:test_id>/reset", methods=["POST"])
@authenticate_jwt_or_esp32
def reset_test(test_id):
    """
    Reset a test session by deleting all uploaded files and inputs,
    and setting the status back to pending.

    Optionally accepts a new config to update the test configuration.
    Only allowed if the test's group is NOT completed.
    Auth: JWT user (owner) or paired ESP32 device.
    """
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    test_session = db.session.get(TestSession, test_id)
    if not test_session:
        return jsonify({"error": "Test not found"}), 404

    if test_session.user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    # Check if group is completed - reject reset if so
    if test_session.group_id:
        group = db.session.get(TestGroup, test_session.group_id)
        if group and group.status == "completed":
            return (
                jsonify(
                    {
                        "error": "Cannot reset test in a completed group. "
                        "Create a new test session instead."
                    }
                ),
                409,
            )

    # Get optional new config from request body
    new_config = None
    json_body = request.get_json(silent=True)
    if json_body and "config" in json_body:
        new_config = json_body["config"]
        if not isinstance(new_config, dict):
            return jsonify({"error": "config must be an object"}), 400
        valid_keys = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
        for key in new_config:
            if key not in valid_keys:
                return (
                    jsonify(
                        {"error": f"Invalid config key: {key}. Must be one of 0-10"}
                    ),
                    400,
                )
            if not isinstance(new_config[key], bool):
                return (
                    jsonify({"error": f"Config value for {key} must be boolean"}),
                    400,
                )

    # Delete uploaded files from disk
    inputs = TestInput.query.filter_by(test_session_id=test_id).all()
    for inp in inputs:
        if inp.file_path:
            delete_file(inp.file_path)
        db.session.delete(inp)

    # Cancel any pending ML job
    if test_session.ml_job_id:
        try:
            queue = get_ml_queue()
            job = queue.fetch_job(test_session.ml_job_id)
            if job:
                job.cancel()
        except Exception as e:
            logger.warning(f"Failed to cancel job {test_session.ml_job_id}: {e}")

    # Reset session state
    test_session.status = "pending"
    test_session.ml_score = None
    test_session.ml_status = None
    test_session.ml_job_id = None
    test_session.completed_at = None

    # Update config if new config provided
    if new_config is not None:
        test_session.config = new_config

    # Reset group state if applicable
    if test_session.group_id:
        group = db.session.get(TestGroup, test_session.group_id)
        if group and group.status == "completed":
            group.status = "in_progress"
            group.overall_score = None
            group.completed_at = None
            group.ml_status = None
            group.ml_job_id = None

    db.session.commit()

    logger.info(f"Test {test_id} reset by user {current_user.id}")

    return (
        jsonify(
            {
                "success": True,
                "data": {"message": "Test reset successfully", "status": "pending"},
            }
        ),
        200,
    )


@upload_bp.route("/<int:test_id>/start", methods=["POST"])
@authenticate_jwt_or_esp32
def start_test(test_id):
    """
    Send a test_started event to the paired ESP32 device for a tremor test.
    Use this to notify the device to start collecting data.

    Auth: JWT user (owner) or paired ESP32 device.
    """
    current_user = db.session.get(User, g.user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    test_session = db.session.get(TestSession, test_id)
    if not test_session:
        return jsonify({"error": "Test not found"}), 404

    if test_session.user_id != current_user.id:
        return jsonify({"error": "Forbidden"}), 403

    if test_session.test_type != "tremor":
        return (
            jsonify({"error": "test_started event is only supported for tremor tests"}),
            400,
        )

    if test_session.device_source != "esp32":
        return (
            jsonify(
                {"error": "test_started event is only supported for ESP32 device tests"}
            ),
            400,
        )

    try:
        success = connection_manager.send_event(
            current_user.id,
            "test_started",
            {
                "test_id": test_session.id,
                "test_type": test_session.test_type,
                "config": test_session.config,
            },
        )
        if success:
            logger.info(
                f"test_started event sent for test {test_id} to user {current_user.id}"
            )
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {"message": "test_started event sent"},
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "error": "ESP32 device is not connected. Make sure the device is powered on and connected."
                    }
                ),
                503,
            )
    except Exception as e:
        logger.error(f"Exception sending test_started event for test {test_id}: {e}")
        return jsonify({"error": "Failed to send event to device"}), 500
