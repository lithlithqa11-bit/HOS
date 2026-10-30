#include <windows.h>
#include <filesystem>
#include <string>

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    wchar_t module[MAX_PATH]{};
    GetModuleFileNameW(nullptr, module, MAX_PATH);
    std::filesystem::path root = std::filesystem::path(module).parent_path().parent_path();
    std::filesystem::path python = root / L".venv" / L"Scripts" / L"python.exe";
    std::filesystem::path launcher = root / L"desktop" / L"launch_direct.py";
    std::wstring command = L"\"" + python.wstring() + L"\" \"" + launcher.wstring() + L"\"";
    STARTUPINFOW startup{sizeof(startup)};
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(nullptr,
                        command.data(), nullptr, nullptr, FALSE, CREATE_NEW_CONSOLE, nullptr,
                        root.wstring().c_str(), &startup, &process)) {
        MessageBoxW(nullptr, L"تعذر تشغيل MediLink NFC. شغّل scripts\\run_demo.ps1 للتحقق من الإعداد.",
                    L"MediLink NFC", MB_ICONERROR | MB_OK);
        return 1;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
