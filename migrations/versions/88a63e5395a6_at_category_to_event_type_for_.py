"""at category to event type for convenience

Revision ID: 88a63e5395a6
Revises: cb9300a49c91
Create Date: 2024-11-11 14:40:54.955147

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '88a63e5395a6'
down_revision = 'cb9300a49c91'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('local_plan_event_type', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_category', postgresql.ENUM('ESTIMATED_REGULATION_18', 'ESTIMATED_REGULATION_19', 'ESTIMATED_EXAMINATION_AND_ADOPTION', 'REGULATION_18', 'REGULATION_19', 'PLANNING_INSPECTORATE_EXAMINATION', 'PLANNING_INSPECTORATE_FINDINGS', name='eventcategory', create_type=False), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('local_plan_event_type', schema=None) as batch_op:
        batch_op.drop_column('event_category')

    # ### end Alembic commands ###