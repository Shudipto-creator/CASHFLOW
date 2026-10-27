import React, { useEffect, useState } from 'react';
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

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const [spendRes, statusRes, toolsRes] = await Promise.all([
          getBankingSpend({ signal: controller.signal }),
          getBankingStatus({ signal: controller.signal }),
          getBankingTools({ signal: controller.signal }),
        ]);
        setSpend(spendRes.data.spent_today_cny ?? '0');
        setStatus(statusRes.data.status || '');
        setTools(toolsRes.data.tools || []);
        const text = (statusRes.data.status || '').toLowerCase();
        setTier(/red/.test(text) ? 'red' : /yellow/.test(text) ? 'yellow' : 'green');
      } catch (error) {
        if (error.name === 'CanceledError') return;
        console.error('Security load failed:', error);
      } finally {
        setLoading(false);
      }
    };
    load();
    return () => controller.abort();
  }, []);

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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <KillSwitch />
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
