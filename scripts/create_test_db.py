"""Create an isolated *_test database using the configured PostgreSQL account."""
import os
from dotenv import load_dotenv
import psycopg
from sqlalchemy.engine import make_url


def main():
    load_dotenv()
    url = make_url(os.environ['DATABASE_URL'])
    if url.get_backend_name() != 'postgresql':
        raise ValueError('PostgreSQL only')
    target = url.set(database='medilink_test', drivername='postgresql')
    admin = target.set(database='postgres').render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True, connect_timeout=5) as connection:
        if not connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', ('medilink_test',)).fetchone():
            connection.execute('CREATE DATABASE medilink_test')
    print('medilink_test is ready; no existing rows changed.')


if __name__ == '__main__':
    main()
