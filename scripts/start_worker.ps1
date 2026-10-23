# Start Ghost-User Background Playwright Worker
$env:PYTHONPATH = "$PSScriptRoot\..;$PSScriptRoot\..\apps\api"
Write-Host "Starting Ghost-User Test Execution Worker..." -ForegroundColor Cyan
& "$PSScriptRoot\..\.venv\Scripts\python.exe" "$PSScriptRoot\..\apps\worker\worker.py"
