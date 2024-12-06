"""remap relationship from local plan to events

Revision ID: b58824f7c7b9
Revises: 5dd5f6ec099a
Create Date: 2024-12-06 16:54:05.320551

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b58824f7c7b9'
down_revision = '5dd5f6ec099a'
branch_labels = None
depends_on = None


def upgrade():
    # Add local_plan_reference column to local_plan_event
    op.add_column(
        'local_plan_event',
        sa.Column('local_plan_reference', sa.Text(), nullable=True)
    )

    # Copy local_plan references from local_plan_timetable to local_plan_event
    op.execute(
        """
        UPDATE local_plan_event
        SET local_plan_reference = (
            SELECT local_plan
            FROM local_plan_timetable
            WHERE local_plan_timetable.reference = local_plan_event.local_plan_timetable
        )
        """
    )

    # Make local_plan_reference not nullable after data migration
    op.alter_column('local_plan_event', 'local_plan_reference',
                    existing_type=sa.Text(),
                    nullable=False)

    # Drop the foreign key constraint from local_plan_event to local_plan_timetable
    op.drop_constraint(
        'local_plan_event_local_plan_timetable_fkey',
        'local_plan_event',
        type_='foreignkey'
    )

    # Drop the local_plan_timetable column from local_plan_event
    op.drop_column('local_plan_event', 'local_plan_timetable')

    # Rename local_plan_event table to local_plan_timetable
    op.rename_table('local_plan_event', 'local_plan_timetable_new')

    # Drop the old local_plan_timetable table
    op.drop_table('local_plan_timetable')

    # Rename the new table to local_plan_timetable
    op.rename_table('local_plan_timetable_new', 'local_plan_timetable')

    # Add foreign key from local_plan_timetable to local_plan
    op.create_foreign_key(
        'local_plan_timetable_local_plan_fkey',
        'local_plan_timetable',
        'local_plan',
        ['local_plan_reference'],
        ['reference']
    )


def downgrade():
    # Create the original local_plan_timetable table
    op.create_table(
        'local_plan_timetable',
        sa.Column('entry_date', sa.Date(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('reference', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('local_plan', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['local_plan'], ['local_plan.reference']),
        sa.PrimaryKeyConstraint('reference')
    )

    # Rename current local_plan_timetable back to local_plan_event
    op.rename_table('local_plan_timetable', 'local_plan_event')

    # Add back the local_plan_timetable column to local_plan_event
    op.add_column(
        'local_plan_event',
        sa.Column('local_plan_timetable', sa.Text(), nullable=True)
    )

    # Drop the foreign key to local_plan
    op.drop_constraint(
        'local_plan_event_local_plan_fkey',
        'local_plan_event',
        type_='foreignkey'
    )

    # Drop the local_plan_reference column
    op.drop_column('local_plan_event', 'local_plan_reference')

    # Create foreign key from local_plan_event to local_plan_timetable
    op.create_foreign_key(
        'local_plan_event_local_plan_timetable_fkey',
        'local_plan_event',
        'local_plan_timetable',
        ['local_plan_timetable'],
        ['reference']
    )
