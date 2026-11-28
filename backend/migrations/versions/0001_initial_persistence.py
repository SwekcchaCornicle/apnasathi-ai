"""Create ApnaSathi persistence schema and pgvector extension."""
from alembic import op
from database.base import Base
import database.models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    daily_tables = {"daily_actions", "reminders", "daily_tasks", "shopping_lists", "expenses", "meal_plans", "message_drafts", "google_calendar_credentials", "google_oauth_states"}
    legacy_tables = [table for name, table in Base.metadata.tables.items() if name not in daily_tables]
    Base.metadata.create_all(bind=op.get_bind(), tables=legacy_tables)

def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
