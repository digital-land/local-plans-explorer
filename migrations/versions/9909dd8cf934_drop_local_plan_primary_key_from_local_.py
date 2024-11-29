"""drop local_plan primary key from local plan document

Revision ID: 9909dd8cf934
Revises: 3fb32534880e
Create Date: 2024-11-29 09:43:11.849496

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9909dd8cf934"
down_revision = "3fb32534880e"
branch_labels = None
depends_on = None


def upgrade():
    # First modify document_organisation table
    with op.batch_alter_table("document_organisation", schema=None) as batch_op:
        # Just drop the column - batch_alter_table will handle any existing constraints
        batch_op.drop_column("local_plan_document_local_plan")

    # Now we can safely modify local_plan_document table
    with op.batch_alter_table("local_plan_document", schema=None) as batch_op:
        # Drop the existing primary key
        batch_op.drop_constraint("local_plan_document_pkey", type_="primary")
        # Create new primary key on reference only
        batch_op.create_primary_key("local_plan_document_pkey", ["reference"])

    # Finally create the new foreign key constraint
    with op.batch_alter_table("document_organisation", schema=None) as batch_op:
        batch_op.create_foreign_key(
            None,
            "local_plan_document",
            ["local_plan_document_reference"],
            ["reference"],
        )


def downgrade():
    # First drop the new foreign key
    with op.batch_alter_table("document_organisation", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")

    # Then restore the composite primary key on local_plan_document
    with op.batch_alter_table("local_plan_document", schema=None) as batch_op:
        batch_op.drop_constraint("local_plan_document_pkey", type_="primary")
        batch_op.create_primary_key(
            "local_plan_document_pkey", ["reference", "local_plan"]
        )

    # Finally restore the original foreign key and column
    with op.batch_alter_table("document_organisation", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "local_plan_document_local_plan",
                sa.TEXT(),
                autoincrement=False,
                nullable=False,
            )
        )
        batch_op.create_foreign_key(
            "document_organisation_local_plan_document_reference_local__fkey",
            "local_plan_document",
            ["local_plan_document_reference", "local_plan_document_local_plan"],
            ["reference", "local_plan"],
        )
