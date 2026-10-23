# Start Ghost-User FastAPI server
$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "$PSScriptRoot\..;$PSScriptRoot\..\apps\api"
$uvicornExe = "$PSScriptRoot\..\.venv\Scripts\uvicorn.exe"

if (-not (Test-Path $uvicornExe)) {
    Write-Error "Virtual environment uvicorn executable not found at $uvicornExe. Please set up .venv first."
    exit 1
}

Write-Host "Starting Ghost-User API Server on http://127.0.0.1:8000..." -ForegroundColor Cyan
& $uvicornExe app.main:app --host 127.0.0.1 --port 8000 --reload
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
