"""Serial bridge for MediLink NFC firmware on RC522 or PN532 readers."""
import json
import re
import threading
import time

import serial


TOKEN = re.compile(r'[0-9a-f]{64}\Z')
_PORT_LOCK = threading.Lock()
_PENDING_FEEDBACK = {}


class NFCError(Exception):
    pass


class SerialRC522Reader:
    def __init__(self, port='COM3', baudrate=115200, timeout=20):
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

    @staticmethod
    def _close(connection):
        close = getattr(connection, 'close', None)
        if close is not None:
            close()
        else:
            connection.__exit__(None, None, None)

    def _next(self, connection, deadline):
        while time.monotonic() < deadline:
            try:
                body = self._message(connection.readline())
            except serial.SerialException as error:
                raise NFCError('انقطع اتصال القارئ التسلسلي') from error
            if not body:
                continue
            if body.get('status') == 'reader_not_detected':
                raise NFCError('القارئ غير مكتشف؛ تحقق من منفذ اللوحة والطاقة والتوصيلات ووضع I2C أو SPI')
            if 'uid' in body and 'token' not in body and body.get('ok') is True:
                raise NFCError('برنامج اللوحة يرسل UID فقط؛ ارفع برنامج MediLink المناسب للقارئ المختار')
            return body
        return None

    def _operate(self, operation, token=None):
        if not _PORT_LOCK.acquire(blocking=False):
            raise NFCError('القارئ مشغول بعملية أخرى')
        connection = None
        keep_connection = False
        try:
            stale = _PENDING_FEEDBACK.pop(self.port, None)
            if stale is not None:
                self._close(stale)
            connection = self._open()
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
                        'read_timeout': 'انتهت مهلة القراءة. قرّب البطاقة إلى القارئ ثم حاول مجدداً',
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
                    if 'PN532' in str(body.get('reader', '')):
                        _PENDING_FEEDBACK[self.port] = connection
                        keep_connection = True
                    return body
        finally:
            if connection is not None and not keep_connection:
                self._close(connection)
            _PORT_LOCK.release()

    def read(self):
        return self._operate('read')

    def write(self, token):
        if not TOKEN.fullmatch(token):
            raise NFCError('رمز بطاقة غير صالح')
        return self._operate('write', token)

    def feedback(self, allowed):
        """Apply the database decision to the ESP32-S3 LEDs and buzzer."""
        if not _PORT_LOCK.acquire(blocking=False):
            raise NFCError('القارئ مشغول بعملية أخرى')
        connection = _PENDING_FEEDBACK.pop(self.port, None)
        if connection is None:
            _PORT_LOCK.release()
            raise NFCError('انتهت جلسة البطاقة؛ أعد قراءتها')
        try:
            command = 'FEEDBACK ALLOW\n' if allowed else 'FEEDBACK DENY\n'
            connection.write(command.encode('ascii'))
            connection.flush()
            ack_deadline = time.monotonic() + 4
            while time.monotonic() < ack_deadline:
                body = self._next(connection, ack_deadline)
                if body and body.get('status') == 'feedback_applied':
                    return
            raise NFCError('لم يستجب القارئ لإشارة السماح أو الرفض')
        except (serial.SerialException, serial.SerialTimeoutException) as error:
            raise NFCError('تعذر إرسال إشارة النتيجة إلى القارئ') from error
        finally:
            self._close(connection)
            _PORT_LOCK.release()
