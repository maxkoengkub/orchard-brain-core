"""add_knowledge_sources

Revision ID: a1b2c3d4e5f6
Revises: b40f64e0d455
Create Date: 2026-06-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b40f64e0d455'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    trust_tier_enum = postgresql.ENUM('TIER_1_EMPIRICAL', 'TIER_2_PEER_REVIEWED', 'TIER_3_EXTENSION', 'TIER_4_PRIOR', name='trusttier')
    trust_tier_enum.create(op.get_bind(), checkfirst=True)

    op.create_table('knowledge_sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=False),
        sa.Column('source_version', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('trust_tier', trust_tier_enum, nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('knowledge_sources')
    trust_tier_enum = postgresql.ENUM('TIER_1_EMPIRICAL', 'TIER_2_PEER_REVIEWED', 'TIER_3_EXTENSION', 'TIER_4_PRIOR', name='trusttier')
    trust_tier_enum.drop(op.get_bind(), checkfirst=True)
