import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  getBankingSpend,
  getBankingStatus,
  getBankingAudit,
  verifyBankingAudit,
  getBankingApprovals,
  getBankingTools,
} from '../services/api';
import { LayoutDashboard, FileText, Activity, Shield, ShieldAlert, CheckCircle2 } from 'lucide-react';
import PageHeader from '../components/Common/PageHeader';
import LoadingSpinner from '../components/Common/LoadingSpinner';
import ErrorBoundary from '../components/Common/ErrorBoundary';
import TierBadge from '../components/Security/TierBadge';
import KillSwitch from '../components/Security/KillSwitch';
import ApprovalList from '../components/Security/ApprovalList';
import AuditLog from '../components/Security/AuditLog';
import { useSignedBankingApi } from '../hooks/useSignedBankingApi';
import { WeComBotWidget } from '../components/WeComBotWidget';

const ICONS = {
  'get-accounts': LayoutDashboard,
  'get-transactions': Activity,
  'get-transaction': Activity,
  'get-categories': FileText,
  'get-transactions-summary': FileText,
  'get-recipients': Shield,
  'prepare-transfer': ShieldAlert,
  'execute-transfer': ShieldAlert,
  'create-recipient': ShieldAlert,
};

export default function Security() {
  const { user } = useAuth();
  const [spend, setSpend] = useState('0');
  const [tier, setTier] = useState('green');
  const [status, setStatus] = useState('');
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Zero-Trust signing: register client public key on mount
  const { registerPublicKey, signedRequest, resetKeyPair } = useSignedBankingApi();
  useEffect(() => {
    registerPublicKey();
  }, [registerPublicKey]);

  // Signed wrappers for banking GET calls
  const signedGetSpend = useCallback(
    (config) => signedRequest(getBankingSpend, null, { ...config, url: '/api/banking/spend' }),
    [signedRequest]
  );
  const signedGetStatus = useCallback(
    (config) => signedRequest(getBankingStatus, null, { ...config, url: '/api/banking/status' }),
    [signedRequest]
  );
  const signedGetTools = useCallback(
    (config) => signedRequest(getBankingTools, null, { ...config, url: '/api/banking/tools' }),
    [signedRequest]
  );

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const [spendRes, statusRes, toolsRes] = await Promise.all([
          signedGetSpend({ signal: controller.signal }),
          signedGetStatus({ signal: controller.signal }),
          signedGetTools({ signal: controller.signal }),
        ]);
        setSpend(spendRes.data.spent_today_cny ?? '0');
        setStatus(statusRes.data.status || '');
        setTools(toolsRes.data.tools || []);
        const text = (statusRes.data.status || '').toLowerCase();
        setTier(/red/.test(text) ? 'red' : /yellow/.test(text) ? 'yellow' : 'green');
        setError(null);
      } catch (error) {
        if (error.name === 'CanceledError') return;
        console.error('Security load failed:', error);
        setError(
          error.response?.status === 401
            ? 'Security request verification failed. Please refresh and try again.'
            : 'Failed to load security data. Please try again.',
        );
      } finally {
        setLoading(false);
      }
    };
    load();
    return () => controller.abort();
  }, []);

  const retry = async () => {
    setLoading(true);
    setError(null);
    try {
      await resetKeyPair();
      await registerPublicKey();
    } catch (e) {
      console.warn("[Security] Key reset failed:", e);
    }
    const controller = new AbortController();
    try {
      const [spendRes, statusRes, toolsRes] = await Promise.all([
        signedGetSpend({ signal: controller.signal }),
        signedGetStatus({ signal: controller.signal }),
        signedGetTools({ signal: controller.signal }),
      ]);
      setSpend(spendRes.data.spent_today_cny ?? '0');
      setStatus(statusRes.data.status || '');
      setTools(toolsRes.data.tools || []);
      const text = (statusRes.data.status || '').toLowerCase();
      setTier(/red/.test(text) ? 'red' : /yellow/.test(text) ? 'yellow' : 'green');
    } catch (error) {
      if (error.name === 'CanceledError') return;
      console.error('Security load failed:', error);
      setError(
        error.response?.status === 401
          ? 'Security request verification failed. Please refresh and try again.'
          : 'Failed to load security data. Please try again.',
      );
    } finally {
      setLoading(false);
    }
  };

  const Icon = ICONS[tools[0]] || Shield;
  return (
    <ErrorBoundary>
      <div>
      <PageHeader
        eyebrow="Zero-Trust security layer"
        title="Security dashboard"
        description={`Governance, MFA, approvals and audit for ${user?.company_name || 'your accounts'}`}
        actions={
          <button
            className="btn-primary flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-[0.15em]"
            onClick={() => window.location.reload()}
          >
            <Refresh className="h-3.5 w-3.5" aria-hidden="true" /> Refresh
          </button>
        }
      />

      {error && (
        <div className="surface-card p-5 mb-5">
          <div className="flex items-center gap-3 p-3 rounded-md border border-[var(--negative-color)]/40 bg-[var(--negative-color)]/5 text-[var(--negative-color)]">
            <span className="shrink-0 h-4 w-4" aria-hidden="true">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </span>
            <span className="text-xs font-medium text-[var(--negative-color)]">{error}</span>
            <button
              onClick={retry}
              className="ml-auto btn-outline disabled:opacity-50 disabled:pointer-events-none uppercase tracking-[0.1em] text-xs px-3 py-1.5"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <KillSwitch />
          <WeComBotWidget />
        </div>
        <div>
          <div className="surface-card p-5 mb-5">
            <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Current tier</h2>
            <div className="flex items-center gap-3">
              <TierBadge tier={tier} />
              <span className="text-xs text-[var(--text-muted)]">Policy enforcement level</span>
            </div>
          </div>
          <div className="surface-card p-5">
            <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Daily spend</h2>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-6xl leading-none text-[var(--text-primary)]">¥{Number(spend || 0).toLocaleString()}</span>
              <span className="text-xs text-[var(--text-muted)]">authorised today (CNY)</span>
            </div>
          </div>
        </div>
        <div className="lg:col-span-1">
          <div className="surface-card p-5">
            <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Tool surface</h2>
            <p className="mb-3 text-[10px] text-[var(--text-muted)]">{tools.length} gated tools available via okgate</p>
            <ul className="flex flex-col gap-2">
              {tools.slice(0, 8).map((tool) => (
                <li key={tool} className="flex items-center gap-3 p-2 rounded-md border border-[var(--border-color)]/50 text-xs">
                  <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" aria-hidden="true" />
                  <span className="font-mono text-[var(--text-secondary)]">{tool.replace(/_/g, '-')}</span>
                </li>
              ))}
              {tools.length > 8 && (
                <li className="flex items-center gap-3 p-2 rounded-md border border-[var(--border-color)]/50 text-xs text-[var(--text-muted)]">
                  <span>…and {tools.length - 8} more</span>
                </li>
              )}
            </ul>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ApprovalList />
        </div>
        <div className="lg:col-span-1">
          <AuditLog />
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center min-h-[300px]">
          <LoadingSpinner size="large" />
        </div>
      )}
      </div>
    </ErrorBoundary>
  );
}

function Refresh() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 4v6h6" />
      <path d="M23 20v-6h-6" />
      <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
    </svg>
  );
}
