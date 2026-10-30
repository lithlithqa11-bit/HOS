from alembic import context
from sqlalchemy import create_engine, pool
from backend.app.core.config import settings
from backend.app.db.models import Base

config = context.config
target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(url=settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(settings().database_url, poolclass=pool.NullPool, connect_args={'connect_timeout': 5})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
