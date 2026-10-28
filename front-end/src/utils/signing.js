/**
 * Client-side cryptographic proof of intent for Zero-Trust banking requests.
 *
 * Uses the Web Crypto API (Ed25519) to sign every banking request before it
 * leaves the browser. The backend verifies the signature and STID before
 * processing, then re-signs for the bank/okgate upstream.
 *
 * Keys are generated once and persisted in IndexedDB.
 */

const DB_NAME = "cashflow-banking";
const DB_STORE = "keys";
const KEY_ID = "ed25519-client-signing-key";

let _keyPair = null;
let _clientId = null;

async function _openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore(DB_STORE, { keyPath: "id" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function _saveKeyPair(pair) {
  const db = await _openDb();
  const publicKey = await crypto.subtle.exportKey("spki", pair.publicKey);
  const privateKey = await crypto.subtle.exportKey("pkcs8", pair.privateKey);
  const tx = db.transaction(DB_STORE, "readwrite");
  tx.objectStore(DB_STORE).put({
    id: KEY_ID,
    publicKey: Array.from(new Uint8Array(publicKey)),
    privateKey: Array.from(new Uint8Array(privateKey)),
  });
  await new Promise((res, rej) => {
    tx.oncomplete = () => res();
    tx.onerror = () => rej(tx.error);
  });
}

async function _loadKeyPair() {
  const db = await _openDb();
  const tx = db.transaction(DB_STORE, "readonly");
  const record = await new Promise((res, rej) => {
    const r = tx.objectStore(DB_STORE).get(KEY_ID);
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
  if (!record) return null;
  const publicKey = await crypto.subtle.importKey(
    "spki",
    new Uint8Array(record.publicKey).buffer,
    { name: "Ed25519", namedCurve: "Ed25519" },
    true,
    ["verify"]
  );
  const privateKey = await crypto.subtle.importKey(
    "pkcs8",
    new Uint8Array(record.privateKey).buffer,
    { name: "Ed25519", namedCurve: "Ed25519" },
    true,
    ["sign"]
  );
  return { publicKey, privateKey };
}

export async function getClientKeyPair() {
  if (_keyPair) return _keyPair;
  const stored = await _loadKeyPair();
  if (stored) {
    _keyPair = stored;
    return _keyPair;
  }
  const pair = await crypto.subtle.generateKey(
    { name: "Ed25519" },
    true,
    ["sign", "verify"]
  );
  await _saveKeyPair(pair);
  _keyPair = pair;
  return pair;
}

export async function getClientId() {
  if (_clientId) return _clientId;
  const db = await _openDb();
  const tx = db.transaction(DB_STORE, "readonly");
  const record = await new Promise((res, rej) => {
    const r = tx.objectStore(DB_STORE).get("client-id");
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
  if (record && record.id) {
    _clientId = record.id;
    return _clientId;
  }
  _clientId = "client_" + crypto.randomUUID().replace(/-/g, "").slice(0, 16);
  const tx2 = db.transaction(DB_STORE, "readwrite");
  tx2.objectStore(DB_STORE).put({ id: "client-id", value: _clientId });
  await new Promise((res, rej) => {
    tx2.oncomplete = () => res();
    tx2.onerror = () => rej(tx2.error);
  });
  return _clientId;
}

export async function getClientPublicKeyB64() {
  const pair = await getClientKeyPair();
  const spki = await crypto.subtle.exportKey("spki", pair.publicKey);
  return btoa(String.fromCharCode(...new Uint8Array(spki)));
}

/** Canonicalize deterministically: sort keys recursively, compact separators. */
export function canonicalizeDeep(value) {
  if (value === null || value === undefined) {
    return "null";
  }
  if (typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map(canonicalizeDeep).join(",") + "]";
  }
  const obj = value;
  const sortedKeys = Object.keys(obj).sort();
  const parts = sortedKeys.map(
    (k) => JSON.stringify(k) + ":" + canonicalizeDeep(obj[k])
  );
  return "{" + parts.join(",") + "}";
}

/**
 * Compute the Semantic Transaction ID (STID):
 * SHA-256 of "METHOD|PATH|canonical_body|client_id"
 */
export async function computeStid(method, path, body, clientId) {
  const canonical = canonicalizeDeep(body);
  const payload = `${method.toUpperCase()}|${path}|${canonical}|${clientId}`;
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(payload)
  );
  const hashArray = Array.from(new Uint8Array(buf));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Sign a canonical payload with the client Ed25519 key.
 * Returns Base64-encoded signature.
 */
export async function signPayload(body) {
  const pair = await getClientKeyPair();
  const canonical = canonicalizeDeep(body);
  const sig = await crypto.subtle.sign(
    "Ed25519",
    pair.privateKey,
    new TextEncoder().encode(canonical)
  );
  return btoa(String.fromCharCode(...new Uint8Array(sig)));
}

/**
 * Build the signing headers for a banking API request.
 * Returns { headers, stid, clientId } to attach to the axios config.
 */
export async function buildSigningHeaders(method, path, body) {
  const clientId = await getClientId();
  const stid = await computeStid(method, path, body, clientId);
  const signature = await signPayload(body);
  const timestamp = String(Math.floor(Date.now() / 1000));
  const pubKey = await getClientPublicKeyB64();
  const headers = {
    "X-Request-Signature": signature,
    "X-Request-STID": stid,
    "X-Client-Id": clientId,
    "X-Request-Timestamp": timestamp,
    "X-Client-Public-Key": pubKey,
  };
  console.debug("[Signing] method=%s path=%s body=%s stid=%s timestamp=%s", method, path, JSON.stringify(body), stid, timestamp);
  return { headers, stid, clientId };
}
