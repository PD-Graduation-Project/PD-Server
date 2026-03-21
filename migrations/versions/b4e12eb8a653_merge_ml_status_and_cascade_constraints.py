"""Merge ml_status and cascade constraints

Revision ID: b4e12eb8a653
Revises: 1ca4fc21024a, b12345678901
Create Date: 2026-03-19 03:57:30.271445

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b4e12eb8a653"
down_revision = ("1ca4fc21024a", "b12345678901")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
