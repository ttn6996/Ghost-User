# Run all backend, worker, and e2e integration tests
$env:PYTHONPATH = "$PSScriptRoot\..;$PSScriptRoot\..\apps\api"
$env:ENVIRONMENT = "test"
$env:DATABASE_URL = "sqlite:///:memory:"
$env:ALLOW_LOCAL_TARGETS = "true"

Write-Host "Running Ghost-User automated test suite..." -ForegroundColor Cyan
& "$PSScriptRoot\..\.venv\Scripts\pytest.exe" -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "All tests passed successfully!" -ForegroundColor Green
