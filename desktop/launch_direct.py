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
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    load_dotenv(root / '.env')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    for args in [('scripts.setup_local',), ('alembic', 'upgrade', 'head'), ('scripts.seed',)]:
        subprocess.run([sys.executable, '-m', *args], cwd=root, check=True, creationflags=flags)
    from backend.app.main import app
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8000, log_level='warning'))
    import threading
    thread = threading.Thread(target=server.run, daemon=True)
    try:
        already_running = httpx.get('http://127.0.0.1:8000/health', timeout=2, trust_env=False).json() == {
            'status': 'ok', 'database': 'postgresql'}
    except (httpx.RequestError, ValueError):
        already_running = False
    if not already_running:
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
        if not already_running:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == '__main__':
    runtime = Path(__file__).resolve().parents[1] / '.runtime'
    runtime.mkdir(exist_ok=True)
    with (runtime / 'direct-launch.log').open('w', encoding='utf-8') as log:
        sys.stdout = sys.stderr = log
        try:
            raise SystemExit(main())
        except Exception:
            import traceback
            traceback.print_exc()
            log.flush()
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,
                'تعذر تشغيل التطبيق. تفاصيل الخطأ في .runtime/direct-launch.log', 'MediLink NFC', 16)
            raise SystemExit(1)
