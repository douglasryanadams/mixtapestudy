"""Adds token_expires and timestamps to time columns.

Revision ID: 93656c0b8262
Revises: 07cba935dd4b
Create Date: 2024-10-06 23:15:53.926103

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "93656c0b8262"
down_revision: Union[str, None] = "07cba935dd4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "user",
        sa.Column(
            "token_expires",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.execute('UPDATE "user" SET token_expires = NOW()')
    op.alter_column("user", "token_expires", nullable=False)
    op.alter_column(
        "user",
        "updated",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "user",
        "created",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "user",
        "created",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
    )
    op.alter_column(
        "user",
        "updated",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
    )
    op.drop_column("user", "token_expires")
    # ### end Alembic commands ###