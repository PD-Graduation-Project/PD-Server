"""Utility functions for test processing."""
import os
import uuid
import random
from datetime import datetime
from config import Config


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


def calculate_progress(test_result):
    """Calculate test completion progress."""
    completed_tests = 0
    if test_result.tremor_score is not None:
        completed_tests += 1
    if test_result.drawing_score is not None:
        completed_tests += 1
    if test_result.speech_score is not None:
        completed_tests += 1

    return {
        "completed": completed_tests,
        "total": 3,
        "percentage": (completed_tests / 3) * 100 if completed_tests > 0 else 0,
    }


def get_test_status(test_result):
    """Get the status of a test."""
    if test_result.completed_at:
        return "completed"
    
    completed_tests = sum([
        test_result.tremor_score is not None,
        test_result.drawing_score is not None,
        test_result.speech_score is not None
    ])
    
    if completed_tests > 0:
        return "in_progress"
    
    return "not_started"


def update_pd_probability(test_result):
    """Calculate and update overall PD probability."""
    scores = [
        s
        for s in [test_result.tremor_score, test_result.drawing_score, test_result.speech_score]
        if s is not None
    ]
    if scores:
        test_result.pd_probability = sum(scores) / len(scores)