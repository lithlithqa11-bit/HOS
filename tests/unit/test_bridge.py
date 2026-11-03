import json

import pytest

from desktop.nfc_bridge import NFCError, SerialRC522Reader


class FakePort:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def readline(self):
        return next(self.messages, b'')

    def write(self, data):
        self.sent.append(data)

    def flush(self):
        pass


def wire(body):
    return (json.dumps(body) + '\n').encode('ascii')


def test_serial_reader_ignores_boot_and_diagnostics(monkeypatch):
    port = FakePort([b'boot noise\n', wire({'ok': True, 'status': 'ready'}),
                     wire({'ok': True, 'status': 'reader_connected'}),
                     wire({'ok': True, 'status': 'read_ready'}),
                     wire({'ok': True, 'token': 'a' * 64})])
    monkeypatch.setattr('desktop.nfc_bridge.serial.Serial', lambda *a, **k: port)
    assert SerialRC522Reader('COM6').read()['token'] == 'a' * 64
    assert port.sent == [b'READ\n']


def test_serial_reader_rejects_old_uid_firmware(monkeypatch):
    port = FakePort([wire({'ok': True, 'uid': 'aabbccdd'})])
    monkeypatch.setattr('desktop.nfc_bridge.serial.Serial', lambda *a, **k: port)
    with pytest.raises(NFCError, match='UID'):
        SerialRC522Reader('COM6').read()


def test_serial_write_waits_for_ready_and_verified_result(monkeypatch):
    port = FakePort([wire({'ok': True, 'status': 'ready'}),
                     wire({'ok': False, 'status': 'card_not_provisioned'}),
                     wire({'ok': True, 'status': 'write_ready'}),
                     wire({'ok': True, 'written': True})])
    monkeypatch.setattr('desktop.nfc_bridge.serial.Serial', lambda *a, **k: port)
    assert SerialRC522Reader('COM6').write('a' * 64)['written'] is True
    assert port.sent == [b'WRITE ' + b'a' * 64 + b'\n']


def test_serial_reader_reports_missing_rc522(monkeypatch):
    port = FakePort([wire({'ok': False, 'status': 'reader_not_detected'})])
    monkeypatch.setattr('desktop.nfc_bridge.serial.Serial', lambda *a, **k: port)
    with pytest.raises(NFCError, match='RC522'):
        SerialRC522Reader('COM6').read()
