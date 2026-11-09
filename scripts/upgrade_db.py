"""Upgrade the database, adopting a complete pre-Alembic schema when present."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from backend.app.db.models import Base
from backend.app.db.session import engine


ROOT = Path(__file__).resolve().parents[1]


def main():
    config = Config(str(ROOT / 'alembic.ini'))
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    expected = set(Base.metadata.tables)

    if 'alembic_version' not in existing:
        present = expected & existing
        if present and expected <= existing:
            # This database predates Alembic but already has the full app schema.
            command.stamp(config, 'head')
        elif present:
            missing = ', '.join(sorted(expected - existing))
            raise RuntimeError(
                'Database has an incomplete existing schema; refusing to modify it. '
                f'Missing tables: {missing}'
            )

    command.upgrade(config, 'head')


if __name__ == '__main__':
    main()
