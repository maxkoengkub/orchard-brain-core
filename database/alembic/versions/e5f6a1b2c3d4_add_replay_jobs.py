"""add_replay_jobs

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-06-16 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e5f6a1b2c3d4'
down_revision: Union[str, None] = 'd4e5f6a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create replay_jobs table
    op.create_table('replay_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('target_epoch_id', sa.Integer(), nullable=False),
        sa.Column('start_telemetry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_telemetry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['target_epoch_id'], ['knowledge_epochs.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create replay_results table
    op.create_table('replay_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('telemetry_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('health_score', sa.Integer(), nullable=True),
        sa.Column('water_stress', sa.Integer(), nullable=True),
        sa.Column('nutrient_stress', sa.Integer(), nullable=True),
        sa.Column('risks_count', sa.Integer(), nullable=True),
        sa.Column('recommendations_count', sa.Integer(), nullable=True),
        sa.Column('evaluation_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['replay_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('replay_results')
    op.drop_table('replay_jobs')
