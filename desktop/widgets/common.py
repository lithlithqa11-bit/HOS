from datetime import datetime
from PySide6.QtCore import Qt, QDate, QDateTime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
                              QFormLayout, QComboBox, QSpinBox, QDateEdit, QDateTimeEdit, QCheckBox,
                              QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox)


def button(text, callback, layout=None):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    if layout is not None:
        layout.addWidget(widget)
    return widget


def line(placeholder=''):
    widget = QLineEdit()
    widget.setPlaceholderText(placeholder)
    return widget


def combo(options):
    widget = QComboBox()
    for text, value in options:
        widget.addItem(text, value)
    return widget


def integer(value=1, maximum=2147483647):
    widget = QSpinBox()
    widget.setRange(1, maximum)
    widget.setValue(value)
    return widget


def date_input():
    widget = QDateEdit(QDate(2000, 1, 1))
    widget.setCalendarPopup(True)
    widget.setDisplayFormat('yyyy-MM-dd')
    return widget


def time_input():
    widget = QDateTimeEdit(QDateTime.currentDateTime().addDays(1))
    widget.setCalendarPopup(True)
    widget.setDisplayFormat('yyyy-MM-dd HH:mm')
    return widget


def value(widget):
    if isinstance(widget, QComboBox):
        return widget.currentData()
    if isinstance(widget, QSpinBox):
        return widget.value()
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QDateEdit):
        return widget.date().toString('yyyy-MM-dd')
    if isinstance(widget, QDateTimeEdit):
        return datetime.fromtimestamp(widget.dateTime().toSecsSinceEpoch()).astimezone().isoformat()
    return widget.text().strip()


class Form(QDialog):
    def __init__(self, title, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.fields = fields
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for key, label, widget in fields:
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def data(self):
        return {key: value(widget) for key, _, widget in self.fields}


class DataTable(QTableWidget):
    def __init__(self, columns):
        super().__init__(0, len(columns))
        self.columns, self.rows = columns, []
        self.setHorizontalHeaderLabels([label for key, label in columns])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setMinimumHeight(160)

    def populate(self, rows):
        self.rows = rows
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, (key, _) in enumerate(self.columns):
                raw = row.get(key, '')
                if isinstance(raw, list):
                    raw = '، '.join(map(str, raw))
                item = QTableWidgetItem(str(raw) if raw is not None else '—')
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
                self.setItem(i, j, item)

    def selected(self):
        selected = self.selectionModel().selectedRows()
        index = selected[0].row() if selected else self.currentRow()
        return self.rows[index] if 0 <= index < len(self.rows) else None


class Page(QWidget):
    def __init__(self, window, title, subtitle=''):
        super().__init__()
        self.window = window
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 20)
        heading = QLabel(title)
        heading.setObjectName('pageTitle')
        self.layout.addWidget(heading)
        if subtitle:
            label = QLabel(subtitle)
            label.setWordWrap(True)
            label.setObjectName('subtitle')
            self.layout.addWidget(label)
        self.actions = QHBoxLayout()
        self.layout.addLayout(self.actions)

    def request(self, method, path, data=None, done=None, failed=None):
        self.window.request(method, path, data, done or (lambda _: self.refresh()), failed)

    def refresh(self):
        pass

    def choose(self, table):
        row = table.selected()
        if row is None:
            self.window.message('حدد سجلاً من الجدول أولاً')
        return row
