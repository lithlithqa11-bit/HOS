$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$out = Join-Path $root 'dist'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$gxx = 'C:\msys64\ucrt64\bin\g++.exe'
$windres = 'C:\msys64\ucrt64\bin\windres.exe'
if (-not (Test-Path $gxx)) { throw "Missing MinGW compiler: $gxx" }
if (-not (Test-Path $windres)) { throw "Missing windres: $windres" }
& $windres desktop/launcher.rc -O coff -o .runtime/launcher-res.o
# MinGW on Windows can fail to link output paths containing Arabic characters.
# Use the short 8.3 alias when available, while keeping the user-facing path unchanged.
$shortRoot = (cmd /c "for %I in (`"$root`") do @echo %~sI").Trim()
if (-not $shortRoot) { $shortRoot = $root }
$shortOut = Join-Path $shortRoot 'dist\MediLink-NFC.exe'
& $gxx -std=c++17 -mwindows -static -O2 desktop/launcher.cpp .runtime/launcher-res.o -o $shortOut
if ($LASTEXITCODE -ne 0) { throw 'Launcher build failed' }
$shortcutScript = @"
`$ws = New-Object -ComObject WScript.Shell
`$shortcut = `$ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\MediLink NFC.lnk')
`$shortcut.TargetPath = '$out\MediLink-NFC.exe'
`$shortcut.WorkingDirectory = '$root'
`$shortcut.IconLocation = '$root\desktop\assets\medilink.ico,0'
`$shortcut.Description = 'MediLink NFC — Smart Hospital Management System'
`$shortcut.Save()
"@
Invoke-Expression $shortcutScript
Write-Host "Built $out\MediLink-NFC.exe and Desktop\MediLink NFC.lnk"
