import React, { useEffect, useState } from 'react';
import { Phone, Copy, CheckCircle2, AlertCircle } from 'lucide-react';
import { startMfaChallenge, getMfaCode, verifyMfaCode } from '../../services/api';

export default function MfaChallenge({ onVerified, onCodeDelivered }) {
  const [challengeId, setChallengeId] = useState(null);
  const [code, setCode] = useState('');
  const [deliveredCode, setDeliveredCode] = useState(null);
  const [delivered, setDelivered] = useState(false);
  const [verified, setVerified] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const startChallenge = async (signal) => {
    setLoading(true);
    setError(null);
    try {
      const res = await startMfaChallenge({
        subject: 'account-holder',
        purpose: 'strong verification for a Red-tier transfer',
      }, { signal });
      const id = res.data.challenge_id;
      setChallengeId(id);
      // Surface the simulated SMS code so the demo UI can present it.
      const codeRes = await getMfaCode(id, { signal });
      setDeliveredCode(codeRes.data.code);
      setDelivered(true);
      if (onCodeDelivered) onCodeDelivered(codeRes.data.code);
    } catch (err) {
      if (err.name === 'CanceledError') return;
      setError(err.response?.data?.detail || 'Failed to start MFA challenge');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (!challengeId || !code) return;
    setLoading(true);
    setError(null);
    try {
      const res = await verifyMfaCode({ challenge_id: challengeId, code });
      if (res.data.valid) {
        setVerified(true);
        if (onVerified) onVerified(challengeId);
      } else {
        setError('Invalid code');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!challengeId) {
      const controller = new AbortController();
      startChallenge(controller.signal);
      return () => controller.abort();
    }
    return undefined;
  }, [challengeId]);

  return (
    <div className="surface-card p-5">
      <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Strong verification (MFA)</h2>
      {verified ? (
        <div className="flex items-center gap-3 p-3 rounded-md border border-[var(--positive-color)]/40 bg-[var(--positive-color)]/10 text-[var(--positive-color)]">
          <CheckCircle2 className="h-5 w-5 shrink-0" aria-hidden="true" />
          <div>
            <p className="text-xs font-medium text-[var(--text-primary)] uppercase tracking-[0.1em]">Verified</p>
            <p className="text-[10px] text-[var(--text-muted)]">Strong verification passed — the call may proceed.</p>
          </div>
        </div>
      ) : (
        <>
          <div className="mb-4 p-3 rounded-md border border-[var(--border-color)] bg-[var(--surface-raised)] text-xs">
            <p className="mb-1 text-[var(--text-secondary)] uppercase tracking-[0.1em]">SMS code (simulated)</p>
            {deliveredCode && (
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-[var(--text-primary)]">{deliveredCode}</span>
                <button
                  onClick={() => navigator.clipboard.writeText(deliveredCode || '')}
                  className="ml-auto text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  title="Copy code"
                >
                  <Copy className="h-3 w-3" aria-hidden="true" />
                </button>
              </div>
            )}
            <p className="mt-1 text-[10px] text-[var(--text-muted)]">
              Enter the code below (in production this arrives via SMS/push).
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <input
              type="text"
              maxLength="6"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              placeholder="6-digit code"
              className="px-3 py-2 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none text-center tracking-widest"
              disabled={loading || deliveredCode == null}
              autoComplete="off"
            />
            {error && (
              <p className="text-[10px] text-[var(--negative-color)] flex items-center gap-1.5">
                <AlertCircle className="h-3 w-3" aria-hidden="true" /> {error}
              </p>
            )}
            <button
              onClick={handleVerify}
              disabled={loading || !deliveredCode || !code || code.length !== 6}
              className="btn-primary disabled:opacity-50 disabled:pointer-events-none uppercase tracking-[0.1em] text-xs"
            >
              {loading ? 'Verifying…' : 'Verify code'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
