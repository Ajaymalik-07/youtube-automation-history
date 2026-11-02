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

:: Create or update scheduled task: Hourly auto catch-up
schtasks /create /tn "YAAS_Hourly_YouTube_Catchup" /tr "\"%PYTHON_EXE%\" \"%SCRIPT_DIR%automation.py\" --auto" /sc hourly /mo 1 /f /rl HIGHEST

:: Also create or update daily morning run
schtasks /create /tn "YAAS_Daily_YouTube_Studio" /tr "\"%PYTHON_EXE%\" \"%SCRIPT_DIR%automation.py\" --auto" /sc daily /st 06:00 /f /rl HIGHEST

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===============================================================
    echo [SUCCESS] Windows Tasks registered successfully!
    echo 1. 'YAAS_Hourly_YouTube_Catchup' runs every hour to catch up
    echo    all due Shorts (9AM, 12PM, 4PM, 7PM, 10PM IST) & Longform (7PM).
    echo 2. 'YAAS_Daily_YouTube_Studio' runs daily at 06:00 AM IST.
    echo ===============================================================
) else (
    echo.
    echo [NOTICE] If permission was denied, right-click this file and select 'Run as administrator'.
)

echo.
pause
