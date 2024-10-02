"""set current date for entry_date

Revision ID: b5cc1e704c5d
Revises: bd14ce5152df
Create Date: 2024-10-02 13:29:27.773107

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b5cc1e704c5d"
down_revision = "bd14ce5152df"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE local_plan_document ALTER COLUMN entry_date SET DEFAULT CURRENT_DATE;"
    )


def downgrade():
    op.execute("ALTER TABLE local_plan_document ALTER COLUMN entry_date DROP DEFAULT;")
