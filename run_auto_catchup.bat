@echo off
cd /d "%~dp0"
call .venv\Scripts\python.exe automation.py --auto
