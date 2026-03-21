"""Add cascade delete constraints to test tables

Revision ID: b12345678901
Revises: acf87bf11a4a
Create Date: 2026-03-19 01:50:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b12345678901"
down_revision = "acf87bf11a4a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE test_sessions "
        "DROP CONSTRAINT IF EXISTS test_sessions_group_id_fkey, "
        "ADD CONSTRAINT test_sessions_group_id_fkey "
        "FOREIGN KEY (group_id) REFERENCES test_groups(id) ON DELETE CASCADE"
    )

    op.execute(
        "ALTER TABLE test_inputs "
        "DROP CONSTRAINT IF EXISTS test_inputs_test_session_id_fkey, "
        "ADD CONSTRAINT test_inputs_test_session_id_fkey "
        "FOREIGN KEY (test_session_id) REFERENCES test_sessions(id) ON DELETE CASCADE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE test_sessions "
        "DROP CONSTRAINT IF EXISTS test_sessions_group_id_fkey, "
        "ADD CONSTRAINT test_sessions_group_id_fkey "
        "FOREIGN KEY (group_id) REFERENCES test_groups(id)"
    )

    op.execute(
        "ALTER TABLE test_inputs "
        "DROP CONSTRAINT IF EXISTS test_inputs_test_session_id_fkey, "
        "ADD CONSTRAINT test_inputs_test_session_id_fkey "
        "FOREIGN KEY (test_session_id) REFERENCES test_sessions(id)"
    )
