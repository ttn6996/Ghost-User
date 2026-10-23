# Ghost-User: Run all backend, worker, security, and e2e integration tests
$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "$PSScriptRoot\..;$PSScriptRoot\..\apps\api"
$env:ENVIRONMENT = "test"
$env:DATABASE_URL = "sqlite:///:memory:"
$env:ALLOW_LOCAL_TARGETS = "true"

$pytestExe = "$PSScriptRoot\..\.venv\Scripts\pytest.exe"
if (-not (Test-Path $pytestExe)) {
    Write-Error "Virtual environment pytest executable not found at $pytestExe. Please run python -m venv .venv and pip install -r requirements.txt first."
    exit 1
}

Write-Host "Running Ghost-User automated test suite..." -ForegroundColor Cyan
& $pytestExe -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "One or more tests failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "All tests passed successfully!" -ForegroundColor Green
exit 0
