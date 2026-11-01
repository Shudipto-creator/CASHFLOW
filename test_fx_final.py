import subprocess
import sys
import time
import requests

# Start backend server
print("Starting FastAPI backend on port 8000...")
proc = subprocess.Popen([
    r"D:\Downloads\CASHFLOW-emmanuel(1)\CASHFLOW-emmanuel\banking-agent\.venv\Scripts\python.exe",
    "-m", "uvicorn", "app.main:app",
    "--host", "127.0.0.1",
    "--port", "8000"
], env={**os.environ if 'os' in dir() else {}, "KEY_PASSPHRASE": "cashflow-dev-passphrase-2026"}, cwd=r"D:\Downloads\CASHFLOW-emmanuel(1)\CASHFLOW-emmanuel")

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

# Test endpoints
email = f"test_{int(time.time())}@example.com"
password = "Password123"

# Register
r = requests.post(BASE + "/api/auth/register", json={
    'email': email, 'password': password,
    'company_name': 'Test Co', 'business_type': 'Retail'
})
print(f"REGISTER: {r.status_code}")

# Login
r = requests.post(BASE + '/api/auth/login', json={'email': email, 'password': password})
print(f'LOGIN: {r.status_code}')
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Generate client key
private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()
public_pem = public_key.public_bytes(encoding=Encoding.PEM, format=PublicFormat.SubjectPublicKeyInfo)
pub_b64 = base64.b64encode(public_pem).decode('ascii')
client_id = 'client_' + ''.join(secrets.choice('0123456789abcdef') for _ in range(16))

def canonicalize_deep(value):
    if value is None or not isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, list):
        return '[' + ','.join(canonicalize_deep(v) for v in value) + ']'
    sorted_keys = sorted(value.keys())
    parts = [json.dumps(k) + ':' + canonicalize_deep(value[k]) for k in sorted_keys]
    return '{' + ','.join(parts) + '}'

def sign_body(body):
    canonical = canonicalize_deep(body)
    sig = private_key.sign(canonical.encode('utf-8'))
    return base64.b64encode(sig).decode('ascii')

def compute_stid(method, path, body, client_id):
    canonical = canonicalize_deep(body)
    payload = f'{method.upper()}|{path}|{canonical}|{client_id}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def signed_request(method, path, body=None):
    signature = sign_body(body)
    stid = compute_stid(method, path, body, client_id)
    h = dict(headers)
    h.update({
        'X-Request-Signature': signature,
        'X-Request-STID': stid,
        'X-Client-Id': client_id,
        'X-Request-Timestamp': str(int(time.time())),
        'X-Client-Public-Key': pub_b64,
    })
    if method == 'GET':
        return requests.get(BASE + url, headers=h, params=body if isinstance(body, dict) else None, timeout=30)
    return requests.post(BASE + url, json=body, headers=h, timeout=30)

print()
print('=== FX Endpoint Tests ===')

# Test tools
r = signed_request('GET', '/api/banking/tools')
print(f'TOOLS: {r.status_code}', r.json().get('tools', [])[:5] if r.status_code == 200 else r.text[:200])

# Test FX rates
r = signed_request('GET', '/api/banking/fx/rates?from_currency=CNY&to_currency=USD')
print(f'FX rates CNY->USD: {r.status_code}', r.text[:300])
if r.status_code == 200:
    print(f'  Rates: {r.json()}')

r = signed_request('GET', '/api/banking/fx/rates?from_currency=USD&to_currency=CNY')
print(f'FX rates USD->CNY:', r.status_code, r.text[:200])

# Test FX convert CNY->USD
r = signed_request('POST', '/api/banking/fx/convert', {'from_currency': 'CNY', 'to_currency': 'USD', 'amount': 1000})
print(f'FX Convert CNY->USD 1000:', r.status_code, r.text[:200])

r = signed_request('POST', '/api/banking/fx/convert', {'from_currency': 'USD', 'to_currency': 'CNY', 'amount': 100})
print(f'FX Convert USD->CNY 100:', r.status_code, r.text[:200])

r = signed_request('POST', '/api/banking/fx/convert', {'from_currency': 'CNY', 'to_currency': 'EUR', 'amount': 1000})
print('FX Convert CNY->EUR 1000:', r.status_code, r.text[:200])

print()
print('=== All FX endpoint tests completed ===')

proc.terminate()