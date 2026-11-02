@echo off
title Ghost-User Terminator
echo ========================================================
echo   Stopping all Ghost-User background services...
echo ========================================================

taskkill /F /T /FI "WINDOWTITLE eq Ghost-User API*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Ghost-User Worker*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq Ghost-User Dashboard*" >nul 2>&1

echo Ghost-User services have been cleanly terminated.
