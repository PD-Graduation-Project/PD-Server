"""
RQ Task definitions for ML inference.

These tasks run in separate RQ worker processes, not in the Flask request thread.
"""

from datetime import datetime, timezone

from loguru import logger

from config import Config
from models.database import db
from models.test_models import TestGroup, TestSession
from models.user import User


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
                logger.warning(
                    f"Unknown test type {test_type} for session {session_id}"
                )

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
            session.ml_score = None
            session.ml_status = "failed"
            session.ml_job_id = None
            db.session.commit()

            if session.group_id:
                group = db.session.get(TestGroup, session.group_id)
                if group:
                    group.ml_status = "failed"
                    group.ml_job_id = None
                    db.session.commit()

            return {"success": False, "error": str(e)}
