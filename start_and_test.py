import subprocess
import sys
import os
import time
import requests

# Paths
repo_root = r"D:\Downloads\CASHFLOW-emmanuel(1)\CASHFLOW-emmanuel"
banking_agent_venv_python = os.path.join(repo_root, "banking-agent", ".venv", "Scripts", "python.exe")

# Start backend server
print("Starting backend server...")
proc = subprocess.Popen([
    VENV_PY,
    "-m", "uvicorn", "app.main:app",
    "--host", "127.0.0.1",
    "--port", "8000"
], cwd=REPO_ROOT, env={**os.environ, "KEY_PASSPHRASE": "cashflow-dev-passphrase-2026"})

# Wait for server to start
print("Waiting for backend to start...")
for i in range(30):
    try:
        r = requests.get("http://127.0.0.1:8000/api/banking/tools", timeout=2)
        if r.status_code in (200, 401):
            print(f"Backend ready! Status: {r.status_code}")
            break
    except Exception:
        pass
    time.sleep(1)
else:
    print("Backend failed to start!")
    proc.terminate()
    sys.exit(1)

print()
print("=== Running FX Endpoint Tests ===")

# Test FX rates
r = signed_request('GET', '/api/banking/fx/rates?from_currency=CNY&to_currency=USD')
print('FX rates CNY->USD:', r.status_code, r.text[:200])

r = signed_request('POST', '/api/banking/fx/convert', {'from_currency': 'CNY', 'to_currency': 'USD', 'amount': 1000})
print(f'FX Convert CNY->USD 1000:', r.status_code, r.text[:200])

r = signed_request('POST', '/api/banking/fx/convert', {'from_currency': 'USD', 'to_currency': 'CNY', 'amount': 100})
print('FX Convert USD->CNY 100:', r.status_code, r.text[:200])

r = signed_request('POST', '/api/banking/fx/convert', {'from_currency': 'CNY', 'to_currency': 'EUR', 'amount': 1000})
print('FX Convert CNY->EUR 1000:', r.status_code, r.text[:200])

print()
print('=== All FX endpoint tests completed ===')
proc.terminate()