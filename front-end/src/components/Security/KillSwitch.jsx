import React, { useEffect, useState } from 'react';
import { ShieldOff, ShieldCheck, AlertTriangle } from 'lucide-react';
import { killBanking, resumeBanking, getBankingStatus } from '../../services/api';

export default function KillSwitch() {
  const [killed, setKilled] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');

  const loadStatus = async (signal) => {
    try {
      const res = await getBankingStatus({ signal });
      setStatus(res.data.status || '');
      setKilled(/kill/i.test(res.data.status || ''));
    } catch (error) {
      if (error.name === 'CanceledError') return;
      setKilled(null);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    loadStatus(controller.signal);
    return () => controller.abort();
  }, []);

  const handleKill = async () => {
    setLoading(true);
    try {
      await killBanking({ reason: 'operator pressed the kill switch' });
      setKilled(true);
      setStatus('kill switch engaged');
    } catch (error) {
      console.error('Kill failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleResume = async () => {
    setLoading(true);
    try {
      await resumeBanking();
      setKilled(false);
      setStatus('service resumed');
    } catch (error) {
      console.error('Resume failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const Icon = killed ? ShieldOff : ShieldCheck;
  return (
    <div className="surface-card p-5">
      <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Kill switch</h2>
      <div className="flex flex-col gap-3">
        <div className={`flex items-center gap-3 p-3 rounded-md border ${
          killed
            ? 'border-[var(--negative-color)]/40 bg-[var(--negative-color)]/5 text-[var(--negative-color)]'
            : 'border-[var(--border-color)] text-[var(--text-secondary)]'
        }`}>
          <AlertTriangle className={`h-5 w-5 shrink-0 ${killed ? 'text-[var(--negative-color)] animate-pulse' : 'text-[var(--text-muted)]'}`} aria-hidden="true" />
          <div>
            <p className="text-xs font-medium text-[var(--text-primary)] uppercase tracking-[0.1em]">
              {killed ? 'ENGAGED — all calls halted' : 'ARMED — calls allowed'}
            </p>
            {status && <p className="text-[10px] text-[var(--text-muted)]">{status}</p>}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleKill}
            disabled={loading || killed}
            className="flex-1 btn-outline disabled:opacity-50 disabled:pointer-events-none uppercase tracking-[0.1em] text-xs"
          >
            <ShieldOff className="h-3 w-3 mr-1.5" aria-hidden="true" />
            Kill
          </button>
          <button
            onClick={handleResume}
            disabled={loading || !killed}
            className="flex-1 btn-primary disabled:opacity-50 disabled:pointer-events-none uppercase tracking-[0.1em] text-xs"
          >
            <ShieldCheck className="h-3 w-3 mr-1.5" aria-hidden="true" />
            Resume
          </button>
        </div>
        {loading && <LoadingSpinner size="small" />}
      </div>
    </div>
  );
}

function LoadingSpinner({ size = 'small' }) {
  const sizeClasses = { small: 'w-4 h-4 border-2', medium: 'w-6 h-6 border-[3px]' };
  return (
    <div className="flex h-6 items-center">
      <div className={`${sizeClasses[size]} animate-spin border-[var(--border-color)] border-t-[var(--primary-accent)] rounded-full`} />
    </div>
  );
}
