"""Create daily assistant workflow tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="0002_daily_assistant"
down_revision="0001_initial"
branch_labels=None
depends_on=None

def upgrade():
    u=postgresql.UUID(as_uuid=True); j=postgresql.JSONB()
    op.create_table("google_calendar_credentials", sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),primary_key=True), sa.Column("refresh_token_encrypted",sa.Text(),nullable=False), sa.Column("connected_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_table("google_oauth_states", sa.Column("state_hash",sa.String(64),primary_key=True), sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False), sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False), sa.Column("used_at",sa.DateTime(timezone=True)))
    op.create_table("daily_actions",sa.Column("id",u,primary_key=True),sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("intent",sa.String(48),nullable=False),sa.Column("payload",j,nullable=False),sa.Column("status",sa.String(24),nullable=False),sa.Column("result",j,nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_daily_actions_user_status","daily_actions",["user_id","status"])
    op.create_table("reminders",sa.Column("id",u,primary_key=True),sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("title",sa.String(200),nullable=False),sa.Column("scheduled_at",sa.DateTime(timezone=True),nullable=False),sa.Column("timezone",sa.String(64),nullable=False),sa.Column("status",sa.String(20),nullable=False))
    op.create_index("ix_reminders_user_due","reminders",["user_id","status","scheduled_at"])
    op.create_table("daily_tasks",sa.Column("id",u,primary_key=True),sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("title",sa.String(240),nullable=False),sa.Column("priority",sa.String(12),nullable=False),sa.Column("status",sa.String(16),nullable=False),sa.Column("due_at",sa.DateTime(timezone=True)))
    op.create_index("ix_daily_tasks_user_status","daily_tasks",["user_id","status"])
    op.create_table("shopping_lists",sa.Column("id",u,primary_key=True),sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(160),nullable=False),sa.Column("items",j,nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_table("expenses",sa.Column("id",u,primary_key=True),sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("amount",sa.Float(),nullable=False),sa.Column("currency",sa.String(3),nullable=False),sa.Column("category",sa.String(64),nullable=False),sa.Column("description",sa.String(240),nullable=False),sa.Column("spent_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_expenses_user_date","expenses",["user_id","spent_at"])
    op.create_table("meal_plans",sa.Column("id",u,primary_key=True),sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("plan_date",sa.DateTime(timezone=True),nullable=False),sa.Column("meal_type",sa.String(20),nullable=False),sa.Column("title",sa.String(200),nullable=False),sa.Column("ingredients",j,nullable=False))
    op.create_index("ix_meal_plans_user_date","meal_plans",["user_id","plan_date"])
    op.create_table("message_drafts",sa.Column("id",u,primary_key=True),sa.Column("user_id",u,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("channel",sa.String(24),nullable=False),sa.Column("recipient",sa.String(160)),sa.Column("body",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))

def downgrade():
    for table in ("google_oauth_states","google_calendar_credentials","message_drafts","meal_plans","expenses","shopping_lists","daily_tasks","reminders","daily_actions"):
        op.drop_table(table)
