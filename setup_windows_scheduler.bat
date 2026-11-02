@echo off
echo ===============================================================
echo   YAAS Windows Daily Scheduled Task Installer
echo ===============================================================
echo.
echo This script registers a daily Windows Task to automatically run:
echo   python automation.py --run-all
echo every day at 06:00 AM, ensuring weekend uploads (Sat and Sun)
echo execute even if you forget to open run_automation_daemon.bat.
echo.

set SCRIPT_DIR=%~dp0
set PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment Python not found at %PYTHON_EXE%
    pause
    exit /b 1
)

:: Create or update scheduled task
schtasks /create /tn "YAAS_Daily_YouTube_Studio" /tr "\"%PYTHON_EXE%\" \"%SCRIPT_DIR%automation.py\" --run-all" /sc daily /st 06:00 /f /rl HIGHEST

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===============================================================
    echo [SUCCESS] Windows Task 'YAAS_Daily_YouTube_Studio' created!
    echo It will execute daily at 06:00 AM IST (every Monday-Sunday).
    echo ===============================================================
) else (
    echo.
    echo [NOTICE] If permission was denied, right-click this file and select 'Run as administrator'.
)

echo.
pause
