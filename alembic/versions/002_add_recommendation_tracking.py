"""Add recommendation tracking tables

Revision ID: 002
Revises: 001
Create Date: 2024-01-23 12:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create recommendation_logs table
    op.create_table(
        "recommendation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("algorithm_name", sa.String(length=50), nullable=False),
        sa.Column("recommendation_score", sa.Float(), nullable=False),
        sa.Column("position_in_results", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("algorithm_version", sa.String(length=20), nullable=True),
        sa.Column("algorithm_metadata", sa.JSON(), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=True),
        sa.Column("interaction_timestamp", sa.DateTime(), nullable=True),
        sa.Column("time_to_interaction_seconds", sa.Float(), nullable=True),
        sa.Column("ab_test_group", sa.String(length=50), nullable=True),
        sa.Column("ab_test_variant", sa.String(length=50), nullable=True),
        sa.Column("generation_time_ms", sa.Float(), nullable=True),
        sa.Column("cache_hit", sa.Boolean(), nullable=True),
        sa.Column("context_data", sa.JSON(), nullable=True),
        sa.Column("explanation_shown", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
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

    # Create indexes for recommendation_logs
    op.create_index(
        "ix_recommendation_logs_user_id",
        "recommendation_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_logs_content_id",
        "recommendation_logs",
        ["content_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_logs_algorithm_name",
        "recommendation_logs",
        ["algorithm_name"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_logs_session_id",
        "recommendation_logs",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_logs_outcome",
        "recommendation_logs",
        ["outcome"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_logs_ab_test_group",
        "recommendation_logs",
        ["ab_test_group"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_logs_created_at",
        "recommendation_logs",
        ["created_at"],
        unique=False,
    )

    # Create algorithm_performance_metrics table
    op.create_table(
        "algorithm_performance_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("algorithm_name", sa.String(length=50), nullable=False),
        sa.Column("algorithm_version", sa.String(length=20), nullable=True),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("total_recommendations", sa.Integer(), nullable=True),
        sa.Column("total_interactions", sa.Integer(), nullable=True),
        sa.Column("click_through_rate", sa.Float(), nullable=True),
        sa.Column("like_rate", sa.Float(), nullable=True),
        sa.Column("save_rate", sa.Float(), nullable=True),
        sa.Column("share_rate", sa.Float(), nullable=True),
        sa.Column("dismissal_rate", sa.Float(), nullable=True),
        sa.Column("avg_recommendation_score", sa.Float(), nullable=True),
        sa.Column("avg_time_to_interaction", sa.Float(), nullable=True),
        sa.Column("avg_generation_time_ms", sa.Float(), nullable=True),
        sa.Column("cache_hit_rate", sa.Float(), nullable=True),
        sa.Column("unique_content_recommended", sa.Integer(), nullable=True),
        sa.Column("content_catalog_coverage", sa.Float(), nullable=True),
        sa.Column("ab_test_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for algorithm_performance_metrics
    op.create_index(
        "ix_algorithm_performance_metrics_algorithm_name",
        "algorithm_performance_metrics",
        ["algorithm_name"],
        unique=False,
    )
    op.create_index(
        "ix_algorithm_performance_metrics_date",
        "algorithm_performance_metrics",
        ["date"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index(
        "ix_algorithm_performance_metrics_date",
        table_name="algorithm_performance_metrics",
    )
    op.drop_index(
        "ix_algorithm_performance_metrics_algorithm_name",
        table_name="algorithm_performance_metrics",
    )
    op.drop_index("ix_recommendation_logs_created_at", table_name="recommendation_logs")
    op.drop_index(
        "ix_recommendation_logs_ab_test_group", table_name="recommendation_logs"
    )
    op.drop_index("ix_recommendation_logs_outcome", table_name="recommendation_logs")
    op.drop_index("ix_recommendation_logs_session_id", table_name="recommendation_logs")
    op.drop_index(
        "ix_recommendation_logs_algorithm_name", table_name="recommendation_logs"
    )
    op.drop_index("ix_recommendation_logs_content_id", table_name="recommendation_logs")
    op.drop_index("ix_recommendation_logs_user_id", table_name="recommendation_logs")

    # Drop tables
    op.drop_table("algorithm_performance_metrics")
    op.drop_table("recommendation_logs")
