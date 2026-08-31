"""add harness_feedback table — Harness Readiness feedback capture
(docs/harness-engineering/HARNESS_FEEDBACK_SCOPE.md)

Revision ID: c91d4a7e2f18
Revises: bef404fe7abd
Create Date: 2026-08-31 00:00:00.000000

Hand-written, not `alembic revision --autogenerate`'d — same reason as the disagreements
migration this follows: no live docker-managed Postgres for this project was reachable in the
environment this was authored in. Mirrors the existing migrations' exact style/column types,
matching `models.HarnessFeedback` field-for-field. Run `alembic upgrade head` against a real dev
DB and re-diff with `alembic check` (or a fresh `--autogenerate` pass) before trusting this in
production if you want a second confirmation it matches models.py exactly.

Note the deliberate absence of a ForeignKeyConstraint, unlike every other table here that
references an analysis: a harness self-audit has no Analysis row and must not create one (an
Analysis is a product requirement — input text plus detected signals — which a self-audit of a
team's own process definitionally is not). See the model docstring for the full rationale.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c91d4a7e2f18'
down_revision: Union[str, Sequence[str], None] = 'bef404fe7abd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('harness_feedback',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('total', sa.Integer(), nullable=False),
    sa.Column('band', sa.String(length=64), nullable=False),
    sa.Column('answers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('helpful', sa.Boolean(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('harness_feedback')
