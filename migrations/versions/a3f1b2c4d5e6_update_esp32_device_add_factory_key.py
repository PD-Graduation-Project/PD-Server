"""Update ESP32Device: add factory_api_key, make user_id nullable

Revision ID: a3f1b2c4d5e6
Revises: 9cdf170d9090
Create Date: 2026-02-10 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a3f1b2c4d5e6"
down_revision = "9cdf170d9090"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("esp32_devices", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "factory_api_key",
                sa.String(length=255),
                nullable=False,
                server_default="",
            )
        )
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column(
            "api_key", existing_type=sa.String(length=255), nullable=True
        )
        batch_op.create_index("idx_esp32_api_key", ["api_key"], unique=False)
        batch_op.create_index(
            "idx_esp32_factory_api_key", ["factory_api_key"], unique=False
        )


def downgrade():
    with op.batch_alter_table("esp32_devices", schema=None) as batch_op:
        batch_op.drop_index("idx_esp32_factory_api_key")
        batch_op.drop_index("idx_esp32_api_key")
        batch_op.alter_column(
            "api_key", existing_type=sa.String(length=255), nullable=False
        )
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("factory_api_key")
