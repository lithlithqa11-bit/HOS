from PySide6.QtWidgets import QMessageBox

from desktop.api_client import Tasks
from desktop.nfc_bridge import NFCError
from desktop.screens.core import NFCPage


class FakeWindow:
    nfc_port = 'COM6'

    def __init__(self):
        self.tasks = Tasks()
        self.messages = []
        self.scanned = []

    def has_role(self, *roles):
        return 'receptionist' in roles

    def message(self, text):
        self.messages.append(text)

    def show_scanned(self, data):
        self.scanned.append(data)


def test_read_failure_releases_card_page(qtbot, monkeypatch):
    window = FakeWindow()
    page = NFCPage(window)
    qtbot.addWidget(page)
    failures = []
    window.tasks.error.connect(failures.append)

    def fail(_):
        raise NFCError('انتهت مهلة القراءة')

    monkeypatch.setattr('desktop.nfc_bridge.SerialRC522Reader.read', fail)
    page.scan()
    assert not page.scan_button.isEnabled()
    qtbot.waitUntil(lambda: bool(failures), timeout=3000)
    assert 'انتهت مهلة القراءة' in page.status.text()
    assert page.scan_button.isEnabled() and page.write_button.isEnabled()


def test_api_failure_after_read_releases_card_page(qtbot, monkeypatch):
    window = FakeWindow()
    window.request = lambda method, path, data, done, failed: failed('رمز البطاقة غير مسجل')
    page = NFCPage(window)
    qtbot.addWidget(page)
    monkeypatch.setattr('desktop.nfc_bridge.SerialRC522Reader.read',
                        lambda _: {'token': 'a' * 64})
    page.scan()
    qtbot.waitUntil(lambda: 'رمز البطاقة غير مسجل' in page.status.text(), timeout=3000)
    assert page.scan_button.isEnabled() and page.write_button.isEnabled()


def test_write_failure_keeps_token_for_retry(qtbot, monkeypatch):
    window = FakeWindow()
    page = NFCPage(window)
    qtbot.addWidget(page)
    page.token.setText('a' * 64)
    page.pending_card = (7, 11)
    window.tasks.error.connect(lambda _: None)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)

    def fail(_, token):
        raise NFCError('انتهت مهلة الكتابة')

    monkeypatch.setattr('desktop.nfc_bridge.SerialRC522Reader.write', fail)
    page.write()
    qtbot.waitUntil(lambda: 'انتهت مهلة الكتابة' in page.status.text(), timeout=3000)
    assert page.token.text() == 'a' * 64
    assert page.scan_button.isEnabled() and page.write_button.isEnabled()


def test_prepared_card_writes_and_activates(qtbot, monkeypatch):
    window = FakeWindow()
    window.opened = []
    window.open_patient = window.opened.append
    activated = []

    def request(method, path, data, done, failed):
        activated.append((method, path, data))
        done({'patient_id': 7, 'card_id': 11, 'active': True})

    window.request = request
    page = NFCPage(window)
    qtbot.addWidget(page)
    monkeypatch.setattr('desktop.nfc_bridge.SerialRC522Reader.write',
                        lambda _, token: {'written': token == 'a' * 64})
    page.prepare_and_write({'patient_id': 7, 'card_id': 11, 'token': 'a' * 64})
    qtbot.waitUntil(lambda: window.opened == [7], timeout=3000)
    assert activated == [('POST', '/api/patients/7/cards/11/activate', {'token': 'a' * 64})]
    assert page.pending_card is None and page.scan_button.isEnabled()
    assert 'مفعّلة' in page.status.text()


def test_activation_failure_allows_retry(qtbot, monkeypatch):
    window = FakeWindow()
    window.request = lambda method, path, data, done, failed: failed('تعذر الاتصال بالخادم')
    page = NFCPage(window)
    qtbot.addWidget(page)
    monkeypatch.setattr('desktop.nfc_bridge.SerialRC522Reader.write',
                        lambda _, token: {'written': True})
    page.prepare_and_write({'patient_id': 7, 'card_id': 11, 'token': 'a' * 64})
    qtbot.waitUntil(lambda: 'تعذر تفعيلها' in page.status.text(), timeout=3000)
    assert page.pending_card == (7, 11)
    assert page.scan_button.isEnabled() and page.write_button.isEnabled()
