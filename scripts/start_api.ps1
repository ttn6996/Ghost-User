# Start Ghost-User FastAPI server
$env:PYTHONPATH = "$PSScriptRoot\..;$PSScriptRoot\..\apps\api"
Write-Host "Starting Ghost-User API Server on http://127.0.0.1:8000..." -ForegroundColor Cyan
& "$PSScriptRoot\..\.venv\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port 8000 --reload
