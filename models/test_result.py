"""Test Result Model with tremor movements support."""

from datetime import datetime
from enum import Enum
from models.database import db
import json


class TestStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TestResult(db.Model):
    __tablename__ = "test_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Test scores
    tremor_score = db.Column(db.Float, nullable=True)  # From tremor test
    drawing_score = db.Column(db.Float, nullable=True)  # From drawing test
    speech_score = db.Column(db.Float, nullable=True)  # From speech test
    pd_probability = db.Column(db.Float, nullable=True)  # Overall PD probability

    # Tremor test protocol - stores the movements performed
    tremor_movements_json = db.Column(db.Text, nullable=True)  # JSON string

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at = db.Column(db.DateTime)

    def __init__(self, user_id, tremor_movements=None):
        self.user_id = user_id
        if tremor_movements:
            self.tremor_movements = tremor_movements

    @property
    def tremor_movements(self):
        """Get tremor movements as Python list."""
        if self.tremor_movements_json:
            return json.loads(self.tremor_movements_json)
        return None

    @tremor_movements.setter
    def tremor_movements(self, movements):
        """Set tremor movements from Python list."""
        if movements:
            self.tremor_movements_json = json.dumps(movements)
        else:
            self.tremor_movements_json = None

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tremor_score": self.tremor_score,
            "drawing_score": self.drawing_score,
            "speech_score": self.speech_score,
            "pd_probability": self.pd_probability,
            "tremor_movements": self.tremor_movements,  # Uses property getter
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }
