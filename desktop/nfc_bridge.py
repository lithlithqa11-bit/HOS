"""Serial bridge for the NodeMCU ESP8266 and RC522 reader."""
import json
import re
import threading
import time

import serial


TOKEN = re.compile(r'[0-9a-f]{64}\Z')
_PORT_LOCK = threading.Lock()


class NFCError(Exception):
    pass


class SerialRC522Reader:
    def __init__(self, port='COM6', baudrate=115200, timeout=20):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

    @staticmethod
    def _message(line):
        if len(line) > 512:
            raise NFCError('استجابة طويلة غير صالحة من القارئ')
        try:
            body = json.loads(line)
        except (UnicodeDecodeError, ValueError):
            return None  # ESP8266 boot output is not JSON.
        return body if isinstance(body, dict) else None

    def _open(self):
        try:
            return serial.Serial(self.port, self.baudrate, timeout=.25, write_timeout=2)
        except serial.SerialException as error:
            raise NFCError(f'تعذر فتح منفذ القارئ {self.port}. أغلق Serial Monitor وتحقق من التوصيل.') from error

    def _next(self, connection, deadline):
        while time.monotonic() < deadline:
            try:
                body = self._message(connection.readline())
            except serial.SerialException as error:
                raise NFCError('انقطع اتصال القارئ التسلسلي') from error
            if not body:
                continue
            if body.get('status') == 'reader_not_detected':
                raise NFCError('لوحة ESP8266 تعمل لكن قارئ RC522 غير مكتشف؛ تحقق من 3.3V وأسلاك SPI')
            if 'uid' in body and 'token' not in body and body.get('ok') is True:
                raise NFCError('برنامج اللوحة قديم ويرسل UID فقط؛ حدّث برنامج ESP8266')
            return body
        return None

    def _operate(self, operation, token=None):
        if not _PORT_LOCK.acquire(blocking=False):
            raise NFCError('القارئ مشغول بعملية أخرى')
        try:
            with self._open() as connection:
                deadline = time.monotonic() + self.timeout
                # Opening a NodeMCU serial port can reset it. Wait for its ready line.
                ready_deadline = min(deadline, time.monotonic() + 4)
                while time.monotonic() < ready_deadline:
                    body = self._next(connection, ready_deadline)
                    if body is None or body.get('status') == 'ready':
                        break
                command = f'WRITE {token}\n' if operation == 'write' else 'READ\n'
                try:
                    connection.write(command.encode('ascii'))
                    connection.flush()
                except (serial.SerialException, serial.SerialTimeoutException) as error:
                    raise NFCError('تعذر إرسال الأمر إلى القارئ') from error
                acknowledgement = 'write_ready' if operation == 'write' else 'read_ready'
                acknowledged = False
                while True:
                    body = self._next(connection, deadline)
                    if body is None:
                        raise NFCError('انتهت مهلة انتظار البطاقة أو استجابة القارئ')
                    if not acknowledged:
                        if body.get('status') == acknowledgement:
                            acknowledged = True
                        elif body.get('status') == 'invalid_command':
                            raise NFCError('رفض القارئ الأمر؛ تحقق من نسخة برنامج ESP8266')
                        continue
                    if body.get('status') in ('ready', 'reader_connected', 'write_ready', 'read_ready'):
                        continue
                    if body.get('ok') is False:
                        status = body.get('status', 'reader_error')
                        messages = {
                            'read_timeout': 'انتهت مهلة القراءة. قرّب البطاقة إلى RC522 ثم حاول مجدداً',
                            'write_timeout': 'انتهت مهلة الكتابة. قرّب البطاقة التجريبية ثم حاول مجدداً',
                            'card_not_provisioned': 'البطاقة بلا رمز. أصدر رمزاً من ملف المريض واكتبه عليها أولاً',
                            'unsupported_card_or_auth_failed': 'البطاقة غير مدعومة أو تعذّر فتحها. استخدم MIFARE Classic 1K بالمفتاح الافتراضي',
                            'write_or_verification_failed': 'فشلت كتابة البطاقة أو التحقق منها. ثبّتها على القارئ وأعد المحاولة',
                        }
                        raise NFCError(messages.get(status, f'تعذرت قراءة أو كتابة البطاقة: {status}'))
                    if operation == 'write':
                        if body.get('written') is True:
                            return body
                    elif 'token' in body:
                        if not TOKEN.fullmatch(str(body['token'])):
                            raise NFCError('رمز غير صالح من القارئ')
                        return body
        finally:
            _PORT_LOCK.release()

    def read(self):
        return self._operate('read')

    def write(self, token):
        if not TOKEN.fullmatch(token):
            raise NFCError('رمز بطاقة غير صالح')
        return self._operate('write', token)
