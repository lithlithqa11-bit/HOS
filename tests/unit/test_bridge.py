import json
import subprocess
from types import SimpleNamespace
import pytest
from desktop.nfc_bridge import MockNFCReader, RealNFCReader, NFCError


def test_mock_token():
    assert MockNFCReader().read('a' * 64)['token'] == 'a' * 64
    for invalid in ('', '12345678', 'G' * 64):
        with pytest.raises(NFCError):
            MockNFCReader().read(invalid)


@pytest.mark.parametrize('stdout,returncode', [('not json', 0), ('[]', 0),
    ('{"ok":false,"error":"no_reader"}', 1), ('{"ok":true,"uid":"1234"}', 0)])
def test_invalid_cpp_protocol(monkeypatch, stdout, returncode):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout=stdout, returncode=returncode))
    with pytest.raises(NFCError):
        RealNFCReader('reader.exe').read()


def test_real_bridge_subprocess_json(monkeypatch):
    def run(args, **kwargs):
        assert args[1] == '--read' and kwargs['shell'] is False
        assert kwargs['timeout'] == 15
        return SimpleNamespace(stdout=json.dumps({'ok': True, 'token': 'a' * 64}), returncode=0)
    monkeypatch.setattr(subprocess, 'run', run)
    assert RealNFCReader('reader.exe').read()['token'] == 'a' * 64


def test_missing_executable():
    with pytest.raises(NFCError):
        RealNFCReader('definitely_not_present.exe').read()
