"""Hospital pages use only API requests; all clinical decisions remain with staff."""
import html
from uuid import uuid4
from PySide6.QtCore import QDateTime
from PySide6.QtGui import QTextDocument, QPdfWriter, QPageSize
from PySide6.QtWidgets import (QDialog, QCheckBox, QTextBrowser, QLabel, QFileDialog,
                              QLineEdit, QVBoxLayout, QFormLayout, QDialogButtonBox,
                              QTableWidget, QHeaderView)
from desktop.widgets.common import Page, DataTable, Form, button, line, combo, integer, time_input


def default_patient(window):
    return window.page_map['ملف المريض'].patient_id or 1


class AppointmentsPage(Page):
    def __init__(self, window):
        super().__init__(window, 'المواعيد وطابور المراجعين', 'الطابور حسب وقت تسجيل الحضور. لا يسمح بتداخل موعد الطبيب أو المريض.')
        button('كل المواعيد', lambda: self.load(False), self.actions)
        button('طابور الانتظار', lambda: self.load(True), self.actions)
        if window.has_role('receptionist'):
            button('حجز', lambda: self.edit(False), self.actions)
            button('حجز لطبيب', lambda: self.edit(False), self.actions)
            button('تعديل', lambda: self.edit(True), self.actions)
            button('حضور', lambda: self.action('check-in'), self.actions)
            button('إلغاء', lambda: self.action('cancel'), self.actions)
        button('إنهاء دور التالي', self.next, self.actions)
        self.table = DataTable([('id', 'الموعد'), ('patient_name', 'المريض'), ('doctor_id', 'الطبيب'),
                                ('starts_at', 'البداية'), ('ends_at', 'النهاية'), ('status', 'الحالة')])
        self.layout.addWidget(self.table)

    def refresh(self):
        self.load(False)

    def load(self, queue):
        self.request('GET', '/api/waiting-queue' if queue else '/api/appointments', done=self.table.populate)

    def edit(self, editing):
        row = self.choose(self.table) if editing else None
        if editing and not row:
            return
        self.request('GET', '/api/doctors', done=lambda doctors: self.form(row, doctors))

    def form(self, row, doctors):
        start, end = time_input(), time_input()
        end.setDateTime(start.dateTime().addSecs(1800))
        physician = combo([(d['full_name'] + f" (#{d['id']})", d['id']) for d in doctors])
        if row:
            start.setDateTime(QDateTime.fromString(row['starts_at'], __import__('PySide6.QtCore', fromlist=['Qt']).Qt.DateFormat.ISODate))
            end.setDateTime(QDateTime.fromString(row['ends_at'], __import__('PySide6.QtCore', fromlist=['Qt']).Qt.DateFormat.ISODate))
            physician.setCurrentIndex(physician.findData(row['doctor_id']))
        dialog = Form('الموعد', [('patient_id', 'رقم المريض', integer(row['patient_id'] if row else default_patient(self.window))),
                                 ('doctor_id', 'الطبيب', physician), ('starts_at', 'البداية', start),
                                 ('ends_at', 'النهاية', end)], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('PUT' if row else 'POST', f"/api/appointments/{row['id']}" if row else '/api/appointments', dialog.data())

    def action(self, action):
        row = self.choose(self.table)
        if row:
            self.request('POST', f"/api/appointments/{row['id']}/{action}")

    def next(self):
        self.request('POST', '/api/waiting-queue/next', done=lambda row: (self.window.message(
            f"تم إنهاء دور {row['patient_name']} • الموعد {row['id']}"), self.load(True)))


class EmergencyPage(Page):
    def __init__(self, window):
        super().__init__(window, 'الطوارئ والفرز', 'الأولوية يحددها المختص: 1 أعلى و5 أدنى. التعادل حسب الوصول ثم رقم الحالة.')
        button('تحديث', self.refresh, self.actions)
        button('حالة جديدة', self.create, self.actions)
        button('تعديل الأولوية والحالة', self.edit, self.actions)
        button('بدء علاج الحالة التالية', lambda: self.request('POST', '/api/emergencies/next'), self.actions)
        self.table = DataTable([('id', 'الحالة'), ('patient_name', 'المريض'), ('priority', 'الأولوية'),
                                ('arrived_at', 'الوصول'), ('status', 'الحالة'), ('notes', 'ملاحظات')])
        self.layout.addWidget(self.table)

    def refresh(self):
        self.request('GET', '/api/emergencies', done=self.table.populate)

    def create(self):
        dialog = Form('تسجيل حالة طوارئ', [('patient_id', 'رقم المريض', integer(default_patient(self.window))),
                      ('priority', 'الأولوية 1–5', integer(3, 5)), ('notes', 'ملاحظات الفرز', line())], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('POST', '/api/emergencies', dialog.data())

    def edit(self):
        row = self.choose(self.table)
        if not row:
            return
        status = combo([('انتظار', 'waiting'), ('قيد العلاج', 'treating'), ('خرج', 'discharged')])
        status.setCurrentIndex(status.findData(row['status']))
        dialog = Form('تحديث الحالة', [('priority', 'الأولوية', integer(row['priority'], 5)),
                                     ('status', 'الحالة', status)], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('PUT', f"/api/emergencies/{row['id']}", dialog.data())


class PrescriptionDialog(QDialog):
    def __init__(self, medications, parent=None):
        super().__init__(parent)
        self.setWindowTitle('إنشاء وصفة تعليمية')
        self.resize(850, 450)
        self.medications = medications
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.visit_id = integer()
        form.addRow('رقم الزيارة من ملف المريض', self.visit_id)
        layout.addLayout(form)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['الدواء', 'الجرعة', 'التعليمات'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        button('إضافة دواء', self.add_item, layout)
        button('حذف السطر المحدد', self.remove_item, layout)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.add_item()

    def add_item(self):
        if self.table.rowCount() >= 30:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setCellWidget(row, 0, combo([(m['name'], m['id']) for m in self.medications]))
        self.table.setCellWidget(row, 1, line('جرعة يحددها الطبيب'))
        self.table.setCellWidget(row, 2, line('تعليمات يحددها الطبيب'))

    def remove_item(self):
        if self.table.currentRow() >= 0:
            self.table.removeRow(self.table.currentRow())

    def data(self):
        return {'visit_id': self.visit_id.value(), 'items': [
            {'medication_id': self.table.cellWidget(row, 0).currentData(),
             'dose': self.table.cellWidget(row, 1).text(), 'instructions': self.table.cellWidget(row, 2).text()}
            for row in range(self.table.rowCount())]}


class PharmacyPage(Page):
    def __init__(self, window):
        super().__init__(window, 'الوصفات والصيدلية', 'Pending → Dispensed • صرف واحد للوصفة مع تسجيل الموظف والتاريخ.')
        self.filter = line('رقم المريض — اتركه فارغاً لعرض المسموح')
        self.actions.addWidget(self.filter)
        button('تحديث', self.refresh, self.actions)
        if window.has_role('doctor'):
            button('وصفة جديدة', self.create, self.actions)
        if window.has_role('pharmacist'):
            button('تسجيل الصرف', self.dispense, self.actions)
        self.table = DataTable([('id', 'الوصفة'), ('patient_id', 'المريض'), ('visit_id', 'الزيارة'),
                                ('hospital_id', 'المستشفى المصدر'), ('status', 'الحالة'),
                                ('dispensed_by', 'الصيدلي'), ('dispensed_at', 'وقت الصرف')])
        self.table.itemSelectionChanged.connect(self.details)
        self.layout.addWidget(self.table)
        self.detail = QTextBrowser()
        self.layout.addWidget(self.detail)

    def refresh(self):
        from urllib.parse import quote
        suffix = '?patient_id=' + quote(self.filter.text().strip()) if self.filter.text().strip() else ''
        self.request('GET', '/api/prescriptions' + suffix, done=self.table.populate)

    def details(self):
        row = self.table.selected()
        if row:
            self.detail.setHtml('<div dir="rtl"><h2>بنود الوصفة</h2>' + ''.join(
                f"<h3>{html.escape(i['name'])}</h3><p>الجرعة: {html.escape(i['dose'])}</p>"
                f"<p>{html.escape(i['instructions'])}</p>" for i in row['items']) + '</div>')
        else:
            self.detail.clear()

    def create(self):
        self.request('GET', '/api/medications', done=self.form)

    def form(self, medications):
        dialog = PrescriptionDialog(medications, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('POST', '/api/prescriptions', dialog.data())

    def dispense(self):
        row = self.choose(self.table)
        if row:
            self.request('POST', f"/api/prescriptions/{row['id']}/dispense")


def receipt_html(data):
    rows = ''.join(f"<tr><td>{html.escape(i['description'])}</td><td>{i['quantity']}</td>"
                   f"<td>{html.escape(i['unit_price'])}</td></tr>" for i in data['items'])
    payments = ''.join(f"<p>دفعة #{p['id']}: {html.escape(p['amount'])} IQD — {html.escape(str(p['paid_at']))}</p>"
                       for p in data['payments'])
    return (f'<div dir="rtl"><h1>MediLink NFC — إيصال تعليمي</h1>'
            f"<p>الفاتورة #{data['id']} • المريض #{data['patient_id']} • المستشفى #{data['hospital_id']}</p>"
            f"<p>{html.escape(str(data['created_at']))}</p>"
            '<table width="100%" cellpadding="8" border="1"><tr><th>الخدمة</th><th>الكمية</th><th>سعر الوحدة IQD</th></tr>'
            f'{rows}</table>' + ''.join(f'<p><b>{label}: {html.escape(data[key])} IQD</b></p>' for key, label in
                [('subtotal', 'المجموع'), ('discount', 'الخصم'), ('total', 'الصافي'), ('paid', 'المدفوع'), ('remaining', 'المتبقي')])
            + payments + '<p>بيانات عرض جامعي وهمية — ليس إيصالاً تجارياً.</p></div>')


class BillingPage(Page):
    def __init__(self, window):
        super().__init__(window, 'الاستقبال — الفواتير والمدفوعات', 'المبالغ بالدينار العراقي IQD. الفاتورة تقبل عدة دفعات دون تجاوز الرصيد.')
        self.filter = line('رقم المريض للسجل')
        self.actions.addWidget(self.filter)
        button('تحديث', self.refresh, self.actions)
        button('فاتورة جديدة', self.create, self.actions)
        button('إضافة بند', self.add_item, self.actions)
        button('تسجيل دفعة', self.pay, self.actions)
        button('تصدير إيصال PDF', self.export, self.actions)
        self.table = DataTable([('id', 'الفاتورة'), ('patient_id', 'المريض'), ('total', 'الصافي IQD'),
                                ('paid', 'المدفوع'), ('remaining', 'المتبقي')])
        self.layout.addWidget(self.table)
        self.receipt = QTextBrowser()
        self.layout.addWidget(self.receipt)
        self.table.itemSelectionChanged.connect(self.details)
        self.pending_payment = None

    def refresh(self):
        from urllib.parse import quote
        suffix = '?patient_id=' + quote(self.filter.text().strip()) if self.filter.text().strip() else ''
        self.request('GET', '/api/invoices' + suffix, done=self.table.populate)

    @staticmethod
    def item_fields():
        return [('description', 'الخدمة', line()), ('quantity', 'العدد', integer(1, 10000)),
                ('unit_price', 'سعر الوحدة IQD', line('10000.00'))]

    def create(self):
        dialog = Form('فاتورة خدمة', [('patient_id', 'رقم المريض', integer(default_patient(self.window))),
                      ('visit_id', 'رقم الزيارة (اختياري)', line()), ('discount', 'الخصم IQD', line('0.00')),
                      *self.item_fields()], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            if data['visit_id'] and not data['visit_id'].isdecimal():
                self.window.message('رقم الزيارة يجب أن يكون عدداً صحيحاً')
                return
            payload = {'patient_id': data.pop('patient_id'), 'visit_id': int(data.pop('visit_id') or 0) or None,
                       'discount': data.pop('discount') or '0.00', 'items': [data]}
            self.request('POST', '/api/invoices', payload)

    def add_item(self):
        row = self.choose(self.table)
        if row:
            dialog = Form('إضافة بند قبل بدء السداد', self.item_fields(), self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.request('POST', f"/api/invoices/{row['id']}/items", dialog.data())

    def pay(self):
        row = self.choose(self.table)
        if not row:
            return
        amount = line(row['remaining'])
        amount.setText(row['remaining'])
        dialog = Form('دفعة جديدة', [('amount', 'المبلغ IQD', amount)], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            signature = (row['id'], data['amount'])
            # Preserve the key after network errors; retrying cannot charge twice.
            if not self.pending_payment or self.pending_payment[:2] != signature:
                self.pending_payment = (*signature, str(uuid4()))
            data['request_key'] = self.pending_payment[2]
            self.request('POST', f"/api/invoices/{row['id']}/payments", data, done=self.paid)

    def paid(self, result):
        self.pending_payment = None
        self.refresh()
        self.receipt.setHtml(receipt_html(result))
        self.window.message('سُجلت الدفعة. المتبقي: ' + result['remaining'] + ' IQD')

    def details(self):
        row = self.table.selected()
        self.receipt.setHtml(receipt_html(row) if row else '')

    def export(self):
        row = self.choose(self.table)
        if not row:
            return
        # Refresh from API before producing a receipt, avoiding stale balances.
        self.request('GET', f"/api/invoices/{row['id']}", done=self.save_receipt)

    def save_receipt(self, data):
        path, _ = QFileDialog.getSaveFileName(self, 'تصدير إيصال', f"receipt-{data['id']}.pdf", 'PDF (*.pdf)')
        if path:
            # QPdfWriter exports directly, without enumerating Windows printer drivers.
            printer = QPdfWriter(path)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setResolution(144)
            document = QTextDocument()
            document.setHtml(receipt_html(data))
            document.print_(printer)
            self.window.message('حُفظ الإيصال: ' + path)


class ReferralsPage(Page):
    def __init__(self, window):
        super().__init__(window, 'المستشفيات والإحالات', 'BFS يحسب أقصر مسار بعدد الروابط. قبول الإحالة يتيح السجلات المشتركة فقط.')
        button('تحديث', self.refresh, self.actions)
        button('عرض مسار إلى مستشفى', self.path, self.actions)
        if window.has_role('doctor'):
            button('إحالة جديدة', self.create, self.actions)
            button('قبول', lambda: self.change('accepted'), self.actions)
            button('رفض', lambda: self.change('rejected'), self.actions)
            button('إلغاء', lambda: self.change('cancelled'), self.actions)
        self.route = QLabel('')
        self.route.setWordWrap(True)
        self.layout.addWidget(self.route)
        self.table = DataTable([('id', 'الإحالة'), ('patient_id', 'المريض'), ('source_name', 'المصدر'),
                                ('destination_name', 'الوجهة'), ('status', 'الحالة'), ('path', 'المسار')])
        self.layout.addWidget(self.table)

    def refresh(self):
        self.request('GET', '/api/referrals', done=self.table.populate)

    def hospital_form(self, hospitals, creating):
        fields = [('destination_id', 'الوجهة', combo([(h['name'], h['id']) for h in hospitals
                                                      if h['id'] != self.window.employee['hospital_id']]))]
        if creating:
            fields += [('patient_id', 'رقم المريض', integer(default_patient(self.window))), ('reason', 'سبب الإحالة', line())]
        dialog = Form('إحالة' if creating else 'مسار المستشفيات', fields, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            if creating:
                self.request('POST', '/api/referrals', data)
            else:
                self.request('GET', f"/api/hospital-path/{data['destination_id']}", done=lambda result:
                             self.route.setText(' ← '.join(result['hospitals'])))

    def path(self):
        self.request('GET', '/api/hospitals', done=lambda h: self.hospital_form(h, False))

    def create(self):
        self.request('GET', '/api/hospitals', done=lambda h: self.hospital_form(h, True))

    def change(self, status):
        row = self.choose(self.table)
        if row:
            self.request('PUT', f"/api/referrals/{row['id']}", {'status': status})


class AdminPage(Page):
    def __init__(self, window):
        super().__init__(window, 'الإدارة', 'إدارة الموظفين والمستشفيات والمنح. صلاحيات المدير لا تمنح تلقائياً دور الطبيب.')
        button('الموظفون', self.refresh, self.actions)
        button('موظف جديد', self.create_employee, self.actions)
        button('صلاحيات الموظف', self.edit_employee, self.actions)
        button('مستشفى جديد', self.create_hospital, self.actions)
        second = __import__('PySide6.QtWidgets', fromlist=['QHBoxLayout']).QHBoxLayout()
        self.layout.addLayout(second)
        button('منح / سحب وصول المريض', self.access, second)
        button('رابط إحالة جديد', self.connection, second)
        button('تصحيح صرف وصفة', self.correct, second)
        button('تحديث سجل التدقيق', self.audit, second)
        self.table = DataTable([('id', 'الموظف'), ('full_name', 'الاسم'), ('username', 'المستخدم'),
                                ('hospital_id', 'المستشفى'), ('roles', 'الأدوار'), ('active', 'فعال')])
        self.layout.addWidget(self.table)
        self.audit_table = DataTable([('id', 'رقم'), ('action', 'العملية'), ('actor_id', 'الموظف'),
                                      ('hospital_id', 'المستشفى'), ('patient_id', 'المريض'), ('detail', 'تفاصيل'),
                                      ('created_at', 'الوقت')])
        self.layout.addWidget(self.audit_table)

    @staticmethod
    def role_fields(selected=()):
        fields = []
        for role, label in [('admin', 'مدير'), ('doctor', 'طبيب'), ('nurse', 'ممرض'),
                            ('pharmacist', 'صيدلي'), ('receptionist', 'استقبال')]:
            check = QCheckBox()
            check.setChecked(role in selected)
            fields.append((role, label, check))
        return fields

    @staticmethod
    def collect_roles(data):
        data['roles'] = [role for role in ('admin', 'doctor', 'nurse', 'pharmacist', 'receptionist') if data.pop(role)]
        return data

    def refresh(self):
        self.request('GET', '/api/admin/employees', done=self.table.populate)

    def create_employee(self):
        password = line('12 حرفاً على الأقل')
        password.setEchoMode(QLineEdit.EchoMode.Password)
        dialog = Form('إضافة موظف', [('username', 'اسم المستخدم', line()), ('full_name', 'الاسم', line()),
                      ('hospital_id', 'رقم المستشفى', integer(self.window.employee['hospital_id'])),
                      ('password', 'كلمة المرور', password), *self.role_fields()], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('POST', '/api/admin/employees', self.collect_roles(dialog.data()))

    def edit_employee(self):
        row = self.choose(self.table)
        if row:
            active = QCheckBox()
            active.setChecked(row['active'])
            dialog = Form('تعديل الصلاحيات', [('active', 'حساب فعال', active), *self.role_fields(row['roles'])], self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.request('PUT', f"/api/admin/employees/{row['id']}", self.collect_roles(dialog.data()))

    def create_hospital(self):
        dialog = Form('مستشفى جديد', [('name', 'الاسم', line()), ('city', 'المدينة', line())], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('POST', '/api/admin/hospitals', dialog.data(), done=lambda r: self.window.message(f"أُنشئ المستشفى #{r['id']}"))

    def access(self):
        active = QCheckBox()
        active.setChecked(True)
        dialog = Form('صلاحية ملف المريض', [('patient_id', 'رقم المريض', integer()),
                      ('hospital_id', 'رقم المستشفى', integer()), ('active', 'وصول فعال', active)], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            id = data.pop('patient_id')
            self.request('PUT', f'/api/admin/patients/{id}/access', data, done=lambda _: self.window.message('حُدثت منحة الوصول'))

    def connection(self):
        dialog = Form('رابط إحالة موجه', [('source_id', 'المستشفى المصدر', integer()),
                      ('destination_id', 'المستشفى الوجهة', integer(2))], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.request('POST', '/api/admin/connections', dialog.data(), done=lambda _: self.window.message('أُضيف الرابط'))

    def correct(self):
        dialog = Form('تصحيح صرف مخوّل', [('id', 'رقم الوصفة', integer()), ('reason', 'سبب التصحيح', line())], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.data()
            id = data.pop('id')
            self.request('POST', f'/api/prescriptions/{id}/correct', data, done=lambda _: self.window.message('أُعيدت الوصفة إلى Pending وسُجل التصحيح'))

    def audit(self):
        self.request('GET', '/api/admin/audit', done=self.audit_table.populate)
