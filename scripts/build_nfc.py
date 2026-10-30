"""Build PC/SC adapter with MinGW/Ninja; handles Windows non-ASCII workspace paths."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys


def short_path(path):
    path = str(Path(path).resolve())
    if os.name != 'nt':
        return path
    buffer = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(path, buffer, len(buffer)):
        return buffer.value
    return path


def main():
    root = short_path(Path(__file__).resolve().parents[1])
    try:
        import cmake
        executable = short_path(Path(cmake.CMAKE_BIN_DIR) / ('cmake.exe' if os.name == 'nt' else 'cmake'))
    except ImportError:
        executable = shutil.which('cmake')
    if not executable:
        sys.exit('Install CMake, or run: python -m pip install cmake')
    source, build = str(Path(root) / 'nfc_cpp'), str(Path(root) / 'nfc_cpp/build')
    args = [executable, '--fresh', '-S', source, '-B', build]
    mingw = Path(os.getenv('MINGW_BIN', 'C:/msys64/ucrt64/bin'))
    environment = os.environ.copy()
    if (mingw / 'g++.exe').exists() and (mingw / 'ninja.exe').exists():
        environment['PATH'] = str(mingw) + os.pathsep + environment.get('PATH', '')
        args += ['-G', 'Ninja', '-DCMAKE_CXX_COMPILER=' + str(mingw / 'g++.exe'),
                 '-DCMAKE_MAKE_PROGRAM=' + str(mingw / 'ninja.exe'), '-DCMAKE_BUILD_TYPE=Release']
    subprocess.run(args, check=True, cwd=root, env=environment)
    subprocess.run([executable, '--build', build, '--config', 'Release'], check=True, cwd=root, env=environment)


if __name__ == '__main__':
    main()
