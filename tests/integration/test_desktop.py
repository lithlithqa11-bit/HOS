import os
from pathlib import Path
import subprocess
import sys
import time
import httpx
import pytest
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QTimer, Qt
from desktop.main import MainWindow
from desktop.widgets.common import Form


@pytest.fixture
def live_api(client):
    log_path = Path('.runtime/qt-test-server.log')
    log_path.parent.mkdir(exist_ok=True)
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app.main:app',
                                    '--host', '127.0.0.1', '--port', '18001'],
                                   stdout=log, stderr=log, env=os.environ.copy(),
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            for _ in range(100):
                try:
                    if httpx.get('http://127.0.0.1:18001/health', timeout=.4, trust_env=False).status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                if process.poll() is not None:
                    pytest.fail(log_path.read_text(encoding='utf-8'))
                time.sleep(.1)
            else:
                pytest.fail('Live API did not start')
            yield 'http://127.0.0.1:18001'
        finally:
            process.terminate()
            process.wait(timeout=10)


def test_desktop_login_create_scan_profile(qtbot, live_api):
    window = MainWindow(live_api)
    qtbot.addWidget(window)
    failures = []
    window.tasks.error.disconnect(window.error)
    window.tasks.error.connect(failures.append)
    window.show()
    assert window.layoutDirection() == Qt.LayoutDirection.RightToLeft
    window.login.username.setText('receptionist.a')
    window.login.password.setText(os.environ['DEMO_PASSWORD'])
    qtbot.mouseClick(window.login.login_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.employee is not None, timeout=15000)
    page = window.page_map['المرضى']

    def fill_form():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QDialog)
        fields = {key: widget for key, _, widget in dialog.fields}
        fields['full_name'].setText('مريض من واجهة PySide6')
        fields['phone'].setText('000000000')
        dialog.accept()

    QTimer.singleShot(100, fill_form)
    page.edit(False)
    profile = window.page_map['ملف المريض']
    qtbot.waitUntil(lambda: 'مريض من واجهة PySide6' in profile.view.toPlainText(), timeout=15000)
    profile.issue()
    nfc = window.page_map['قراءة NFC']
    qtbot.waitUntil(lambda: len(nfc.token.text()) == 64, timeout=15000)
    profile.view.clear()
    nfc.scan()
    qtbot.waitUntil(lambda: 'مريض من واجهة PySide6' in profile.view.toPlainText(), timeout=15000)
    qtbot.waitUntil(lambda: not window.tasks.pending, timeout=15000)
    assert not failures
    Path('docs/screenshots').mkdir(exist_ok=True)
    window.grab().save('docs/screenshots/patient-profile.png')
    window.sign_out()
    assert window.api.token is None and window.root.currentWidget() is window.login


def test_desktop_all_roles_and_billing_receipt(qtbot, live_api, client, auth, monkeypatch):
    """Every page refreshes against HTTP; reception creates and pays a real invoice."""
    from PySide6.QtWidgets import QLineEdit, QSpinBox, QComboBox, QCheckBox, QFileDialog
    window = MainWindow(live_api)
    qtbot.addWidget(window)
    failures = []
    window.tasks.error.disconnect(window.error)
    window.tasks.error.connect(failures.append)
    window.show()

    def idle():
        qtbot.waitUntil(lambda: not window.tasks.pending, timeout=15000)
        assert not failures, failures

    def sign_in(role):
        window.sign_in(role + '.a', os.environ['DEMO_PASSWORD'])
        qtbot.waitUntil(lambda: window.employee is not None, timeout=15000)
        idle()

    def complete_form(action, values):
        def fill():
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, Form)
            for key, _, widget in dialog.fields:
                if key not in values:
                    continue
                value = values[key]
                if isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(value)
                elif isinstance(widget, QComboBox):
                    widget.setCurrentIndex(widget.findData(value))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(value)
            dialog.accept()
        QTimer.singleShot(100, fill)
        action()
        idle()

    sign_in('receptionist')
    billing = window.page_map['فواتير الاستقبال']
    window.nav.setCurrentRow(window.pages.indexOf(billing))
    idle()
    complete_form(billing.create, {'patient_id': 1, 'discount': '5.00', 'description': 'خدمة من واجهة الاستقبال',
                                   'quantity': 2, 'unit_price': '50.00'})
    assert len(billing.table.rows) == 1 and billing.table.rows[0]['total'] == '95.00'
    billing.table.setCurrentCell(0, 0)
    assert billing.table.selected() is not None, (billing.table.rowCount(), billing.table.columnCount(), billing.table.isEnabled(), billing.table.item(0, 0))
    complete_form(billing.add_item, {'description': 'بند ثانٍ', 'quantity': 1, 'unit_price': '5.00'})
    billing.table.setCurrentCell(0, 0)
    complete_form(billing.pay, {'amount': '25.50'})
    billing.table.setCurrentCell(0, 0)
    assert billing.table.rows[0]['remaining'] == '74.50'
    assert 'خدمة من واجهة الاستقبال' in billing.receipt.toPlainText()
    receipt_path = str(Path('.runtime/test-receipt.pdf').resolve())
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a, **k: (receipt_path, 'PDF (*.pdf)'))
    billing.export()
    idle()
    assert Path(receipt_path).read_bytes().startswith(b'%PDF-')
    assert Path(receipt_path).stat().st_size > 1000
    window.grab().save('docs/screenshots/reception-billing.png')
    window.sign_out()

    sign_in('nurse')
    emergency = window.page_map['الطوارئ والفرز']
    window.nav.setCurrentRow(window.pages.indexOf(emergency))
    idle()
    complete_form(emergency.create, {'patient_id': 1, 'priority': 2, 'notes': 'فرز تدريبي من الواجهة'})
    assert len(emergency.table.rows) == 1
    emergency.table.setCurrentCell(0, 0)
    complete_form(emergency.edit, {'priority': 1, 'status': 'treating'})
    assert emergency.table.rows[0]['status'] == 'treating'
    window.grab().save('docs/screenshots/emergency-triage.png')
    window.sign_out()

    for role in ('doctor', 'pharmacist', 'admin'):
        sign_in(role)
        for index in range(window.pages.count()):
            window.nav.setCurrentRow(index)
            idle()
        if role == 'admin':
            window.page_map['الإدارة'].audit()
            idle()
            assert window.page_map['الإدارة'].audit_table.rows
        window.grab().save(f'docs/screenshots/{role}-dashboard.png')
        window.sign_out()

    stored = client.get('/api/invoices', headers=auth()).json()[0]
    assert stored['remaining'] == '74.50' and len(stored['payments']) == 1
