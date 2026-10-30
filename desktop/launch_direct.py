"""Direct GUI launcher used by the Windows EXE; it never opens PowerShell."""
import os
import subprocess
import sys
import time
from pathlib import Path
import httpx
import uvicorn
from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    load_dotenv(root / '.env')
    subprocess.run([sys.executable, '-m', 'scripts.setup_local'], cwd=root, check=True)
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=root, check=True)
    subprocess.run([sys.executable, '-m', 'scripts.seed'], cwd=root, check=True)
    server = uvicorn.Server(uvicorn.Config('backend.app.main:app', host='127.0.0.1', port=8000, log_level='warning'))
    import threading
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(80):
        try:
            if httpx.get('http://127.0.0.1:8000/health', timeout=.5, trust_env=False).status_code == 200:
                break
        except httpx.RequestError:
            time.sleep(.1)
    else:
        raise RuntimeError('FastAPI did not become ready')
    from desktop.main import main as desktop_main
    try:
        return desktop_main()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
