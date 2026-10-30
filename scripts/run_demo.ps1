$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
$pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path $pythonExe) -or -not (Test-Path '.env')) {
    throw 'Run scripts/bootstrap.ps1 first, or follow Docker setup in README.'
}
# Start the isolated bundled cluster only for the dedicated local configuration.
if (Select-String -LiteralPath '.env' -Pattern ':55432/medilink' -Quiet) {
    & $pythonExe -m scripts.setup_local
    if ($LASTEXITCODE -ne 0) { throw 'Local PostgreSQL unavailable' }
}
& $pythonExe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
& $pythonExe -m scripts.seed
if ($LASTEXITCODE -ne 0) { throw 'Seed failed' }
New-Item -ItemType Directory -Path '.runtime' -Force | Out-Null
$apiProcess = $null
try {
    $response = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2
    if ($response.database -ne 'postgresql') { throw 'Unexpected server at port 8000' }
} catch {
    $apiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput '.runtime/api.stdout.log' -RedirectStandardError '.runtime/api.stderr.log'
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 250
        if ($apiProcess.HasExited) { throw 'API failed to start; see .runtime/api.stderr.log' }
        try {
            $response = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 1
            if ($response.status -eq 'ok') { $ready = $true; break }
        } catch { }
    }
    if (-not $ready) { Stop-Process -Id $apiProcess.Id; throw 'API did not become ready' }
}
try {
    & $pythonExe -m desktop.main
} finally {
    if ($apiProcess -and -not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }
}
