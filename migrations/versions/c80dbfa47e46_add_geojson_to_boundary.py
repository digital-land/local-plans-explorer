"""add geojson to boundary

Revision ID: c80dbfa47e46
Revises: b5cc1e704c5d
Create Date: 2024-10-04 12:33:31.825687

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c80dbfa47e46"
down_revision = "b5cc1e704c5d"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("local_plan_boundary", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("local_plan_boundary", schema=None) as batch_op:
        batch_op.drop_column("geojson")

    # ### end Alembic commands ###
