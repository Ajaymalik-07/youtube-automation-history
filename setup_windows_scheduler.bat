@echo off
echo ===============================================================
echo   YAAS Windows Daily Scheduled Task Installer
echo ===============================================================
echo.
cd /d "%~dp0"
call .venv\Scripts\python.exe register_scheduler.py
echo.
pause
