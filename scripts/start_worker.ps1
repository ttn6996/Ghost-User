# Start Ghost-User Background Playwright Worker
$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "$PSScriptRoot\..;$PSScriptRoot\..\apps\api"
$pythonExe = "$PSScriptRoot\..\.venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Error "Virtual environment python executable not found at $pythonExe. Please set up .venv first."
    exit 1
}

Write-Host "Starting Ghost-User Test Execution Worker..." -ForegroundColor Cyan
& $pythonExe "$PSScriptRoot\..\apps\worker\worker.py"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
