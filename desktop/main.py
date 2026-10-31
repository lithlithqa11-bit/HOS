import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                              QStackedWidget, QLabel, QListWidget, QMessageBox)
from desktop.api_client import ApiClient, Tasks
from desktop.screens.core import LoginScreen, Dashboard, PatientsPage, ProfilePage, NFCPage, DoctorsPage
from desktop.widgets.common import button
from desktop.screens.modules import AppointmentsPage, EmergencyPage, PharmacyPage, BillingPage, ReferralsPage, AdminPage


class MainWindow(QMainWindow):
    def __init__(self, api_url=None):
        super().__init__()
        # Qt's offscreen platform on Windows may not discover system fonts.
        for font_file in ('segoeui.ttf', 'segoeuib.ttf'):
            font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / font_file
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))
        QApplication.instance().setFont(QFont('Segoe UI', 10))
        self.setWindowTitle('MediLink NFC — المستشفيات الذكية')
        self.resize(1280, 820)
        self.setMinimumSize(1000, 680)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.api = ApiClient(api_url or os.getenv('API_URL', 'http://127.0.0.1:8000'))
        self.nfc_executable = os.getenv('NFC_EXECUTABLE', 'nfc_cpp/build/nfc_reader.exe')
        self.employee = None
        self.generation = 0
        self.tasks = Tasks(self)
        self.tasks.error.connect(self.error)
        self.tasks.busy.connect(self.loading)
        self.root = QStackedWidget()
        self.login = LoginScreen()
        self.login.login_requested.connect(self.sign_in)
        self.root.addWidget(self.login)
        self.setCentralWidget(self.root)
        self.statusBar().showMessage('جاهز • بيانات تعليمية فقط')
        style = Path(__file__).parent / 'assets' / 'style.qss'
        if style.exists():
            self.setStyleSheet(style.read_text(encoding='utf-8'))

    def has_role(self, *names):
        return bool(set(self.employee['roles']).intersection(names))

    def request(self, method, path, data=None, done=None):
        generation = self.generation
        self.tasks.submit(lambda: self.api.request(method, path, data),
                          lambda result: done(result) if generation == self.generation and done else None)

    def sign_in(self, username, password):
        self.request('POST', '/api/auth/login', {'username': username, 'password': password}, self.signed_in)

    def signed_in(self, result):
        self.api.token = result['access_token']
        self.employee = result['employee']
        self.login.password.clear()
        self.shell = QWidget()
        layout = QHBoxLayout(self.shell)
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(250)
        sidebar = QVBoxLayout(sidebar_widget)
        brand = QLabel('MediLink NFC\nالمستشفيات الذكية')
        brand.setObjectName('brand')
        sidebar.addWidget(brand)
        sidebar.addWidget(QLabel(self.employee['full_name']))
        self.nav = QListWidget()
        self.nav.setFixedWidth(220)
        sidebar.addWidget(self.nav)
        button('تسجيل الخروج', self.sign_out, sidebar)
        layout.addWidget(sidebar_widget)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.page_map = {}
        for name, page in [('الرئيسية', Dashboard(self)), ('المرضى', PatientsPage(self)),
                           ('ملف المريض', ProfilePage(self)), ('قراءة NFC', NFCPage(self))]:
            self.add_page(name, page)
        if self.has_role('doctor', 'nurse', 'receptionist'):
            self.add_page('المواعيد والطابور', AppointmentsPage(self))
            self.add_page('المستشفيات والإحالات', ReferralsPage(self))
        if self.has_role('receptionist', 'doctor', 'admin'):
            self.add_page('دليل الأطباء', DoctorsPage(self))
        if self.has_role('doctor', 'nurse'):
            self.add_page('الطوارئ والفرز', EmergencyPage(self))
        if self.has_role('doctor', 'pharmacist'):
            self.add_page('الوصفات والصيدلية', PharmacyPage(self))
        if self.has_role('receptionist'):
            self.add_page('فواتير الاستقبال', BillingPage(self))
        if self.has_role('admin'):
            self.add_page('الإدارة', AdminPage(self))
        self.nav.currentRowChanged.connect(self.navigate)
        self.root.addWidget(self.shell)
        self.root.setCurrentWidget(self.shell)
        self.nav.setCurrentRow(0)

    def add_page(self, name, page):
        self.nav.addItem(name)
        self.page_map[name] = page
        self.pages.addWidget(page)

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        page = self.pages.currentWidget()
        if page:
            page.refresh()

    def open_patient(self, id):
        page = self.page_map['ملف المريض']
        page.patient_id = id
        self.nav.setCurrentRow(self.pages.indexOf(page))
        page.refresh()

    def show_scanned(self, data):
        page = self.page_map['ملف المريض']
        page.show_profile(data)
        self.nav.setCurrentRow(self.pages.indexOf(page))

    def card_issued(self, data):
        page = self.page_map['قراءة NFC']
        page.token.setText(data['token'])
        self.nav.setCurrentRow(self.pages.indexOf(page))
        self.message('أُصدرت البطاقة وأُلغي الرمز السابق إن وُجد. الرمز يظهر مرة واحدة؛ اضغط قراءة للمحاكاة.')

    def sign_out(self):
        self.generation += 1
        self.api.token = None
        self.employee = None
        self.root.setCurrentWidget(self.login)
        self.root.removeWidget(self.shell)
        self.shell.deleteLater()

    def loading(self, busy):
        self.login.login_button.setEnabled(not busy)
        self.statusBar().showMessage('جارٍ تنفيذ الطلب…' if busy else 'جاهز • PostgreSQL / FastAPI')

    def message(self, text):
        self.statusBar().showMessage(text, 15000)

    def error(self, text):
        self.statusBar().showMessage(text, 20000)
        QMessageBox.warning(self, 'تعذر إكمال العملية', text)


def main():
    load_dotenv()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
