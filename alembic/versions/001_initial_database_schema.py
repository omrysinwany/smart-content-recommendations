"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2024-12-19 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create content_categories table
    op.create_table(
        "content_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["content_categories.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(
        op.f("ix_content_categories_name"), "content_categories", ["name"], unique=False
    )

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, default=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=True),
        sa.Column("total_interactions", sa.Integer(), nullable=False, default=0),
        sa.Column("last_active", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # Create content table
    op.create_table(
        "content",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "content_type",
            sa.Enum(
                "ARTICLE", "VIDEO", "COURSE", "BOOK", "PODCAST", name="contenttype"
            ),
            nullable=False,
        ),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("content_metadata", sa.JSON(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, default=False),
        sa.Column("publish_date", sa.DateTime(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, default=0),
        sa.Column("like_count", sa.Integer(), nullable=False, default=0),
        sa.Column("share_count", sa.Integer(), nullable=False, default=0),
        sa.Column("trending_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("quality_score", sa.Float(), nullable=False, default=0.0),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["content_categories.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_content_title"), "content", ["title"], unique=False)
    op.create_index(
        op.f("ix_content_trending_score"), "content", ["trending_score"], unique=False
    )
    op.create_index(
        op.f("ix_content_created_at"), "content", ["created_at"], unique=False
    )

    # Create interactions table
    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column(
            "interaction_type",
            sa.Enum(
                "VIEW",
                "LIKE",
                "SHARE",
                "COMMENT",
                "SAVE",
                "RATE",
                "CLICK",
                name="interactiontype",
            ),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("interaction_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["content.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interactions_user_id"), "interactions", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_interactions_content_id"), "interactions", ["content_id"], unique=False
    )
    op.create_index(
        op.f("ix_interactions_created_at"), "interactions", ["created_at"], unique=False
    )

    # Create indexes for performance
    op.create_index(
        "ix_content_published_trending",
        "content",
        ["is_published", "trending_score"],
        unique=False,
    )
    op.create_index(
        "ix_interactions_user_content",
        "interactions",
        ["user_id", "content_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_interactions_user_content", table_name="interactions")
    op.drop_index("ix_content_published_trending", table_name="content")

    # Drop tables in reverse order
    op.drop_index(op.f("ix_interactions_created_at"), table_name="interactions")
    op.drop_index(op.f("ix_interactions_content_id"), table_name="interactions")
    op.drop_index(op.f("ix_interactions_user_id"), table_name="interactions")
    op.drop_table("interactions")

    op.drop_index(op.f("ix_content_created_at"), table_name="content")
    op.drop_index(op.f("ix_content_trending_score"), table_name="content")
    op.drop_index(op.f("ix_content_title"), table_name="content")
    op.drop_table("content")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_content_categories_name"), table_name="content_categories")
    op.drop_table("content_categories")
