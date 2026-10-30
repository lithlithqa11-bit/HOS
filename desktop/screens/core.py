import html
from urllib.parse import quote
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QFormLayout,
                              QDialog, QTextBrowser, QCheckBox)
from desktop.widgets.common import Page, DataTable, Form, button, line, combo, date_input


class LoginScreen(QWidget):
    login_requested = Signal(str, str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(180, 70, 180, 70)
        layout.addStretch()
        title = QLabel('MediLink NFC\nنظام المستشفيات الذكي')
        title.setObjectName('brand')
        layout.addWidget(title)
        layout.addWidget(QLabel('بيئة تعليمية • بيانات تجريبية فقط'))
        form = QFormLayout()
        self.username, self.password = line('receptionist.a'), line('كلمة المرور من ملف .env')
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('اسم المستخدم', self.username)
        form.addRow('كلمة المرور', self.password)
        layout.addLayout(form)
        self.login_button = button('تسجيل الدخول', self.submit, layout)
        self.password.returnPressed.connect(self.submit)
        layout.addStretch()

    def submit(self):
        self.login_requested.emit(self.username.text().strip(), self.password.text())


class Dashboard(Page):
    def __init__(self, window):
        super().__init__(window, 'مرحباً بك في MediLink', 'ملف موحّد للمريض • مستشفيات مترابطة • وصول حسب الصلاحية')
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setObjectName('card')
        self.layout.addWidget(self.summary)
        self.work = DataTable([('id', 'الرقم'), ('patient_id', 'المريض'), ('status', 'الحالة')])
        self.layout.addWidget(self.work)

    def refresh(self):
        e = self.window.employee
        descriptions = {'doctor': 'الطبيب: مراجعة الملف، تسجيل الزيارات والتشخيصات، كتابة الوصفات والإحالات.',
                        'nurse': 'التمريض: الحساسية والأمراض المزمنة، ترتيب الطوارئ وتحديث الحالة.',
                        'pharmacist': 'الصيدلية: عرض الأدوية والتعليمات وتسجيل صرف الوصفة مرة واحدة.',
                        'receptionist': 'الاستقبال: المرضى وبطاقات NFC، المواعيد، الفواتير والمدفوعات.',
                        'admin': 'الإدارة: المستشفيات والموظفون وصلاحيات الوصول وسجل التدقيق.'}
        self.summary.setText(f"{e['full_name']}\nالمستشفى رقم {e['hospital_id']}\n\n" +
                             '\n'.join(descriptions[r] for r in e['roles']))
        if self.window.has_role('admin'):
            self.work.hide()
        else:
            path = '/api/prescriptions' if self.window.has_role('pharmacist') else (
                '/api/emergencies' if self.window.has_role('nurse') else '/api/waiting-queue')
            self.request('GET', path, done=self.work.populate)


class PatientsPage(Page):
    def __init__(self, window):
        super().__init__(window, 'المرضى', 'ابحث بالاسم أو الرقم؛ النتائج مقيدة بمستشفاك.')
        self.search = line('اسم المريض أو رقمه')
        self.actions.addWidget(self.search)
        button('بحث', self.refresh, self.actions)
        button('عرض الملف', self.open_patient, self.actions)
        if window.has_role('receptionist'):
            button('مريض جديد', lambda: self.edit(False), self.actions)
            button('تعديل', lambda: self.edit(True), self.actions)
        self.table = DataTable([('id', 'الرقم'), ('full_name', 'اسم المريض'), ('birth_date', 'تاريخ الولادة'),
                                ('sex', 'الجنس'), ('phone', 'الهاتف')])
        self.layout.addWidget(self.table)
        self.table.doubleClicked.connect(self.open_patient)
        self.search.returnPressed.connect(self.refresh)

    def refresh(self):
        self.request('GET', '/api/patients?q=' + quote(self.search.text()), done=self.table.populate)

    def open_patient(self):
        row = self.choose(self.table)
        if row:
            self.window.open_patient(row['id'])

    def edit(self, editing):
        row = self.choose(self.table) if editing else None
        if editing and not row:
            return
        fields = [('full_name', 'الاسم الكامل', line()), ('birth_date', 'تاريخ الولادة', date_input()),
                  ('sex', 'الجنس', combo([('ذكر', 'male'), ('أنثى', 'female'), ('آخر', 'other')])),
                  ('phone', 'الهاتف', line())]
        if row:
            from PySide6.QtCore import QDate
            fields[0][2].setText(row['full_name'])
            fields[1][2].setDate(QDate.fromString(row['birth_date'], 'yyyy-MM-dd'))
            fields[2][2].setCurrentIndex(fields[2][2].findData(row['sex']))
            fields[3][2].setText(row['phone'])
        dialog = Form('تعديل المريض' if editing else 'تسجيل مريض', fields, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('PUT' if editing else 'POST', f"/api/patients/{row['id']}" if editing else '/api/patients',
                         dialog.data(), done=lambda result: self.window.open_patient(result['id']))


class ProfilePage(Page):
    def __init__(self, window):
        super().__init__(window, 'ملف المريض', 'المعلومات المعروضة تحددها صلاحيات الخادم.')
        self.patient_id = None
        button('تحديث', self.refresh, self.actions)
        if window.has_role('receptionist'):
            button('إصدار / استبدال بطاقة', self.issue, self.actions)
            button('إلغاء البطاقة', self.revoke, self.actions)
        if window.has_role('doctor', 'nurse'):
            button('حساسية / مرض مزمن', self.fact, self.actions)
        if window.has_role('doctor'):
            button('تسجيل زيارة وتشخيص', self.visit, self.actions)
            button('مشاركة زيارة', self.share, self.actions)
        self.view = QTextBrowser()
        self.layout.addWidget(self.view)

    def refresh(self):
        if self.patient_id:
            self.request('GET', f'/api/patients/{self.patient_id}', done=self.show_profile)

    def show_profile(self, data):
        self.patient_id = data['id']
        def escape(value):
            return html.escape(str(value))
        content = f"<h1>{escape(data['full_name'])}</h1><p>رقم الملف: {data['id']} • {escape(data['birth_date'])}</p>"
        content += f"<p>الهاتف: {escape(data['phone'])} • الجنس: {escape(data['sex'])}</p>"
        for name, label in [('allergies', 'الحساسية'), ('chronic_conditions', 'الأمراض المزمنة')]:
            if name in data:
                content += f'<h2>{label}</h2>'
                content += ''.join(f"<p>{escape(f['description'])} — المستشفى {f['hospital_id']} "
                                   f"({'مشترك' if f['shared'] else 'محلي'})</p>" for f in data[name]) or '<p>لا توجد سجلات</p>'
        if 'visits' in data:
            content += '<h2>الزيارات والتشخيصات</h2>'
            for visit in data['visits']:
                content += f"<h3>زيارة {visit['id']} • المستشفى {visit['hospital_id']}</h3>"
                content += f"<p>{escape(visit['created_at'])} • {'مشتركة' if visit['shared'] else 'محلية'}</p>"
                content += f"<p>{escape(visit['notes'])}</p><p>{escape('، '.join(visit['diagnoses']))}</p>"
        self.view.setHtml('<div dir="rtl">' + content + '</div>')

    def issue(self):
        if self.patient_id:
            self.request('POST', f'/api/patients/{self.patient_id}/cards', done=self.window.card_issued)

    def revoke(self):
        if self.patient_id:
            self.request('DELETE', f'/api/patients/{self.patient_id}/cards', done=lambda _: self.window.message('أُلغيت البطاقة'))

    def fact(self):
        if not self.patient_id:
            return
        dialog = Form('إضافة معلومة طبية', [('kind', 'النوع', combo([('حساسية', 'allergy'), ('مرض مزمن', 'chronic')])),
                      ('description', 'الوصف', line()), ('shared', 'السماح بالمشاركة', QCheckBox())], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('POST', f'/api/patients/{self.patient_id}/facts', dialog.data())

    def visit(self):
        if not self.patient_id:
            return
        dialog = Form('زيارة جديدة', [('notes', 'الملاحظات', line()), ('diagnosis', 'التشخيص', line()),
                                     ('shared', 'السماح بالمشاركة', QCheckBox())], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('POST', '/api/visits', {'patient_id': self.patient_id, **dialog.data()})

    def share(self):
        from desktop.widgets.common import integer
        dialog = Form('مشاركة أو إخفاء زيارة من مستشفاك', [('visit_id', 'رقم الزيارة', integer()),
                      ('shared', 'السماح بالمشاركة', QCheckBox())], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            id = data.pop('visit_id')
            self.request('PATCH', f'/api/visits/{id}/sharing', data)


class NFCPage(Page):
    def __init__(self, window):
        super().__init__(window, 'قارئ NFC', 'البطاقة تحمل رمزاً عشوائياً فقط؛ يلزم تسجيل دخول الموظف للوصول إلى الملف.')
        self.mode = combo([('محاكاة — دون جهاز', 'mock'), ('قارئ PC/SC حقيقي', 'real')])
        import os
        self.mode.setCurrentIndex(1 if os.getenv('NFC_MODE') == 'real' else 0)
        self.actions.addWidget(self.mode)
        self.token = line('ألصق رمز البطاقة التجريبية أو أصدر بطاقة من ملف المريض')
        self.layout.addWidget(self.token)
        button('قراءة البطاقة', self.scan, self.actions)
        if window.has_role('receptionist'):
            button('كتابة الرمز على بطاقة Type 2 تجريبية', self.write, self.actions)
        self.layout.addStretch()

    def scan(self):
        from desktop.nfc_bridge import MockNFCReader, RealNFCReader
        reader = MockNFCReader() if self.mode.currentData() == 'mock' else RealNFCReader(self.window.nfc_executable)
        token = self.token.text().strip()
        self.window.tasks.submit(lambda: reader.read(token), lambda result: self.request(
            'POST', '/api/nfc/scan', {'token': result['token']}, done=self.window.show_scanned))

    def write(self):
        from desktop.nfc_bridge import RealNFCReader
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self, 'كتابة بطاقة تجريبية',
                'ستُستبدل بيانات الصفحات 4–12. استخدم بطاقة Type 2 تجريبية فارغة مخصصة للمشروع. متابعة؟') \
                != QMessageBox.StandardButton.Yes:
            return
        token = self.token.text().strip()
        self.window.tasks.submit(lambda: RealNFCReader(self.window.nfc_executable).write(token),
                                 lambda _: self.window.message('كُتب الرمز وتحققت قراءته'))
