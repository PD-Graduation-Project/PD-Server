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

    probs = []
    for inp in inputs:
        prob = _predict(inp.file_path)
        probs.append(prob)

    return sum(probs) / len(probs)


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
    subtests: dict[str, dict[str, str]] = {}
    for inp in inputs:
        filename = Path(inp.file_path).name  # e.g. "42_2_l.txt"
        parts = filename.replace(".txt", "").split("_")
        # parts: [test_id, subtest, hand]
        if len(parts) < 3:
            continue
        subtest = parts[1]
        hand = parts[2]  # 'l' or 'r'
        subtests.setdefault(subtest, {})[hand] = inp.file_path

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
            probs.append(prob)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

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
    Predict Parkinson's probability from a voice recording (WAV).

    Queries the DB for voice_recording inputs, extracts audio features,
    and returns the model probability.

    Args:
        test_session_id: The ID of the TestSession

    Returns:
        float: Probability of Parkinson's disease (0.0 = healthy, 1.0 = PD)
    """
    from predict_from_audio import predict as _predict

    from models.test_models import TestInput, TestSession

    inputs = TestInput.query.filter_by(
        test_session_id=test_session_id,
        input_type="voice_recording",
    ).all()

    if not inputs:
        raise ValueError(f"No voice inputs found for session {test_session_id}")

    # Determine gender from the user's profile if available
    session = TestSession.query.get(test_session_id)
    gender = None
    if session and session.user_id_fk:
        user = session.user_id_fk
        if hasattr(user, "gender") and user.gender:
            gender = "F" if str(user.gender).lower() in ("female", "f", "1") else "M"

    probs = []
    for inp in inputs:
        prob = _predict(inp.file_path, gender=gender)
        probs.append(prob)

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

    return _predict(x)
