"""Create isolated local settings and PostgreSQL cluster. No system service changes."""
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    pg = Path(os.environ.get('PG_BIN', r'C:\Program Files\PostgreSQL\18\bin'))
    env_file = ROOT / '.env'
    if not env_file.exists():
        db_password, demo_password = secrets.token_urlsafe(24), secrets.token_urlsafe(15)
        env_file.write_text(
            f'DATABASE_URL=postgresql+psycopg://medilink:{db_password}@127.0.0.1:55432/medilink\n'
            f'JWT_SECRET={secrets.token_urlsafe(48)}\nDEMO_PASSWORD={demo_password}\n'
            'API_URL=http://127.0.0.1:8000\nNFC_PORT=COM6\n'
            f'POSTGRES_USER=medilink\nPOSTGRES_PASSWORD={db_password}\nPOSTGRES_DB=medilink\n',
            encoding='utf-8')
    values = dict(line.split('=', 1) for line in env_file.read_text().splitlines() if '=' in line)
    if ':55432/medilink' not in values['DATABASE_URL']:
        sys.exit('Existing .env uses another database. Use that configuration; nothing changed.')
    data = runtime / 'pgdata'
    if not (data / 'PG_VERSION').exists():
        pw = runtime / 'init_password'
        pw.write_text(values['POSTGRES_PASSWORD'], encoding='ascii')
        try:
            subprocess.run([str(pg / 'initdb.exe'), '-D', str(data), '-U', 'medilink',
                            '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C',
                            '--pwfile', str(pw)], check=True)
        finally:
            pw.unlink(missing_ok=True)
        with (data / 'postgresql.conf').open('a') as config:
            config.write("\nport = 55432\nlisten_addresses = '127.0.0.1'\n")
    status = subprocess.run([str(pg / 'pg_ctl.exe'), '-D', str(data), 'status'], capture_output=True)
    if status.returncode:
        subprocess.run([str(pg / 'pg_ctl.exe'), '-D', str(data), '-l', str(runtime / 'postgres.log'),
                        '-w', 'start'], check=True)
    import psycopg
    admin_url = values['DATABASE_URL'].replace('postgresql+psycopg', 'postgresql').rsplit('/', 1)[0] + '/postgres'
    with psycopg.connect(admin_url, autocommit=True, connect_timeout=5) as connection:
        for name in ('medilink', 'medilink_test'):
            if not connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone():
                connection.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(name)))
    print('PostgreSQL ready at 127.0.0.1:55432; credentials are in ignored .env')


if __name__ == '__main__':
    main()
