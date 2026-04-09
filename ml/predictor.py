"""
ML Predictor Interface

Bridges the Flask server with the _FINAL_SCRIPTS prediction modules.
Replaces drawing_model.py, tremor_model.py, and voice_model.py.

Each function accepts a TestSession ID (or User ID for questionnaire),
queries the DB for the uploaded file paths / user profile, then delegates
to the appropriate _FINAL_SCRIPTS predict().
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger

# ---------------------------------------------------------------------------
# S3 Download Helper
# ---------------------------------------------------------------------------
_temp_files = []  # Track temp files for cleanup


def _get_file_path(file_path: str) -> str:
    """
    Get local file path, downloading from S3 if needed.

    If S3 is enabled, downloads the file to a temp location and returns that path.
    Otherwise, returns the local path with uploads/ prefix if needed.

    Args:
        file_path: S3 key (e.g., 'drawing/64/spiral_l.jpg') or local path

    Returns:
        str: Local file path usable for reading
    """
    from config import Config

    # Check if S3 storage is enabled
    if Config.STORAGE_BACKEND == "s3":
        from utils.s3_storage import get_storage

        storage = get_storage()

        # Download to temp file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_path).suffix)
        tmp_path = tmp.name
        tmp.close()

        success = storage.download_file(file_path, tmp_path)
        if not success:
            raise FileNotFoundError(f"Failed to download {file_path} from S3")

        _temp_files.append(tmp_path)
        logger.debug(f"Downloaded S3 file {file_path} to {tmp_path}")
        return tmp_path
    else:
        # Local: prepend uploads/ prefix if needed
        if file_path.startswith("uploads/"):
            return file_path
        return f"uploads/{file_path}"


def _cleanup_temp_files():
    """Clean up any temp files downloaded from S3."""
    global _temp_files
    for path in _temp_files:
        try:
            os.unlink(path)
            logger.debug(f"Cleaned up temp file: {path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {path}: {e}")
    _temp_files = []


# ---------------------------------------------------------------------------
# Make _FINAL_SCRIPTS importable (models/, utils/, weights/ are relative to it)
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).parent / "_FINAL_SCRIPTS"

# We need to *change* the working directory before calling predict() because
# the scripts load weights with relative paths like "weights/...".
# We do this safely inside each function via os.chdir inside a try/finally.
# We also add _SCRIPTS_DIR to sys.path so the imports resolve.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _run_in_scripts_dir(fn):
    """
    Decorator: temporarily changes cwd to _SCRIPTS_DIR so that relative
    weight paths (e.g. 'weights/Spiral_Drawing_Model.pth') resolve correctly.
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        original_cwd = os.getcwd()
        try:
            os.chdir(_SCRIPTS_DIR)
            return fn(*args, **kwargs)
        finally:
            os.chdir(original_cwd)

    return wrapper


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
@_run_in_scripts_dir
def predict_drawing(test_session_id: int) -> float:
    """
    Predict Parkinson's probability from spiral drawing images.

    Queries the DB for drawing_spiral inputs belonging to this session,
    runs inference on each image, and returns the average probability.

    Args:
        test_session_id: The ID of the TestSession

    Returns:
        float: Probability of Parkinson's disease (0.0 = healthy, 1.0 = PD)
    """
    from predict_from_drawing import predict as _predict

    from models.test_models import TestInput

    inputs = TestInput.query.filter_by(
        test_session_id=test_session_id,
        input_type="drawing_spiral",
    ).all()

    if not inputs:
        raise ValueError(f"No drawing inputs found for session {test_session_id}")

    logger.info(
        f"Predicting drawing for session {test_session_id}, {len(inputs)} inputs"
    )
    probs = []
    try:
        for inp in inputs:
            local_path = _get_file_path(inp.file_path)
            prob = _predict(local_path)
            logger.info(f"Drawing input {inp.file_path} -> prob: {prob}")
            probs.append(prob)
    finally:
        _cleanup_temp_files()

    avg = sum(probs) / len(probs)
    logger.info(f"Drawing prediction result: {avg}")
    return avg


# ---------------------------------------------------------------------------
# Tremor
# ---------------------------------------------------------------------------

# Maps subtest index (str) to movement index (int) expected by TremorClassifier
_SUBTEST_TO_MOVEMENT = {
    "0": 0,  # CrossArms
    "1": 1,  # DrinkGlas
    "2": 2,  # Entrainment
    "3": 3,  # HoldWeight
    "4": 4,  # LiftHold
    "5": 5,  # PointFinger
    "6": 6,  # Relaxed
    "7": 7,  # RelaxedTask
    "8": 8,  # StretchHold
    "9": 9,  # TouchIndex
    "10": 10,  # TouchNose
}


@_run_in_scripts_dir
def predict_tremor(test_session_id: int) -> float:
    """
    Predict Parkinson's probability from wrist IMU data.

    Queries the DB for tremor_gyro inputs, groups them by subtest into
    left/right pairs, runs inference on each pair, and returns the average.

    File naming convention (from upload_routes.py):
        {test_session_id}_{subtest}_{hand}.txt   where hand is 'l' or 'r'

    The _FINAL_SCRIPTS predict_from_tremor expects a directory containing
    exactly one *LeftWrist*.txt and one *RightWrist*.txt. We create a
    temporary directory with symlinks using that naming convention.

    Args:
        test_session_id: The ID of the TestSession

    Returns:
        float: Probability of Parkinson's disease (0.0 = healthy, 1.0 = PD)
    """
    from predict_from_tremor import predict as _predict

    from models.test_models import TestInput, TestSession

    inputs = TestInput.query.filter_by(
        test_session_id=test_session_id,
        input_type="tremor_gyro",
    ).all()

    if not inputs:
        raise ValueError(f"No tremor inputs found for session {test_session_id}")

    # Group files by subtest: {subtest: {"l": path, "r": path}}
    # Parse subtest/hand from original file_path (S3 key or local path), NOT from temp download name
    subtests: dict[str, dict[str, str]] = {}
    for inp in inputs:
        # Use original file_path for parsing (e.g., "tremor/42/42_2_l.txt" or "uploads/tremor/42/42_2_l.txt")
        original_path = inp.file_path
        # Extract filename regardless of prefix
        filename = Path(original_path).name  # e.g. "42_2_l.txt"
        parts = filename.replace(".txt", "").split("_")
        # parts: [test_id, subtest, hand]
        if len(parts) < 3:
            logger.warning(
                f"Skipping tremor input with unparseable filename: {filename}"
            )
            continue
        subtest = parts[1]
        hand = parts[2]  # 'l' or 'r'

        # Download from S3 if needed, then add to map
        local_path = _get_file_path(inp.file_path)
        subtests.setdefault(subtest, {})[hand] = local_path

    # Get handedness from session config (default: right)
    session = TestSession.query.get(test_session_id)
    config = session.config or {}
    handedness = config.get("handedness", "right")

    probs = []
    tmpdir = tempfile.mkdtemp()
    try:
        for subtest, hands in subtests.items():
            if "l" not in hands or "r" not in hands:
                continue  # skip incomplete pairs

            movement = _SUBTEST_TO_MOVEMENT.get(subtest, int(subtest))

            # Create a per-subtest temp dir with expected naming
            sub_tmpdir = os.path.join(tmpdir, subtest)
            os.makedirs(sub_tmpdir, exist_ok=True)

            left_dst = os.path.join(sub_tmpdir, f"{subtest}_LeftWrist.txt")
            right_dst = os.path.join(sub_tmpdir, f"{subtest}_RightWrist.txt")

            shutil.copy2(hands["l"], left_dst)
            shutil.copy2(hands["r"], right_dst)

            prob = _predict(
                txt_dir=sub_tmpdir,
                movement=movement,
                handedness=handedness,
            )
            logger.info(
                f"Tremor subtest {subtest} (movement {movement}) -> prob: {prob}"
            )
            probs.append(prob)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        _cleanup_temp_files()

    if not probs:
        raise ValueError(
            f"No valid left/right tremor pairs found for session {test_session_id}"
        )

    return sum(probs) / len(probs)


# ---------------------------------------------------------------------------
# Voice / Audio
# ---------------------------------------------------------------------------
@_run_in_scripts_dir
def predict_voice(test_session_id: int) -> float:
    """
    Predict Parkinson's probability from a voice recording (WAV/M4A).

    Queries the DB for voice_recording inputs, extracts audio features,
    and returns the model probability.

    Args:
        test_session_id: The ID of the TestSession

    Returns:
        float: Probability of Parkinson's disease (0.0 = healthy, 1.0 = PD)
    """
    import subprocess

    from predict_from_audio import predict as _predict

    from models.test_models import TestInput, TestSession

    inputs = TestInput.query.filter_by(
        test_session_id=test_session_id,
        input_type="voice_recording",
    ).all()

    if not inputs:
        raise ValueError(f"No voice inputs found for session {test_session_id}")

    session = TestSession.query.get(test_session_id)
    gender = None
    if session and session.user_id_fk:
        user = session.user_id_fk
        if hasattr(user, "gender") and user.gender:
            gender = "F" if str(user.gender).lower() in ("female", "f", "1") else "M"

    probs = []
    try:
        for inp in inputs:
            local_path = _get_file_path(inp.file_path)

            if local_path.lower().endswith(".m4a"):
                wav_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
                _temp_files.append(wav_path)
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        local_path,
                        "-ar",
                        "44100",
                        "-ac",
                        "1",
                        wav_path,
                    ],
                    capture_output=True,
                    check=True,
                )
                local_path = wav_path

            prob = _predict(local_path, gender=gender)

            logger.info(f"Voice Test Input {inp.file_path} -> prob: {prob}")
            probs.append(prob)
    finally:
        _cleanup_temp_files()

    return sum(probs) / len(probs)


# ---------------------------------------------------------------------------
# Questionnaire
# ---------------------------------------------------------------------------
@_run_in_scripts_dir
def predict_questionnaire(user_id: int) -> float:
    """
    Predict Parkinson's probability from the user's questionnaire profile.

    Reads demographic info and Q01–Q28 answers from the User model,
    assembles the input list expected by predict_from_questionnaire.predict(),
    and returns the model probability.

    Args:
        user_id: The ID of the User whose profile to use

    Returns:
        float: Probability of Parkinson's disease (0.0 = healthy, 1.0 = PD)

    Raises:
        ValueError: If user not found or required profile fields are missing
    """
    from predict_from_questionnaire import predict as _predict

    from models.user import User

    user = User.query.get(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    # All 28 questions — use -1 (unknown) for any unanswered question
    questions = [
        (
            int(getattr(user, f"Q{i:02d}"))
            if getattr(user, f"Q{i:02d}") is not None
            else -1
        )
        for i in range(1, 29)
    ]

    x = [
        user.age if user.age is not None else -1,
        user.height if user.height is not None else -1,
        user.weight if user.weight is not None else -1,
        user.gender if user.gender is not None else -1,
        (
            user.pd_appearance_in_kinship
            if user.pd_appearance_in_kinship is not None
            else -1
        ),
        (
            user.pd_appearance_in_first_grade_kinship
            if user.pd_appearance_in_first_grade_kinship is not None
            else -1
        ),
        questions,
    ]

    score = _predict(x)
    logger.info(f"Questionnaire for User {user_id} -> prob: {score}")
    return score
