@echo off
cd /d "D:\Downloads\CASHFLOW-emmanuel(1)\CASHFLOW-emmanuel"
set KEY_PASSPHRASE=cashflow-dev-passphrase-2026
"banking-agent\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause