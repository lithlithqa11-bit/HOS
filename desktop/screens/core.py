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
        self.finance = QLabel('')
        self.finance.setObjectName('card')
        self.finance.setWordWrap(True)
        self.layout.addWidget(self.finance)
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
        if self.window.has_role('receptionist'):
            self.finance.setText('جاري تحميل ملخص الفواتير…')
            self.request('GET', '/api/invoices', done=self.show_finance)
        else:
            self.finance.setText('لوحة مالية متاحة لموظف الاستقبال فقط')
        if self.window.has_role('admin'):
            self.work.hide()
        else:
            path = '/api/prescriptions' if self.window.has_role('pharmacist') else (
                '/api/emergencies' if self.window.has_role('nurse') else '/api/waiting-queue')
            self.request('GET', path, done=self.work.populate)

    def show_finance(self, invoices):
        total = sum(float(row.get('total') or 0) for row in invoices)
        paid = sum(float(row.get('paid') or 0) for row in invoices)
        remaining = sum(float(row.get('remaining') or 0) for row in invoices)
        self.finance.setText(
            f"ملخص الاستقبال المالي\n"
            f"الفواتير: {len(invoices)}  •  الصافي: {total:,.2f} IQD\n"
            f"المدفوع: {paid:,.2f} IQD  •  المتبقي: {remaining:,.2f} IQD")


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


class DoctorsPage(Page):
    def __init__(self, window):
        super().__init__(window, 'دليل الأطباء', 'الأطباء الفعالون في مستشفاك مع عدد الحجوزات الحالية.')
        button('تحديث', self.refresh, self.actions)
        self.table = DataTable([('full_name', 'اسم الطبيب'), ('username', 'الحساب'),
                                ('hospital_name', 'المستشفى'), ('active', 'الحالة'),
                                ('appointments_count', 'عدد الحجوزات')])
        self.layout.addWidget(self.table)

    def refresh(self):
        self.request('GET', '/api/doctor-directory', done=self.table.populate)


class ProfilePage(Page):
    def __init__(self, window):
        super().__init__(window, 'ملف المريض', 'المعلومات المعروضة تحددها صلاحيات الخادم.')
        self.patient_id = None
        button('تحديث', self.refresh, self.actions)
        if window.has_role('receptionist'):
            self.issue_button = button('تهيئة البطاقة تلقائياً', self.issue, self.actions)
            button('إلغاء البطاقة', self.revoke, self.actions)
        if window.has_role('doctor', 'nurse'):
            button('حساسية / مرض مزمن', self.fact, self.actions)
        if window.has_role('doctor'):
            button('تسجيل زيارة وتشخيص', self.visit, self.actions)
            button('مشاركة زيارة', self.share, self.actions)
        self.view = QTextBrowser()
        self.layout.addWidget(self.view)
        self.card_status = QLabel('حالة البطاقة: جارٍ التحميل…')
        self.card_status.setObjectName('card')
        self.layout.addWidget(self.card_status)

    def refresh(self):
        if self.patient_id:
            self.request('GET', f'/api/patients/{self.patient_id}', done=self.show_profile)
            self.request('GET', f'/api/patients/{self.patient_id}/cards', done=self.show_card_status)

    def show_card_status(self, cards):
        active = next((card for card in cards if card.get('active')), None)
        if active:
            issued = str(active.get('issued_at', '')).replace('T', ' ')[:19]
            self.card_status.setText(f'حالة البطاقة: فعالة • رقم السجل {active["card_id"]} • الإصدار {issued}')
        else:
            self.card_status.setText('حالة البطاقة: لا توجد بطاقة فعالة')

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
        from PySide6.QtWidgets import QMessageBox

        if not self.patient_id or not self.issue_button.isEnabled():
            return
        reader_page = self.window.page_map['قراءة NFC']
        if not reader_page.scan_button.isEnabled():
            self.window.message('انتظر انتهاء عملية القارئ الحالية قبل تهيئة بطاقة أخرى')
            return
        if QMessageBox.question(self, 'تهيئة بطاقة المريض',
                'قرّب بطاقة MIFARE Classic 1K التجريبية من RC522 وأبقها ثابتة. '
                'ستُستبدل بيانات الكتل 4–6؛ استخدم بطاقة منفصلة عن القديمة عند الاستبدال. '
                'رمز البطاقة القديمة يبقى فعالاً بالنظام حتى تنجح التهيئة. متابعة؟') \
                != QMessageBox.StandardButton.Yes:
            return
        self.issue_button.setEnabled(False)
        self.request('POST', f'/api/patients/{self.patient_id}/cards/prepare',
                     done=self.prepared, failed=self.prepare_failed)

    def prepared(self, data):
        self.issue_button.setEnabled(True)
        self.window.card_prepared(data)

    def prepare_failed(self, _):
        self.issue_button.setEnabled(True)

    def revoke(self):
        if self.patient_id:
            self.request('DELETE', f'/api/patients/{self.patient_id}/cards',
                         done=lambda _: (self.show_card_status([]), self.window.message('أُلغيت البطاقة')))

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
        self.token = line('أصدر بطاقة من ملف المريض ثم اكتب الرمز عليها')
        self.token.setReadOnly(True)
        self.layout.addWidget(self.token)
        self.pending_card = None
        self.status = QLabel(f'الحالة: جاهز لقارئ RC522 على {window.nfc_port}')
        self.status.setObjectName('card')
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        self.scan_button = button('قراءة مباشرة من RC522', self.scan, self.actions)
        self.write_button = None
        if window.has_role('receptionist'):
            self.write_button = button('كتابة الرمز على بطاقة تجريبية', self.write, self.actions)
        self.layout.addStretch()

    def set_card_busy(self, busy):
        self.scan_button.setEnabled(not busy)
        if self.write_button is not None:
            self.write_button.setEnabled(not busy)
        self.token.setEnabled(not busy)

    def scan(self):
        from desktop.nfc_bridge import SerialRC522Reader
        if not self.scan_button.isEnabled():
            return
        self.status.setText('الحالة: بانتظار البطاقة قرب RC522 (المهلة نحو 20 ثانية)…')
        self.set_card_busy(True)
        self.window.tasks.submit(lambda: SerialRC522Reader(self.window.nfc_port).read(),
                                 self.scan_result, self.scan_failed)

    def scan_result(self, result):
        self.status.setText('الحالة: قُرئت البطاقة، جارٍ التحقق من رمزها…')
        self.request('POST', '/api/nfc/scan', {'token': result['token']},
                     done=self.scanned, failed=self.scan_failed)

    def scanned(self, data):
        self.status.setText('الحالة: تمت قراءة البطاقة وفتح ملف المريض')
        self.set_card_busy(False)
        self.window.show_scanned(data)

    def scan_failed(self, error):
        if 'بطاقة غير معروفة أو ملغاة' in error:
            self.status.setText('الحالة: البطاقة قُرئت لكن رمزها غير فعّال. افتح ملف المريض واضغط «تهيئة البطاقة تلقائياً».')
        else:
            self.status.setText(f'الحالة: تعذرت قراءة البطاقة: {error}')
        self.set_card_busy(False)

    def write(self):
        self._start_write(confirm=True)

    def prepare_and_write(self, data):
        self.pending_card = (data['patient_id'], data['card_id'])
        self.token.setText(data['token'])
        self._start_write(confirm=False)

    def _start_write(self, confirm):
        from desktop.nfc_bridge import SerialRC522Reader, TOKEN
        from PySide6.QtWidgets import QMessageBox
        if self.write_button is None or not self.write_button.isEnabled():
            self.status.setText('الحالة: القارئ مشغول؛ أعد محاولة الكتابة بعد انتهاء العملية الحالية.')
            return
        if self.pending_card is None:
            self.status.setText('الحالة: افتح ملف المريض واضغط «تهيئة البطاقة تلقائياً» أولاً.')
            return
        token = self.token.text().strip()
        if not TOKEN.fullmatch(token):
            self.status.setText('الحالة: رمز التهيئة غير صالح؛ أعد التهيئة من ملف المريض.')
            return
        if confirm and QMessageBox.question(self, 'إعادة كتابة البطاقة التجريبية',
                'ستُستبدل الكتل 4–6 من القطاع 1 في بطاقة MIFARE Classic 1K. '
                'استخدم بطاقة تجريبية مخصصة للمشروع فقط. متابعة؟') \
                != QMessageBox.StandardButton.Yes:
            return
        self.status.setText('الحالة: بانتظار البطاقة التجريبية لكتابة الرمز (المهلة نحو 20 ثانية)…')
        self.set_card_busy(True)
        self.window.tasks.submit(lambda: SerialRC522Reader(self.window.nfc_port).write(token),
                                 self.written, self.write_failed)

    def written(self, _):
        if self.pending_card is None:
            self.set_card_busy(False)
            return
        patient_id, card_id = self.pending_card
        self.status.setText('الحالة: كُتب الرمز وتحققت قراءته؛ جارٍ تفعيل البطاقة…')
        self.request('POST', f'/api/patients/{patient_id}/cards/{card_id}/activate',
                     {'token': self.token.text().strip()}, done=self.activated,
                     failed=self.activation_failed)

    def activated(self, data):
        self.pending_card = None
        self.status.setText('الحالة: البطاقة مكتوبة ومفعّلة وجاهزة للقراءة.')
        self.set_card_busy(False)
        self.window.message('اكتملت تهيئة البطاقة وجرى التحقق من كتابتها')
        self.window.open_patient(data['patient_id'])

    def activation_failed(self, error):
        self.status.setText(f'الحالة: كُتبت البطاقة، لكن تعذر تفعيلها: {error}. أعد محاولة الكتابة أو التهيئة.')
        self.set_card_busy(False)

    def write_failed(self, error):
        self.status.setText(f'الحالة: تعذرت كتابة البطاقة: {error}. أبقِ الرمز لإعادة المحاولة.')
        self.set_card_busy(False)
