import os
from datetime import datetime

from gevent.threadpool import ThreadPoolExecutor
from werkzeug.security import check_password_hash, generate_password_hash

from models.database import db

_bcrypt_pool = ThreadPoolExecutor(max_workers=4)


def _reset_bcrypt_pool() -> None:
    global _bcrypt_pool
    _bcrypt_pool = ThreadPoolExecutor(max_workers=4)


os.register_at_fork(after_in_child=_reset_bcrypt_pool)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Demographic information
    age = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(50), nullable=True)  # accepts "male" or "female"
    pd_appearance_in_kinship = db.Column(db.Boolean, nullable=True)
    pd_appearance_in_first_grade_kinship = db.Column(db.Boolean, nullable=True)

    # Questionnaire responses
    Q01 = db.Column(db.Boolean, nullable=True)
    Q02 = db.Column(db.Boolean, nullable=True)
    Q03 = db.Column(db.Boolean, nullable=True)
    Q04 = db.Column(db.Boolean, nullable=True)
    Q05 = db.Column(db.Boolean, nullable=True)
    Q06 = db.Column(db.Boolean, nullable=True)
    Q07 = db.Column(db.Boolean, nullable=True)
    Q08 = db.Column(db.Boolean, nullable=True)
    Q09 = db.Column(db.Boolean, nullable=True)
    Q10 = db.Column(db.Boolean, nullable=True)
    Q11 = db.Column(db.Boolean, nullable=True)
    Q12 = db.Column(db.Boolean, nullable=True)
    Q13 = db.Column(db.Boolean, nullable=True)
    Q14 = db.Column(db.Boolean, nullable=True)
    Q15 = db.Column(db.Boolean, nullable=True)
    Q16 = db.Column(db.Boolean, nullable=True)
    Q17 = db.Column(db.Boolean, nullable=True)
    Q18 = db.Column(db.Boolean, nullable=True)
    Q19 = db.Column(db.Boolean, nullable=True)
    Q20 = db.Column(db.Boolean, nullable=True)
    Q21 = db.Column(db.Boolean, nullable=True)
    Q22 = db.Column(db.Boolean, nullable=True)
    Q23 = db.Column(db.Boolean, nullable=True)
    Q24 = db.Column(db.Boolean, nullable=True)
    Q25 = db.Column(db.Boolean, nullable=True)
    Q26 = db.Column(db.Boolean, nullable=True)
    Q27 = db.Column(db.Boolean, nullable=True)
    Q28 = db.Column(db.Boolean, nullable=True)

    # Relationship to refresh tokens
    refresh_tokens = db.relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = _bcrypt_pool.submit(generate_password_hash, password).result()

    def check_password(self, password):
        return _bcrypt_pool.submit(check_password_hash, self.password_hash, password).result()

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "age": self.age,
            "height": self.height,
            "weight": self.weight,
            "gender": self.gender,
            "pd_appearance_in_kinship": self.pd_appearance_in_kinship,
            "pd_appearance_in_first_grade_kinship": self.pd_appearance_in_first_grade_kinship,
        }


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token_hash = db.Column(db.String(256), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    revoked = db.Column(db.Boolean, default=False, nullable=False)

    # Device/session tracking (optional but useful)
    device_info = db.Column(db.String(256), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible

    # Relationship back to user
    user = db.relationship("User", back_populates="refresh_tokens")

    def is_valid(self):
        """Check if token is still valid (not expired and not revoked)"""
        return not self.revoked and self.expires_at > datetime.utcnow()
