@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please follow HOME_SETUP.md to install the local environment first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" check_runtime.py
if errorlevel 1 (
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
