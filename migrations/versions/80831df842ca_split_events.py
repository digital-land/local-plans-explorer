"""split events

Revision ID: 80831df842ca
Revises: d8b834bb4294
Create Date: 2024-11-29 15:42:07.665213

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "80831df842ca"
down_revision = "d8b834bb4294"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("local_plan_event", schema=None) as batch_op:
        batch_op.add_column(sa.Column("event_date", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("local_plan_event_type_reference", sa.Text(), nullable=True)
        )
        batch_op.create_foreign_key(
            None,
            "local_plan_event_type",
            ["local_plan_event_type_reference"],
            ["reference"],
        )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("local_plan_event", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.drop_column("local_plan_event_type_reference")
        batch_op.drop_column("event_date")

    # ### end Alembic commands ###