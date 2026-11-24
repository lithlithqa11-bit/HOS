from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.config import settings

engine = create_engine(
    settings().database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={'connect_timeout': 10, 'prepare_threshold': None},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
