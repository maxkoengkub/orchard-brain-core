"""add_dynamic_thresholds

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-06-16 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a1b2'
down_revision: Union[str, None] = 'b2c3d4e5f6a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('dynamic_thresholds',
        sa.Column('threshold_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('parameter_name', sa.String(length=100), nullable=False),
        sa.Column('optimal_min', sa.Float(), nullable=True),
        sa.Column('optimal_max', sa.Float(), nullable=True),
        sa.Column('warn_min', sa.Float(), nullable=True),
        sa.Column('warn_max', sa.Float(), nullable=True),
        sa.Column('critical_min', sa.Float(), nullable=True),
        sa.Column('critical_max', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=True),
        sa.Column('knowledge_epoch_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['knowledge_sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('threshold_id')
    )

def downgrade() -> None:
    op.drop_table('dynamic_thresholds')
