"""Store Instagram drafts across ECS tasks."""
from alembic import op

revision = "0002_instagram_drafts"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE instagram_drafts (
            id varchar(64) PRIMARY KEY,
            owner_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            state_hash varchar(64) UNIQUE,
            image_key varchar(64) UNIQUE NOT NULL,
            image bytea,
            caption varchar(2200) NOT NULL,
            phase varchar(20) NOT NULL,
            expires_at timestamptz NOT NULL,
            notice text,
            media_id text
        )
    """)
    op.execute("CREATE INDEX instagram_drafts_expiration ON instagram_drafts (expires_at)")


def downgrade():
    op.drop_table("instagram_drafts")
