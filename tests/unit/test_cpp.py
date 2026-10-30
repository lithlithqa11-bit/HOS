import json
from pathlib import Path
import subprocess
import pytest

EXECUTABLE = Path('nfc_cpp/build/nfc_reader.exe')


@pytest.mark.skipif(not EXECUTABLE.exists(), reason='Build the optional PC/SC executable first')
@pytest.mark.parametrize('args,input_text,error', [
    (['--invalid'], None, 'usage_read_or_explicit_type2_write'),
    (['--write-token-stdin', '--confirm-type2'], 'invalid', 'invalid_token')])
def test_compiled_cpp_json_errors(args, input_text, error):
    result = subprocess.run([str(EXECUTABLE.resolve()), *args], input=input_text,
                             capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert result.returncode == 1
    assert json.loads(result.stdout) == {'ok': False, 'error': error}
