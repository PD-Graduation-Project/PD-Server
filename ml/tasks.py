"""
RQ Task definitions for ML inference.

These tasks run in separate RQ worker processes, not in the Flask request thread.
"""

import time
from datetime import datetime, timezone
from functools import wraps

from loguru import logger

from config import Config
from models.database import db
from models.test_models import TestGroup, TestSession
from models.user import User


def with_retry(max_retries=3, delay=1, backoff=2):
    """Decorator to retry on transient errors."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = Exception("Retry failed with no exception")
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait = delay * (backoff**attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {wait}s..."
                        )
                        time.sleep(wait)
            logger.error(f"All {max_retries} attempts failed: {last_error}")
            raise last_error

        return wrapper

    return decorator


@with_retry(max_retries=3, delay=2, backoff=2)
def run_inference(session_id: int) -> dict:
    """
    RQ task: Run ML inference for a completed test session.

    This function runs in a separate RQ worker process, so we must
    push a Flask app context to access the database.

    Args:
        session_id: The ID of the completed TestSession

    Returns:
        dict with keys: success, ml_score, group_completed, group_overall_score
    """
    from flask import Flask

    from ml.overall_model import predict_overall
    from ml.predictor import predict_drawing, predict_tremor, predict_voice

    app = Flask("ml_worker")
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        session = db.session.get(TestSession, session_id)
        if not session:
            logger.error(f"Session {session_id} not found for ML inference")
            return {"success": False, "error": "Session not found"}

        # Idempotency: skip if already completed or failed
        if session.ml_status in ("completed", "failed"):
            logger.info(
                f"Session {session_id} already has ml_status={session.ml_status}, skipping"
            )
            return {
                "success": session.ml_status == "completed",
                "ml_score": session.ml_score,
                "skipped": True,
            }

        try:
            ml_score = None
            test_type = session.test_type

            if test_type == "tremor":
                ml_score = float(predict_tremor(session_id))
            elif test_type == "drawing":
                ml_score = float(predict_drawing(session_id))
            elif test_type == "voice":
                ml_score = float(predict_voice(session_id))
            else:
                raise ValueError(f"Unknown test type: {test_type}")

            # Store the score before trying to commit
            session.ml_score = ml_score
            session.ml_status = "completed"
            session.ml_job_id = None
            db.session.commit()

            group_completed = False
            group_overall_score = None

            if session.group_id:
                group = (
                    db.session.query(TestGroup)
                    .filter_by(id=session.group_id)
                    .with_for_update()
                    .first()
                )

                if group and group.overall_score is None:
                    group_tests = TestSession.query.filter_by(group_id=group.id).all()
                    type_to_score = {
                        t.test_type: t.ml_score
                        for t in group_tests
                        if t.ml_score is not None
                    }
                    required = {"tremor", "drawing", "voice"}

                    all_done = required == set(type_to_score.keys()) and all(
                        t.status == "completed" for t in group_tests
                    )

                    if all_done:
                        group_overall_score = predict_overall(
                            tremor_score=type_to_score["tremor"],
                            drawing_score=type_to_score["drawing"],
                            voice_score=type_to_score["voice"],
                            user_id=session.user_id,
                        )
                        group.overall_score = group_overall_score
                        group.ml_status = "completed"
                        group.ml_job_id = None
                        group.status = "completed"
                        group.completed_at = datetime.now(timezone.utc)
                        db.session.commit()
                        group_completed = True
                        logger.info(
                            f"Group {group.id} completed with overall score {group_overall_score}"
                        )

            logger.info(
                f"Inference completed for session {session_id}, score: {ml_score}"
            )
            return {
                "success": True,
                "ml_score": ml_score,
                "group_completed": group_completed,
                "group_overall_score": group_overall_score,
            }

        except Exception as e:
            logger.exception(f"ML inference failed for session {session_id}: {e}")
            # Rollback first to ensure clean state
            db.session.rollback()

            # Re-fetch session to get fresh state
            session = db.session.get(TestSession, session_id)
            if session:
                session.ml_score = None
                session.ml_status = "failed"
                session.ml_job_id = None
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            if session and session.group_id:
                group = db.session.get(TestGroup, session.group_id)
                if group:
                    group.ml_status = "failed"
                    group.ml_job_id = None
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

            return {"success": False, "error": str(e)}
