"""Create users and refresh_tokens tables

Revision ID: users_and_tokens
Revises:
Create Date: 2026-03-16 23:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "users_and_tokens"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(length=50), nullable=True),
        sa.Column("pd_appearance_in_kinship", sa.Boolean(), nullable=True),
        sa.Column("pd_appearance_in_first_grade_kinship", sa.Boolean(), nullable=True),
        sa.Column("Q01", sa.Boolean(), nullable=True),
        sa.Column("Q02", sa.Boolean(), nullable=True),
        sa.Column("Q03", sa.Boolean(), nullable=True),
        sa.Column("Q04", sa.Boolean(), nullable=True),
        sa.Column("Q05", sa.Boolean(), nullable=True),
        sa.Column("Q06", sa.Boolean(), nullable=True),
        sa.Column("Q07", sa.Boolean(), nullable=True),
        sa.Column("Q08", sa.Boolean(), nullable=True),
        sa.Column("Q09", sa.Boolean(), nullable=True),
        sa.Column("Q10", sa.Boolean(), nullable=True),
        sa.Column("Q11", sa.Boolean(), nullable=True),
        sa.Column("Q12", sa.Boolean(), nullable=True),
        sa.Column("Q13", sa.Boolean(), nullable=True),
        sa.Column("Q14", sa.Boolean(), nullable=True),
        sa.Column("Q15", sa.Boolean(), nullable=True),
        sa.Column("Q16", sa.Boolean(), nullable=True),
        sa.Column("Q17", sa.Boolean(), nullable=True),
        sa.Column("Q18", sa.Boolean(), nullable=True),
        sa.Column("Q19", sa.Boolean(), nullable=True),
        sa.Column("Q20", sa.Boolean(), nullable=True),
        sa.Column("Q21", sa.Boolean(), nullable=True),
        sa.Column("Q22", sa.Boolean(), nullable=True),
        sa.Column("Q23", sa.Boolean(), nullable=True),
        sa.Column("Q24", sa.Boolean(), nullable=True),
        sa.Column("Q25", sa.Boolean(), nullable=True),
        sa.Column("Q26", sa.Boolean(), nullable=True),
        sa.Column("Q27", sa.Boolean(), nullable=True),
        sa.Column("Q28", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=256), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("device_info", sa.String(length=256), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_refresh_tokens_token_hash"),
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade():
    op.drop_index(op.f("ix_refresh_tokens_token_hash"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
