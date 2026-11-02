@echo off
title Ghost-User Launcher
echo ========================================================
echo   Starting Ghost-User Autonomous UI Testing Platform
echo ========================================================

set PYTHONPATH=.

REM 1. Start API Backend (FastAPI on Port 8000)
start "Ghost-User API" cmd /k "call .venv\Scripts\activate.bat && set PYTHONPATH=. && uvicorn app.main:app --host 127.0.0.1 --port 8000"

REM 2. Start Background Worker (Playwright Runner)
start "Ghost-User Worker" cmd /k "call .venv\Scripts\activate.bat && set PYTHONPATH=. && python -m apps.worker.main"

REM 3. Start Next.js Web UI (Port 3000)
start "Ghost-User Dashboard" cmd /k "npm run web:dev"

echo.
echo Waiting for services to initialize...
timeout /t 4 /nobreak >nul

echo.
echo ========================================================
echo   Ghost-User is LIVE!
echo   - Web Dashboard:  http://localhost:3000
echo   - API Backend:    http://127.0.0.1:8000/docs
echo ========================================================

start http://localhost:3000

