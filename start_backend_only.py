import subprocess
import sys
import os

REPO = "D:\\Downloads\\CASHFLOW-emmanuel(1)\\CASHFLOW-emmanuel"

print("Starting backend server...")
proc = subprocess.Popen([
    r"banking-agent\.venv\Scripts\\python.exe",
    "-m", "uvicorn", "app.main:app",
    "--host", "127.0.0.1",
    "--port", "8000"
], env={**os.environ, "KEY_PASSPHRASE": "cashflow-dev-passphrase-2026"}, cwd=REPO)

print("Backend server PID:", proc.pid)
print("Backend URL: http://127.0.0.1:8000")
print()
print("Server is running. You can now run the test in another terminal:")
print("  python fix_test.py")
print()
print("Press Ctrl+C to stop the server.")
proc.wait()