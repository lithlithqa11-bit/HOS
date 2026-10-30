"""Run the complete demo against a real temporary HTTP server, preserving demo data."""
import os
from pathlib import Path
import subprocess
import sys
import time
import httpx


def main():
    runtime = Path('.runtime')
    runtime.mkdir(exist_ok=True)
    env = os.environ.copy()
    env['API_URL'] = 'http://127.0.0.1:18002'
    with (runtime / 'demo-api.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app',
                                    '--host', '127.0.0.1', '--port', '18002'],
                                   env=env, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            for _ in range(80):
                try:
                    if httpx.get(env['API_URL'] + '/health', timeout=.5, trust_env=False).status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                if process.poll() is not None:
                    raise RuntimeError('Demo API exited; see .runtime/demo-api.log')
                time.sleep(.1)
            else:
                raise RuntimeError('Demo API startup timed out')
            subprocess.run([sys.executable, '-m', 'scripts.demo_workflow'], env=env, check=True)
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
