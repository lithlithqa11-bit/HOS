"""Destructive test setup is restricted to an explicitly named *_test database."""
# ruff: noqa: E402 -- configure isolated database before importing application modules
import os
from pathlib import Path
import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')
source = os.environ.get('TEST_DATABASE_URL') or os.environ.get('DATABASE_URL', '').rsplit('/', 1)[0] + '/medilink_test'
if not source.startswith('postgresql+psycopg://') or not source.rsplit('/', 1)[-1].endswith('_test'):
    raise RuntimeError('Integration tests require PostgreSQL database with a name ending in _test')
os.environ['DATABASE_URL'] = source

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from backend.app.db.session import engine, SessionLocal
from backend.app.db.models import Base
from backend.app.main import create_app
from scripts.seed import seed


@pytest.fixture(scope='session', autouse=True)
def migrated_database():
    command.upgrade(Config('alembic.ini'), 'head')


@pytest.fixture
def client():
    with engine.begin() as connection:
        names = ', '.join('"' + table.name + '"' for table in Base.metadata.sorted_tables)
        connection.execute(text(f'TRUNCATE {names} RESTART IDENTITY CASCADE'))
    with SessionLocal.begin() as db:
        seed(db, os.environ['DEMO_PASSWORD'])
    with TestClient(create_app()) as api:
        yield api


@pytest.fixture
def auth(client):
    def headers(role='receptionist', hospital='a'):
        response = client.post('/api/auth/login', json={'username': f'{role}.{hospital}',
                                                       'password': os.environ['DEMO_PASSWORD']})
        assert response.status_code == 200, response.text
        return {'Authorization': 'Bearer ' + response.json()['access_token']}
    return headers
