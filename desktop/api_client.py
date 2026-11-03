"""HTTP-only desktop boundary. Never imports backend database modules."""
import httpx
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url='http://127.0.0.1:8000'):
        self.base_url = base_url.rstrip('/')
        self.token = None

    def request(self, method, path, data=None):
        headers = {'Authorization': f'Bearer {self.token}'} if self.token else {}
        try:
            response = httpx.request(method, self.base_url + path, json=data, headers=headers,
                                     timeout=12, follow_redirects=False, trust_env=False)
        except httpx.RequestError as error:
            raise ApiError('تعذر الاتصال بالخادم. تحقق من تشغيل FastAPI والاتصال ثم أعد المحاولة.') from error
        try:
            body = response.json()
        except ValueError:
            raise ApiError(f'استجابة غير صالحة من الخادم ({response.status_code})') from None
        if response.is_error:
            detail = body.get('detail', 'فشل الطلب')
            if isinstance(detail, list):
                detail = '\n'.join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in detail)
            raise ApiError(str(detail))
        return body


class WorkerSignals(QObject):
    success = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            self.signals.success.emit(self.function())
        except Exception as error:
            self.signals.error.emit(str(error))
        finally:
            self.signals.finished.emit()


class Tasks(QObject):
    """Own workers until completion; all callbacks are delivered on the UI thread."""
    error = Signal(str)
    busy = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pending = set()

    def submit(self, function, callback, failed=None):
        worker = Worker(function)
        self.pending.add(worker)
        worker.signals.success.connect(callback)
        if failed is not None:
            worker.signals.error.connect(failed)
        worker.signals.error.connect(self.error.emit)
        worker.signals.finished.connect(lambda: self._finished(worker))
        self.busy.emit(True)
        self.pool.start(worker)

    def _finished(self, worker):
        self.pending.discard(worker)
        self.busy.emit(bool(self.pending))
