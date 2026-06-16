"""add_epoch_management

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-06-16 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a1b2c3'
down_revision: Union[str, None] = 'c3d4e5f6a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Create knowledge_epochs
    op.create_table('knowledge_epochs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 2. Create active_epoch_pointer with CHECK constraint for singleton
    op.create_table('active_epoch_pointer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('epoch_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('id = 1', name='chk_active_epoch_pointer_singleton'),
        sa.ForeignKeyConstraint(['epoch_id'], ['knowledge_epochs.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 3. Insert the singleton row
    op.execute("INSERT INTO active_epoch_pointer (id, updated_at) VALUES (1, NOW())")

    # 4. Add foreign keys to existing tables
    op.create_foreign_key('fk_risk_evidence_epoch', 'risk_evidence', 'knowledge_epochs', ['knowledge_epoch_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('fk_recommendation_evidence_epoch', 'recommendation_evidence', 'knowledge_epochs', ['knowledge_epoch_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key('fk_dynamic_thresholds_epoch', 'dynamic_thresholds', 'knowledge_epochs', ['knowledge_epoch_id'], ['id'], ondelete='RESTRICT')

def downgrade() -> None:
    op.drop_constraint('fk_dynamic_thresholds_epoch', 'dynamic_thresholds', type_='foreignkey')
    op.drop_constraint('fk_recommendation_evidence_epoch', 'recommendation_evidence', type_='foreignkey')
    op.drop_constraint('fk_risk_evidence_epoch', 'risk_evidence', type_='foreignkey')
    
    op.drop_table('active_epoch_pointer')
    op.drop_table('knowledge_epochs')
