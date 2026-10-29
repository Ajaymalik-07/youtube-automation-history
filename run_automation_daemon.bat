@echo off
title YAAS Autonomous History Studio Daemon
cd /d "%~dp0"
echo Starting Autonomous Daily History Studio Daemon (IST Timezone)...
call .venv\Scripts\python.exe automation.py --daemon
pause
