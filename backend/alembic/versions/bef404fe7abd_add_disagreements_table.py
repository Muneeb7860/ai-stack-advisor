"""add disagreements table — "Challenge This Pick" widget (docs/challenge-this-pick-spec.md)

Revision ID: bef404fe7abd
Revises: b6376436f359
Create Date: 2026-08-30 00:00:00.000000

Hand-written, not `alembic revision --autogenerate`'d — no live docker-managed Postgres
instance for this project was reachable in the environment this was authored in (colima/docker
daemon not running). Mirrors the existing initial migration's exact style/column types for the
new `disagreements` table, matching `models.Disagreement` field-for-field. Run
`alembic upgrade head` against a real dev DB and re-diff with `alembic check`
(or a fresh `--autogenerate` pass) before trusting this in production if you want a second
confirmation it matches models.py exactly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'bef404fe7abd'
down_revision: Union[str, Sequence[str], None] = 'b6376436f359'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('disagreements',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('analysis_id', sa.UUID(), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('current_pick', sa.Text(), nullable=False),
    sa.Column('proposed_alternative', sa.Text(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_disagreements_analysis_id'), 'disagreements', ['analysis_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_disagreements_analysis_id'), table_name='disagreements')
    op.drop_table('disagreements')
