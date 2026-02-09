"""Initial migration for test sessions, inputs, and ESP32 devices

Revision ID: 829038cfab8f
Revises:
Create Date: 2026-02-09 17:39:31.197494

"""

import sqlalchemy as sa
from alembic import op

revision = "829038cfab8f"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "test_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("test_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, default="pending"),
        sa.Column("device_source", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("ml_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_test_session_user_status",
        "test_sessions",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_test_session_user_type",
        "test_sessions",
        ["user_id", "test_type"],
        unique=False,
    )

    op.create_table(
        "test_inputs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_session_id", sa.Integer(), nullable=False),
        sa.Column("input_type", sa.String(length=30), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["test_session_id"],
            ["test_sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_test_input_session_type",
        "test_inputs",
        ["test_session_id", "input_type"],
        unique=False,
    )

    op.create_table(
        "esp32_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("api_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("is_connected", sa.Boolean(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index("idx_esp32_device_id", "esp32_devices", ["device_id"], unique=False)
    op.create_index("idx_esp32_user_id", "esp32_devices", ["user_id"], unique=False)


def downgrade():
    op.drop_index("idx_esp32_user_id", table_name="esp32_devices")
    op.drop_index("idx_esp32_device_id", table_name="esp32_devices")
    op.drop_table("esp32_devices")
    op.drop_index("idx_test_input_session_type", table_name="test_inputs")
    op.drop_table("test_inputs")
    op.drop_index("idx_test_session_user_type", table_name="test_sessions")
    op.drop_index("idx_test_session_user_status", table_name="test_sessions")
    op.drop_table("test_sessions")
