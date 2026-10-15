"""Alembic uses DATABASE_URL; no secrets in migration files or logs."""

from alembic import context

from vericlue_api.core.config import get_settings
from vericlue_api.db.database import Database
from vericlue_api.db.models import Base

config = context.config
url = config.get_main_option("sqlalchemy.url") or get_settings().database_url
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    database = Database(url)
    engine = database.engine
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
