import subprocess
import sys
import time
import requests
import json
import base64
import hashlib
import secrets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

BASE = 'http://127.0.0.1:8000'

# Register and login
email = f'test_{int(time.time())}@example.com'
password = 'Password123'

r = requests.post(BASE + '/api/auth/register', json={
    'email': email, 'password': password,
    'company_name': 'Test Co', 'business_type': 'Retail'
})
print(f'REGISTER: {r.status_code}')

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

# Test FX rates
r = signed_request('GET', '/api/banking/fx/rates?from_currency=CNY&to_currency=USD')
print(f'FX rates CNY->USD: {r.status_code}', r.text[:200])

r = signed_request('POST', '/api/banking/fx/convert', {'from_currency': 'CNY', 'to_currency': 'USD', 'amount': 1000})
print(f'FX Convert CNY->USD 1000:', r.status_code, r.text[:200])

r = signed_request('POST', '/api/banking/fx/convert', {'from_currency': 'USD', 'to_currency': 'CNY', 'amount': 100})
print(f'FX Convert USD->CNY 100:', r.status_code, r.text[:200])

r = signed_request('POST', '/api/banking/fx/convert', {'from_currency': 'CNY', 'to_currency': 'EUR', 'amount': 1000})
print('FX Convert CNY->EUR 1000:', r.status_code, r.text[:200])

print()
print('=== All FX endpoint tests completed ===')