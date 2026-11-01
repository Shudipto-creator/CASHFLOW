import React, { useEffect, useState, useCallback } from 'react';
import { FileText, CheckCircle2, AlertTriangle } from 'lucide-react';
import { getBankingAudit, verifyBankingAudit } from '../../services/api';
import { useSignedBankingApi } from '../../hooks/useSignedBankingApi';

export default function AuditLog() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifying, setVerifying] = useState(false);

  const { signedRequest } = useSignedBankingApi();

  const signedGetAudit = useCallback(
    (config) => signedRequest(getBankingAudit, null, { ...config, url: '/api/banking/audit' }),
    [signedRequest]
  );
  const signedVerifyAudit = useCallback(
    (config) => signedRequest(verifyBankingAudit, null, { ...config, url: '/api/banking/audit/verify' }),
    [signedRequest]
  );

  const load = async (signal) => {
    setLoading(true);
    try {
      const res = await signedGetAudit({ signal });
      setEntries(res.data.audit || []);
    } catch (error) {
      if (error.name === 'CanceledError') return;
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, []);

  const handleVerify = async () => {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await signedVerifyAudit();
      setVerifyResult(res.data.result || '');
    } catch (error) {
      setVerifyResult(error.response?.data?.detail || 'Verification failed');
    } finally {
      setVerifying(false);
    }
  };

  const intact = verifyResult && /intact/i.test(verifyResult);
  const broken = verifyResult && /broken|tamper/i.test(verifyResult);

  if (loading) {
    return (
      <div className="surface-card p-5">
        <div className="flex h-24 items-center justify-center text-[11px] text-[var(--text-muted)]">Loading audit log…</div>
      </div>
    );
  }

  return (
    <div className="surface-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Audit log</h2>
        <button
          onClick={handleVerify}
          disabled={verifying}
          className="btn-outline disabled:opacity-50 disabled:pointer-events-none uppercase tracking-[0.1em] text-xs px-3 py-1.5 flex items-center gap-1.5"
        >
          {verifying ? 'Verifying…' : 'Verify chain'}
        </button>
      </div>
      {verifyResult && (
        <div className={`mb-4 p-3 rounded-md border text-xs ${
          intact
            ? 'border-[var(--positive-color)]/40 bg-[var(--positive-color)]/10 text-[var(--positive-color)]'
            : broken
              ? 'border-[var(--negative-color)]/40 bg-[var(--negative-color)]/10 text-[var(--negative-color)]'
              : 'border-[var(--border-color)] bg-[var(--surface-raised)] text-[var(--text-secondary)]'
        }`}>
          <span className={`mr-2 ${intact ? 'text-[var(--positive-color)]' : broken ? 'text-[var(--negative-color)]' : 'text-[var(--text-muted)]'}`} aria-hidden="true">
            {intact ? <CheckCircle2 className="h-3 w-3" /> : broken ? <AlertTriangle className="h-3 w-3" /> : <FileText className="h-3 w-3" />}
          </span>
          {verifyResult.split('\n').pop() || verifyResult}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[10px] border-collapse">
          <thead>
            <tr className="border-b border-[var(--border-color)] text-[var(--text-muted)] uppercase tracking-[0.1em]">
              <th className="pb-2 text-left w-16">Seq</th>
              <th className="pb-2 text-left">Tool</th>
              <th className="pb-2 text-left w-40">Class</th>
              <th className="pb-2 text-left w-32">Outcome</th>
              <th className="pb-2 text-left w-32">Code</th>
              <th className="pb-2 text-right">USD</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, i) => (
              <tr key={i} className="border-b border-[var(--border-color)]/50 hover:bg-[var(--surface-raised)]/50">
                <td className="py-2 text-[var(--text-muted)] font-mono">{entry.seq ?? i + 1}</td>
                <td className="py-2 text-[var(--text-secondary)] font-mono">{entry.tool ?? '-'}</td>
                <td className="py-2 text-[var(--text-secondary)]">{entry.class ?? '-'}</td>
                <td className="py-2 text-[var(--text-secondary)]">{entry.outcome ?? '-'}</td>
                <td className="py-2 text-[var(--text-secondary)] font-mono">{((entry.error || {}).code ?? '-')}</td>
                <td className="py-2 text-right text-[var(--text-secondary)]">
                  {typeof entry.usd === 'number' ? entry.usd.toFixed(2) : '-'}
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan={6} className="py-4 text-center text-[var(--text-muted)] text-[11px]">
                  No audit entries yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[10px] uppercase tracking-[0.1em] text-[var(--text-muted)]">
        {entries.length} gated call(s) recorded
      </p>
    </div>
  );
}
