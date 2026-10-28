import React, { useEffect, useState, useCallback } from 'react';
import { List, CheckCircle2, AlertCircle } from 'lucide-react';
import { getBankingApprovals, approveBankingTransfer } from '../../services/api';
import { useSignedBankingApi } from '../../hooks/useSignedBankingApi';

export default function ApprovalList({ onApprovalSettled }) {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(new Set());

  const { signedRequest } = useSignedBankingApi();

  const signedGetApprovals = useCallback(
    (config) => signedRequest(getBankingApprovals, null, { ...config, url: '/api/banking/approvals' }),
    [signedRequest]
  );
  const signedApproveTransfer = useCallback(
    (approvalId, data, config) =>
      signedRequest(approveBankingTransfer, data, {
        ...config,
        url: `/api/banking/transfer/execute/${encodeURIComponent(approvalId)}/approve`,
        intentId: approvalId,
      }),
    [signedRequest]
  );

  const load = async (signal) => {
    setLoading(true);
    try {
      const res = await signedGetApprovals({ signal });
      const text = res.data.approvals || '';
      setApprovals(parseApprovals(text));
    } catch (error) {
      if (error.name === 'CanceledError') return;
      setApprovals([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, []);

  function parseApprovals(text) {
    const ids = [...text.matchAll(/apr_[0-9a-fA-F]+/g)].map((m) => m[0]);
    return ids.map((id) => ({ id }));
  }

  const handleApprove = async (approvalId) => {
    setApproving((prev) => new Set([...prev, approvalId]));
    try {
      await signedApproveTransfer(approvalId, { approval_id: approvalId });
      if (onApprovalSettled) onApprovalSettled(approvalId);
      await load();
    } catch (error) {
      console.error('Approve failed:', error);
    } finally {
      setApproving((prev) => {
        const next = new Set(prev);
        next.delete(approvalId);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="surface-card p-5">
        <div className="flex h-24 items-center justify-center text-[11px] text-[var(--text-muted)]">Loading approvals…</div>
      </div>
    );
  }

  if (approvals.length === 0) {
    return (
      <div className="surface-card p-5">
        <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Pending approvals</h2>
        <div className="flex h-24 items-center justify-center rounded-md border border-dashed border-[var(--border-color)] px-6 text-center text-[11px] text-[var(--text-muted)]">
          No pending approvals
        </div>
      </div>
    );
  }

  return (
    <div className="surface-card p-5">
      <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Pending approvals</h2>
      <ul className="flex flex-col gap-2">
        {approvals.map(({ id }) => (
          <li key={id} className="flex items-center justify-between gap-3 p-3 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)]">
            <div className="flex items-center gap-3">
              <List className="h-4 w-4 shrink-0 text-[var(--text-muted)]" aria-hidden="true" />
              <span className="text-xs font-mono text-[var(--text-secondary)]">{id}</span>
            </div>
            <button
              onClick={() => handleApprove(id)}
              disabled={approving.has(id)}
              className="btn-outline disabled:opacity-50 disabled:pointer-events-none uppercase tracking-[0.1em] text-xs px-3 py-1.5"
            >
              {approving.has(id) ? 'Approving…' : 'Approve'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
