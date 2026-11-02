@echo off
title Ghost-User Launcher
echo ========================================================
echo   Starting Ghost-User Autonomous UI Testing Platform
echo ========================================================

REM Check virtualenv
if exist ".venv\Scripts\activate.bat" (
    set "ACTIVATE_CMD=call .venv\Scripts\activate.bat &&"
) else (
    set "ACTIVATE_CMD="
)

REM 1. Start API Backend (FastAPI on Port 8000)
start "Ghost-User API" cmd /k "%ACTIVATE_CMD% set PYTHONPATH=.^;apps\api && uvicorn app.main:app --host 127.0.0.1 --port 8000"

REM 2. Start Background Worker (Playwright Runner)
start "Ghost-User Worker" cmd /k "%ACTIVATE_CMD% set PYTHONPATH=.^;apps\api && python -m apps.worker.worker"

REM 3. Start Next.js Web UI (Port 3000)
start "Ghost-User Dashboard" cmd /k "npm run web:dev"

echo.
echo Waiting for services to initialize...
timeout /t 5 /nobreak >nul

echo.
echo ========================================================
echo   Ghost-User is LIVE!
echo   - Web Dashboard:  http://localhost:3000
echo   - API Backend:    http://127.0.0.1:8000/docs
echo ========================================================

start http://localhost:3000
