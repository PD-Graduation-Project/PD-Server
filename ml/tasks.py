"""
RQ Task definitions for ML inference.

These tasks run in separate RQ worker processes, not in the Flask request thread.
"""

import math
import time
from datetime import datetime, timezone
from functools import wraps

import datetime as _dt
import os as _os

from loguru import logger

from config import Config
from models.database import db
from models.test_models import TestGroup, TestSession
from models.user import User

# ── Logging setup ──────────────────────────────────────────────────────────────
logger.remove()
_log_level = _os.environ.get("LOG_LEVEL", "INFO").upper()
logger.add(
    lambda msg: _os.write(2, msg.encode()),
    level=_log_level,
    format="{message}",
)
_os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/worker_{time:YYYY-MM-DD}.log",
    level=_log_level,
    format="{time} | {level:<8} | {name}:{function}:{line} - {message}",
    rotation="1 day",
    retention="7 days",
    filter=lambda record: record["name"].startswith("ml."),
)
# ───────────────────────────────────────────────────────────────────────────────


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

        # Idempotency: completed sessions can be safely skipped.
        if session.ml_status == "completed":
            logger.info(
                f"Session {session_id} already has ml_status=completed, skipping"
            )
            return {
                "success": True,
                "ml_score": session.ml_score,
                "skipped": True,
            }

        # Preserve failure semantics for RQ retries/monitoring.
        if session.ml_status == "failed":
            raise RuntimeError(f"Session {session_id} already has ml_status=failed")

        try:
            started_at = time.time()
            test_type = session.test_type

            logger.info(
                f"Starting inference for session {session_id}, "
                f"type={test_type}, group={session.group_id}, user={session.user_id}"
            )

            if test_type == "tremor":
                ml_score = float(predict_tremor(session_id))
            elif test_type == "drawing":
                ml_score = float(predict_drawing(session_id))
            elif test_type == "voice":
                ml_score = float(predict_voice(session_id))
            else:
                raise ValueError(f"Unknown test type: {test_type}")

            inference_duration = time.time() - started_at
            logger.info(
                f"Inference result for session {session_id}: "
                f"score={ml_score:.4f}, type={test_type}, duration={inference_duration:.2f}s"
            )

            if math.isnan(ml_score) or math.isinf(ml_score):
                raise ValueError(
                    f"Invalid ML score returned: {ml_score} for session {session_id}"
                )

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
                    logger.info(
                        f"Group {group.id} status: completed_tests={set(type_to_score.keys())}, "
                        f"required={required}, all_done={all_done}"
                    )

                    if all_done:
                        group_overall_score = predict_overall(
                            tremor_score=type_to_score["tremor"],
                            drawing_score=type_to_score["drawing"],
                            voice_score=type_to_score["voice"],
                            user_id=session.user_id,
                        )
                        if math.isnan(group_overall_score) or math.isinf(
                            group_overall_score
                        ):
                            raise ValueError(
                                f"Invalid overall score: {group_overall_score} for group {group.id}"
                            )
                        group.overall_score = group_overall_score
                        group.ml_status = "completed"
                        group.ml_job_id = None
                        group.status = "completed"
                        group.completed_at = datetime.now(timezone.utc)
                        db.session.commit()
                        group_completed = True
                        logger.info(
                            f"Group {group.id} completed with overall score {group_overall_score:.4f}"
                        )

            total_duration = time.time() - started_at
            logger.info(
                f"Job complete for session {session_id}: "
                f"score={ml_score:.4f}, group_completed={group_completed}, "
                f"duration={total_duration:.2f}s"
            )

            try:
                from redis import Redis

                r = Redis.from_url(Config.REDIS_URL)
                r.incr("pd:ml:completed_total")
                r.incrbyfloat("pd:ml:duration_sum_seconds", total_duration)
                r.incr("pd:ml:duration_count")

                r.delete(f"cache:v1:user:{session.user_id}:test:{session_id}")
                logger.debug(f"Invalidated cache for test {session_id}")
                if session.group_id:
                    r.delete(
                        f"cache:v1:user:{session.user_id}:group:{session.group_id}"
                    )
                    logger.debug(f"Invalidated cache for group {session.group_id}")

                r.close()
            except Exception as redis_err:
                logger.warning(f"Failed to update Redis counters: {redis_err}")

            return {
                "success": True,
                "ml_score": ml_score,
                "group_completed": group_completed,
                "group_overall_score": group_overall_score,
            }

        except Exception as e:
            logger.exception(f"ML inference failed for session {session_id}: {e}")
            try:
                from redis import Redis

                r = Redis.from_url(Config.REDIS_URL)
                r.incr("pd:ml:failed_total")
                r.close()
            except Exception as redis_err:
                logger.warning(f"Failed to increment failed counter: {redis_err}")
            db.session.rollback()

            session = db.session.get(TestSession, session_id)
            if session:
                logger.info(f"Marking session {session_id} as failed")
                session.ml_score = None
                session.ml_status = "failed"
                session.ml_job_id = None
                try:
                    db.session.commit()
                except Exception as commit_err:
                    logger.warning(f"Failed to mark session {session_id} as failed: {commit_err}")
                    db.session.rollback()

            if session and session.group_id:
                group = db.session.get(TestGroup, session.group_id)
                if group:
                    logger.info(f"Marking group {group.id} as failed due to session {session_id}")
                    group.ml_status = "failed"
                    group.ml_job_id = None
                    try:
                        db.session.commit()
                    except Exception as commit_err:
                        logger.warning(f"Failed to mark group {group.id} as failed: {commit_err}")
                        db.session.rollback()

            try:
                from redis import Redis

                r = Redis.from_url(Config.REDIS_URL)
                r.delete(f"cache:v1:user:{session.user_id}:test:{session_id}")
                logger.debug(f"Invalidated cache for failed test {session_id}")
                r.close()
            except Exception as redis_err:
                logger.warning(f"Failed to invalidate cache for failed session: {redis_err}")

            raise
