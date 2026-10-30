import json
from pathlib import Path
import re
import subprocess


class NFCError(Exception):
    pass


class MockNFCReader:
    def read(self, token=''):
        if not re.fullmatch(r'[0-9a-f]{64}', token):
            raise NFCError('أدخل الرمز التجريبي الصادر من الخادم (64 خانة)')
        return {'ok': True, 'token': token, 'reader': 'Mock NFC'}


class RealNFCReader:
    def __init__(self, executable):
        self.executable = str(Path(executable).resolve())

    def _run(self, args):
        try:
            result = subprocess.run([self.executable, *args], capture_output=True, text=True,
                                     encoding='utf-8', timeout=15, shell=False,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except FileNotFoundError:
            raise NFCError('برنامج قارئ NFC غير موجود؛ ابنِ nfc_cpp أولاً') from None
        except subprocess.TimeoutExpired:
            raise NFCError('انتهت مهلة انتظار قارئ NFC') from None
        except OSError as error:
            raise NFCError('تعذر تشغيل برنامج NFC') from error
        try:
            body = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise NFCError('استجابة JSON غير صالحة من قارئ NFC') from None
        if not isinstance(body, dict) or result.returncode or body.get('ok') is not True:
            message = body.get('error', 'reader_failed') if isinstance(body, dict) else 'reader_failed'
            raise NFCError(f'خطأ قارئ NFC: {message}')
        return body

    def read(self, token=''):
        body = self._run(['--read'])
        if not re.fullmatch(r'[0-9a-f]{64}', body.get('token', '')):
            raise NFCError('البطاقة لا تحتوي رمز MediLink صالحاً؛ UID وحده غير مقبول')
        return body

    def write(self, token):
        if not re.fullmatch(r'[0-9a-f]{64}', token):
            raise NFCError('رمز بطاقة غير صالح')
        # Token goes to stdin, never command line or diagnostic logs.
        try:
            result = subprocess.run([self.executable, '--write-token-stdin', '--confirm-type2'],
                                    input=token, capture_output=True, text=True, encoding='utf-8', timeout=15,
                                    shell=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            body = json.loads(result.stdout)
            if result.returncode or not isinstance(body, dict) or body.get('ok') is not True:
                raise NFCError('تعذرت كتابة البطاقة؛ استخدم بطاقة Type 2 تجريبية متوافقة')
            return body
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            raise NFCError('تعذر الاتصال بقارئ NFC لكتابة البطاقة') from error
