from datetime import datetime
from enum import Enum
from models.database import db


class TestStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TestResult(db.Model):
    __tablename__ = "test_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    tremor_score = db.Column(db.Float, nullable=True)  # From tremor test
    drawing_score = db.Column(db.Float, nullable=True)  # From drawing test
    speech_score = db.Column(db.Float, nullable=True)  # From speech test

    overall_score = db.Column(db.Float, nullable=True)  # 0.0 to 1.0

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tremor_score": self.tremor_score,
            "drawing_score": self.drawing_score,
            "speech_score": self.speech_score,
            "overall_score": self.overall_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }
