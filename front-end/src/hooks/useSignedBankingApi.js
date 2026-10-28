/**
 * React hook for signed banking API calls.
 *
 * Wraps each banking request with Ed25519 signing headers (X-Request-Signature,
 * X-Request-STID, X-Client-Id, X-Request-Timestamp, X-Client-Public-Key) so
 * the backend can verify cryptographic proof of intent before processing.
 *
 * Usage:
 *   const { registerPublicKey, signedRequest } = useSignedBankingApi();
 *   const res = await signedRequest(prepareBankingTransfer, { ...data });
 */

import { useCallback } from "react";
import {
  buildSigningHeaders,
  getClientPublicKeyB64,
  getClientKeyPair,
  computeStid,
} from "../utils/signing";

export function useSignedBankingApi() {
  /**
   * Register the client's public key with localStorage so the backend can
   * verify future signatures. Call once after login.
   */
  const registerPublicKey = useCallback(async () => {
    const pubB64 = await getClientPublicKeyB64();
    localStorage.setItem("cashflow-client-pubkey", pubB64);
    return pubB64;
  }, []);

  /**
   * Clear cached key pair so a new one is generated on next use.
   */
  const resetKeyPair = useCallback(() => {
    // The key pair is regenerated lazily on next getClientKeyPair() call
    // because getClientKeyPair checks _keyPair and regenerates if null.
    // We clear IndexedDB to force a fresh key pair.
    return new Promise((resolve, reject) => {
      const req = indexedDB.deleteDatabase("cashflow-banking");
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  }, []);

  /**
   * Wrap an axios banking call with signing headers.
   * `apiFn` is one of the exported functions from services/api.js.
   * `data` is the request body (for POST/PUT) or null (for GET).
   * `config` is optional axios config (signal, params, etc.).
   * `url` is the endpoint path (required for correct STID computation).
   */
  const signedRequest = useCallback(
    async (apiFn, data = null, config = {}) => {
      const method = (config && config.method) || (data ? "POST" : "GET");
      const url = config.url || "/api/banking/call";

      const attempt = async () => {
        const { headers, stid, clientId } = await buildSigningHeaders(
          method,
          url,
          data
        );

        const mergedConfig = {
          ...config,
          headers: {
            ...(config.headers || {}),
            ...headers,
          },
        };

        return apiFn(data, mergedConfig);
      };

      try {
        const response = await attempt();
        return { ...response, _stid: stid, _clientId: clientId };
      } catch (error) {
        throw error;
      }
    },
    []
  );

  return {
    registerPublicKey,
    signedRequest,
    resetKeyPair,
  };
}
