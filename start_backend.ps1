$venv_python = "D:\Downloads\CASHFLOW-emmanuel(1)\CASHFLOW-emmanuel\banking-agent\.venv\Scripts\python.exe"
$workdir = "D:\Downloads\CASHFLOW-emmanuel(1)\CASHFLOW-emmanuel"

$env:KEY_PASSPHRASE = "cashflow-dev-passphrase-2026"

& "$venv_python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000