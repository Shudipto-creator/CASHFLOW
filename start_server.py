import subprocess
import sys
import time
import os
import requests

# Change to project directory
os.chdir(r"D:\Downloads\CASHFLOW-emmanuel(1)\CASHFLOW-emmanuel")

# Set environment variable
os.environ['KEY_PASSPHRASE'] = 'cashflow-dev-passphrase-2026'

# Start backend server
proc = subprocess.Popen([
    "banking-agent\\.venv\\Scripts\\python.exe",
    "-m", "uvicorn", "app.main:app",
    "--host", "127.0.0.1",
    "--port", "8000"
], env=os.environ)

print("Backend server starting on http://127.0.0.1:8000")

# Wait for server to start
print("Waiting for server to start...")
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
print('=== FastAPI Backend Running on http://127.0.0.1:8000 ===')
print()
print('Available endpoints:')
print('  GET  /api/banking/tools')
print(fr'  POST /api/banking/transfer/prepare')
print(f'POST   /api/banking/transfer/execute')
print(f'POST   /api/banking/transfer/execute/{{intent_id}}/approve')
print(f'POST   /api/banking/mfa/challenge')
print(f'GET    /api/banking/fx/rates?from_currency=CNY&to_currency=USD')
print(f'POST   /api/banking/fx/convert')
print()
print('Press Ctrl+C to stop server.')
print()

try:
    proc.wait()
except KeyboardInterrupt:
    print("\nShutting down backend server...")
    proc.terminate()
    proc.wait()