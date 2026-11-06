@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=banking-agent\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo No project virtual environment was found. Create one and install requirements.txt.
  pause
  exit /b 1
)

if "%KEY_PASSPHRASE%"=="" set "KEY_PASSPHRASE=finn-local-development-only"
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
