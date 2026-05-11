from datetime import datetime

from models.database import db


class TestGroup(db.Model):
    """
    Groups one tremor, one drawing, and one voice TestSession together
    into a single assessment session. Created by the mobile app before
    any individual tests are started.
    """

    __tablename__ = "test_groups"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # "pending" → "in_progress" (first test created) → "completed" (all 3 done)
    status = db.Column(db.String(20), nullable=False, default="pending")

    # Set once all three tests are completed, via predict_overall()
    overall_score = db.Column(db.Float, nullable=True)

    # ML inference status for the entire group
    ml_status = db.Column(db.String(20), nullable=True)  # processing, completed, failed
    ml_job_id = db.Column(db.String(50), nullable=True)  # RQ job ID

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationship back to the three child test sessions
    tests = db.relationship(
        "TestSession",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    user = db.relationship("User", backref="test_groups")

    __table_args__ = (
        db.Index("idx_test_group_user_id", "user_id"),
        db.Index("idx_test_group_user_status", "user_id", "status"),
    )


class TestSession(db.Model):
    __tablename__ = "test_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # FK to the parent group — nullable so old rows and standalone tests still work
    # at the DB level, but the API enforces it for new POSTs.
    group_id = db.Column(
        db.Integer,
        db.ForeignKey("test_groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    test_type = db.Column(db.String(20), nullable=False)  # tremor, drawing, voice
    status = db.Column(
        db.String(20), nullable=False, default="pending"
    )  # pending, in_progress, completed
    device_source = db.Column(db.String(20), nullable=True)
    config = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    ml_score = db.Column(db.Float, nullable=True)
    ml_status = db.Column(db.String(20), nullable=True)  # processing, completed, failed
    ml_job_id = db.Column(db.String(50), nullable=True)  # RQ job ID

    user_id_fk = db.relationship("User", backref="test_sessions")

    group = db.relationship("TestGroup", back_populates="tests")

    inputs = db.relationship(
        "TestInput",
        back_populates="test_session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.Index("idx_test_session_user_status", "user_id", "status"),
        db.Index("idx_test_session_user_type", "user_id", "test_type"),
    )


class TestInput(db.Model):
    __tablename__ = "test_inputs"

    id = db.Column(db.Integer, primary_key=True)
    test_session_id = db.Column(
        db.Integer,
        db.ForeignKey("test_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_type = db.Column(db.String(30), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    test_session = db.relationship("TestSession", back_populates="inputs")

    __table_args__ = (
        db.Index("idx_test_input_session_type", "test_session_id", "input_type"),
    )


class ESP32Device(db.Model):
    __tablename__ = "esp32_devices"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    factory_api_key = db.Column(db.String(255), nullable=False)
    api_key = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(100), nullable=True)
    is_connected = db.Column(db.Boolean, default=False)
    last_seen_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="esp32_devices")

    __table_args__ = (
        db.Index("idx_esp32_device_id", "device_id"),
        db.Index("idx_esp32_user_id", "user_id"),
        db.Index("idx_esp32_api_key", "api_key"),
        db.Index("idx_esp32_factory_api_key", "factory_api_key"),
    )


class ESP32Log(db.Model):
    __tablename__ = "esp32_logs"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(
        db.String(100),
        db.ForeignKey("esp32_devices.device_id", ondelete="SET NULL"),
        nullable=True,
    )
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)
    log_type = db.Column(db.String(50), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.Index("idx_esp32_log_device_time", "device_id", "uploaded_at"),
    )
