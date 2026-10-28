import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  getBankingTools,
  bankingCall,
  prepareBankingTransfer,
  executeBankingTransfer,
  approveBankingTransfer,
  startMfaChallenge,
  getMfaCode,
  verifyMfaCode,
  killBanking,
  resumeBanking,
  getBankingStatus,
  getBankingSpend,
} from '../services/api';
import PageHeader from '../components/Common/PageHeader';
import LoadingSpinner from '../components/Common/LoadingSpinner';
import ErrorBoundary from '../components/Common/ErrorBoundary';
import TierBadge from '../components/Security/TierBadge';
import MfaChallenge from '../components/Security/MfaChallenge';
import { useSignedBankingApi } from '../hooks/useSignedBankingApi';
import { Send, Wallet, CreditCard, AlertCircle, CheckCircle2, ShieldAlert } from 'lucide-react';

const DEBTOR_ACCOUNT = 'acc_cmb_001';
const DEFAULT_CREDITOR = {
  name: '李娜',
  accountIdentifier: {
    type: 'accountNumber',
    accountNumber: '6225 8888 0000 1234',
    country: 'CN',
  },
};

function formatMoney(value) {
  return `¥${Number(value || 0).toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
}

export default function Banking() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Transfer form state
  const [amount, setAmount] = useState('');
  const [creditorName, setCreditorName] = useState(DEFAULT_CREDITOR.name);
  const [creditorAccount, setCreditorAccount] = useState(DEFAULT_CREDITOR.accountIdentifier.accountNumber);
  const [creditorCountry, setCreditorCountry] = useState(DEFAULT_CREDITOR.accountIdentifier.country);

  // Two-phase transfer outcome state
  const [outcome, setOutcome] = useState(null);
  const [stage, setStage] = useState('idle'); // idle | prepared | awaiting-confirmation | awaiting-mfa | awaiting-approval | settled | error
  const [intentId, setIntentId] = useState(null);
  const [approvalId, setApprovalId] = useState(null);
  const [mfaNeeded, setMfaNeeded] = useState(false);
  const [mfaCode, setMfaCode] = useState('');
  const [mfaVerified, setMfaVerified] = useState(false);
  const [mfaChallengeId, setMfaChallengeId] = useState(null);
  const [mfaDeliveredCode, setMfaDeliveredCode] = useState(null);
  const [message, setMessage] = useState('');
  const [submitLoading, setSubmitLoading] = useState(false);
  const [error, setError] = useState(null);

  // Zero-Trust signing: register client public key on mount
  const { registerPublicKey, signedRequest } = useSignedBankingApi();
  useEffect(() => {
    registerPublicKey();
  }, [registerPublicKey]);

  // Signed wrappers for banking API calls
  const signedBankingCall = useCallback(
    (data, config) => signedRequest(bankingCall, data, { ...config, url: '/api/banking/call' }),
    [signedRequest]
  );
  const signedPrepareTransfer = useCallback(
    (data, config) => signedRequest(prepareBankingTransfer, data, { ...config, url: '/api/banking/transfer/prepare' }),
    [signedRequest]
  );
  const signedExecuteTransfer = useCallback(
    (data, config) => signedRequest(executeBankingTransfer, data, { ...config, url: '/api/banking/transfer/execute' }),
    [signedRequest]
  );
  const signedApproveTransfer = useCallback(
    (intentId, data, config) =>
      signedRequest(approveBankingTransfer, data, {
        ...config,
        url: `/api/banking/transfer/execute/${encodeURIComponent(intentId)}/approve`,
      }),
    [signedRequest]
  );
  const signedKill = useCallback(
    (data, config) => signedRequest(killBanking, data, { ...config, url: '/api/banking/kill' }),
    [signedRequest]
  );
  const signedResume = useCallback(
    (config) => signedRequest(resumeBanking, null, { ...config, url: '/api/banking/resume' }),
    [signedRequest]
  );

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      try {
        const [accRes, txRes] = await Promise.all([
          signedBankingCall({ tool: 'get-accounts', args: {} }, { signal: controller.signal }),
          signedBankingCall({ tool: 'get-transactions', args: { count: 10 } }, { signal: controller.signal }),
        ]);
        setAccounts(((accRes.data.value || {}).items || []));
        setTransactions(((txRes.data.value || {}).items || []));
      } catch (error) {
        if (error.name === 'CanceledError') return;
        setError(error.response?.data?.detail || 'Failed to load accounts');
      } finally {
        setLoading(false);
      }
    };
    load();
    return () => controller.abort();
  }, []);

  const handlePrepare = async () => {
    setSubmitLoading(true);
    setError(null);
    setOutcome(null);
    setStage('idle');
    setMfaNeeded(false);
    setMfaVerified(false);
    setMfaChallengeId(null);
    setMfaDeliveredCode(null);
    setMfaCode('');
    const amt = Number(amount);
    if (!amt || amt <= 0) {
      setError('Enter a valid amount');
      setSubmitLoading(false);
      return;
    }
    try {
      const res = await signedPrepareTransfer({
        debtor_account_id: DEBTOR_ACCOUNT,
        creditor: {
          name: creditorName,
          accountIdentifier: { type: 'accountNumber', accountNumber: creditorAccount, country: creditorCountry },
        },
        amount: amt,
        currency: 'CNY',
        rail: 'swift',
      });
      const data = res.data;
      setOutcome(data);
      setMessage(data.message || '');
      if (data.needs_mfa) {
        setStage('awaiting-mfa');
        setMfaNeeded(true);
        // Start the challenge and surface the simulated SMS code.
        const chalRes = await signedRequest(startMfaChallenge, {
          subject: 'account-holder',
          purpose: 'strong verification for a Red-tier transfer',
        }, { url: '/api/banking/mfa/challenge' });
        const cid = chalRes.data.challenge_id;
        setMfaChallengeId(cid);
        const codeRes = await signedRequest(getMfaCode, cid, { url: `/api/banking/mfa/code/${cid}` });
        setMfaDeliveredCode(codeRes.data.code);
      } else if (data.needs_confirmation) {
        setStage('awaiting-confirmation');
      } else if (data.ok) {
        setStage('prepared');
        setIntentId(data.intent_id);
      } else {
        setStage('error');
        setError(data.message || 'Transfer was refused');
      }
    } catch (err) {
      setStage('error');
      setError(err.response?.data?.detail || 'Prepare failed');
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleConfirm = async () => {
    setSubmitLoading(true);
    setError(null);
    const amt = Number(amount);
    try {
      const res = await signedPrepareTransfer({
        debtor_account_id: DEBTOR_ACCOUNT,
        creditor: {
          name: creditorName,
          accountIdentifier: { type: 'accountNumber', accountNumber: creditorAccount, country: creditorCountry },
        },
        amount: amt,
        currency: 'CNY',
        rail: 'swift',
        confirmed: true,
      });
      const data = res.data;
      setOutcome(data);
      if (data.needs_mfa) {
        setStage('awaiting-mfa');
        setMfaNeeded(true);
        const chalRes = await startMfaChallenge({
          subject: 'account-holder',
          purpose: 'strong verification for a Red-tier transfer',
        });
        const cid = chalRes.data.challenge_id;
        setMfaChallengeId(cid);
        const codeRes = await getMfaCode(cid);
        setMfaDeliveredCode(codeRes.data.code);
      } else if (data.ok) {
        setStage('prepared');
        setIntentId(data.intent_id);
        setMessage(data.message || 'Transfer prepared');
      } else {
        setStage('error');
        setError(data.message || 'Confirm failed');
      }
    } catch (err) {
      setStage('error');
      setError(err.response?.data?.detail || 'Confirm failed');
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleMfaVerify = async () => {
    if (!mfaChallengeId || !mfaCode) return;
    setSubmitLoading(true);
    setError(null);
    try {
      const res = await signedRequest(verifyMfaCode, { challenge_id: mfaChallengeId, code: mfaCode }, { url: '/api/banking/mfa/verify' });
      if (!res.data.valid) {
        setError('Invalid code');
        setSubmitLoading(false);
        return;
      }
      setMfaVerified(true);
      // Re-prepare with the verified code.
      const amt = Number(amount);
      const prepRes = await signedPrepareTransfer({
        debtor_account_id: DEBTOR_ACCOUNT,
        creditor: {
          name: creditorName,
          accountIdentifier: { type: 'accountNumber', accountNumber: creditorAccount, country: creditorCountry },
        },
        amount: amt,
        currency: 'CNY',
        rail: 'swift',
        mfa_challenge_id: mfaChallengeId,
        mfa_code: mfaCode,
        confirmed: true,
      });
      const data = prepRes.data;
      setOutcome(data);
      if (data.ok) {
        setStage('prepared');
        setIntentId(data.intent_id);
        setMessage('Transfer prepared and verified');
      } else if (data.needs_confirmation) {
        setStage('awaiting-confirmation');
      } else {
        setStage('error');
        setError(data.message || 'MFA release failed');
      }
    } catch (err) {
      setStage('error');
      setError(err.response?.data?.detail || 'MFA verify failed');
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!intentId) return;
    setSubmitLoading(true);
    setError(null);
    try {
      const res = await signedExecuteTransfer({ intent_id: intentId });
      const data = res.data;
      setOutcome(data);
      if (data.needs_approval) {
        setStage('awaiting-approval');
        setApprovalId(data.approval_id);
        setMessage('Awaiting human approval — okgate is holding the execute-transfer');
      } else if (data.ok) {
        setStage('settled');
        setMessage('Transfer settled');
      } else {
        setStage('error');
        setError(data.message || 'Execute failed');
      }
    } catch (err) {
      setStage('error');
      setError(err.response?.data?.detail || 'Execute failed');
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleApproveAndExecute = async () => {
    if (!intentId || !approvalId) return;
    setSubmitLoading(true);
    setError(null);
    try {
      await signedApproveTransfer(intentId, { approval_id: approvalId });
      const res = await signedExecuteTransfer({ intent_id: intentId });
      const data = res.data;
      setOutcome(data);
      if (data.ok) {
        setStage('settled');
        setMessage('Approved and settled');
      } else {
        setStage('error');
        setError(data.message || 'Post-approval execute failed');
      }
    } catch (err) {
      setStage('error');
      setError(err.response?.data?.detail || 'Approve/execute failed');
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleKill = async () => {
    try {
      await signedKill({ reason: 'operator pressed the kill switch' });
      setMessage('Kill switch engaged');
    } catch (err) {
      setError('Kill failed');
    }
  };

  const handleResume = async () => {
    try {
      await signedResume();
      setMessage('Service resumed');
    } catch (err) {
      setError('Resume failed');
    }
  };

  const canTransfer = stage === 'idle' || stage === 'error';
  const tierColor = stage === 'awaiting-mfa' ? 'red' : stage === 'awaiting-confirmation' ? 'yellow' : 'green';

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div>
      <PageHeader
        eyebrow="Zero-Trust banking"
        title="Transfer funds"
        description={`Two-phase transfers for ${user?.company_name || 'your account'}`}
        actions={
          <>
            <button
              onClick={handleKill}
              className="btn-outline disabled:opacity-50 disabled:pointer-events-none uppercase tracking-[0.1em] text-xs px-3 py-1.5"
            >
              <ShieldAlert className="h-3.5 w-3.5 mr-1.5" aria-hidden="true" /> Kill
            </button>
            <button
              onClick={handleResume}
              className="btn-outline disabled:opacity-50 disabled:pointer-events-none uppercase tracking-[0.1em] text-xs px-3 py-1.5"
            >
              <ShieldAlert className="h-3.5 w-3.5 mr-1.5" aria-hidden="true" /> Resume
            </button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
        <div className="lg:col-span-3">
          {/* Transfer form */}
          <div className="surface-card p-5 mb-6">
            <h2 className="mb-4 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">New transfer</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="col-span-full sm:col-span-2">
                <label className="block mb-1.5 text-[10px] uppercase tracking-[0.15em] text-[var(--text-muted)]">Creditor name</label>
                <input
                  value={creditorName}
                  onChange={(e) => setCreditorName(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none text-xs"
                />
              </div>
              <div>
                <label className="block mb-1.5 text-[10px] uppercase tracking-[0.15em] text-[var(--text-muted)]">Account number</label>
                <input
                  value={creditorAccount}
                  onChange={(e) => setCreditorAccount(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none text-xs font-mono"
                />
              </div>
              <div>
                <label className="block mb-1.5 text-[10px] uppercase tracking-[0.15em] text-[var(--text-muted)]">Country</label>
                <input
                  value={creditorCountry}
                  onChange={(e) => setCreditorCountry(e.target.value)}
                  className="w-full px-3 py-2 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none text-xs"
                />
              </div>
              <div className="col-span-full sm:col-span-2">
                <label className="block mb-1.5 text-[10px] uppercase tracking-[0.15em] text-[var(--text-muted)]">Amount (CNY)</label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-[var(--text-muted)] text-xs">¥</span>
                  <input
                    type="number"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="w-full pl-8 pr-3 py-2 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none text-xs"
                  />
                </div>
              </div>
            </div>

            {stage === 'awaiting-mfa' && (
              <div className="mt-5 p-4 rounded-md border border-[#d97706]/40 bg-[#d97706]/5 text-[var(--text-secondary)] text-xs">
                <ShieldAlert className="mr-2 h-4 w-4" aria-hidden="true" />
                Red tier — strong verification required. Enter the SMS code below.
              </div>
            )}
            {stage === 'awaiting-confirmation' && (
              <div className="mt-5 p-4 rounded-md border border-[#d97706]/40 bg-[#d97706]/5 text-[var(--text-secondary)] text-xs">
                <ShieldAlert className="mr-2 h-4 w-4" aria-hidden="true" />
                Yellow tier — confirm the transfer details before execution.
              </div>
            )}

            <div className="mt-6 flex flex-col sm:flex-row sm:items-end gap-3">
              <button
                onClick={handlePrepare}
                disabled={submitLoading || !canTransfer}
                className="btn-primary disabled:opacity-50 disabled:pointer-events-none flex-1 sm:w-auto px-6 py-2.5 uppercase tracking-[0.1em] text-xs"
              >
                {submitLoading ? 'Preparing…' : stage === 'awaiting-mfa' ? 'Start MFA' : 'Prepare transfer'}
              </button>
              {stage === 'awaiting-confirmation' && (
                <button
                  onClick={handleConfirm}
                  disabled={submitLoading}
                  className="btn-primary disabled:opacity-50 disabled:pointer-events-none flex-1 sm:w-auto px-6 py-2.5 uppercase tracking-[0.1em] text-xs"
                >
                  Confirm &amp; prepare
                </button>
              )}
              {stage === 'awaiting-mfa' && (
                <div className="flex-1 sm:w-auto flex flex-col gap-2">
                  <input
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="6-digit code"
                    className="px-3 py-2 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none text-center tracking-widest text-xs"
                    disabled={submitLoading || !mfaDeliveredCode}
                    maxLength="6"
                  />
                  {mfaDeliveredCode && (
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="text-[var(--text-muted)]">Simulated SMS:</span>
                      <span className="font-mono text-xs text-[var(--text-primary)]">{mfaDeliveredCode}</span>
                    </div>
                  )}
                  <button
                    onClick={handleMfaVerify}
                    disabled={submitLoading || !mfaDeliveredCode || mfaCode.length !== 6}
                    className="btn-primary disabled:opacity-50 disabled:pointer-events-none w-full py-2.5 uppercase tracking-[0.1em] text-xs"
                  >
                    Verify code
                  </button>
                </div>
              )}
              {stage === 'prepared' && (
                <button
                  onClick={handleExecute}
                  disabled={submitLoading}
                  className="btn-primary disabled:opacity-50 disabled:pointer-events-none flex-1 sm:w-auto px-6 py-2.5 uppercase tracking-[0.1em] text-xs"
                >
                  Execute (awaits approval)
                </button>
              )}
              {stage === 'awaiting-approval' && (
                <button
                  onClick={handleApproveAndExecute}
                  disabled={submitLoading}
                  className="btn-primary disabled:opacity-50 disabled:pointer-events-none flex-1 sm:w-auto px-6 py-2.5 uppercase tracking-[0.1em] text-xs"
                >
                  Approve &amp; execute
                </button>
              )}
            </div>

            {message && (
              <p className={`mt-3 text-xs ${stage === 'settled' || stage === 'prepared' ? 'text-[var(--positive-color)]' : 'text-[var(--text-secondary)]'}`}>
                {message}
              </p>
            )}
            {error && (
              <p className="mt-3 text-xs text-[var(--negative-color)] flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" /> {error}
              </p>
            )}
          </div>

          {/* Outcome summary card */}
          {outcome && (
            <div className="surface-card p-5">
              <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Outcome</h2>
              <div className="flex items-center gap-3 mb-3">
                <TierBadge tier={tierColor} />
                <span className="text-xs font-mono text-[var(--text-muted)]">{outcome.code ?? 'ok'}</span>
              </div>
              <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2 text-xs">
                <dt className="text-[var(--text-muted)] uppercase tracking-[0.1em]">Stage</dt>
                <dd className="text-[var(--text-primary)]">{stage}</dd>
                <dt className="text-[var(--text-muted)] uppercase tracking-[0.1em]">Intent id</dt>
                <dd className="text-[var(--text-secondary)] font-mono">{intentId ?? outcome.intent_id ?? '-'}</dd>
                {outcome.approval_id && (
                  <>
                    <dt className="text-[var(--text-muted)] uppercase tracking-[0.1em]">Approval id</dt>
                    <dd className="text-[var(--text-secondary)] font-mono">{outcome.approval_id}</dd>
                  </>
                )}
                {outcome.approval_command && (
                  <>
                    <dt className="text-[var(--text-muted)] uppercase tracking-[0.1em]">Approval command</dt>
                    <dd className="text-[var(--text-secondary)] font-mono text-[10px]">{outcome.approval_command}</dd>
                  </>
                )}
              </dl>
              {outcome.message && (
                <p className="mt-3 text-[10px] text-[var(--text-muted)]">{outcome.message}</p>
              )}
            </div>
          )}
        </div>

        <div className="lg:col-span-1 flex flex-col gap-6">
          <div className="surface-card p-5 shrink-0">
            <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Accounts</h2>
            <ul>
              {accounts.map((acc) => (
                <li key={acc.account_id || acc.id || acc.name} className="flex items-center justify-between gap-3 py-2 border-b border-[var(--border-color)]/50 last:border-0 text-xs">
                  <span className="font-mono text-[var(--text-secondary)] truncate">{acc.name || acc.account_id || 'Account'}</span>
                  <span className="font-mono text-[var(--text-primary)]">{acc.available_balance ? formatMoney(acc.available_balance) : '—'}</span>
                </li>
              ))}
              {accounts.length === 0 && <p className="text-[10px] text-[var(--text-muted)]">No accounts</p>}
            </ul>
          </div>
          <div className="surface-card p-5 shrink-0">
            <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">Recent transactions</h2>
            <ul>
              {transactions.slice(0, 5).map((tx) => (
                <li key={tx.transaction_id || tx.id} className="py-2 border-b border-[var(--border-color)]/50 last:border-0 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-secondary)]">{tx.description || tx.name || 'Transaction'}</span>
                    <span className="font-mono text-[var(--text-primary)]">{tx.amount ? formatMoney(tx.amount) : '—'}</span>
                  </div>
                  <span className="block text-[9px] text-[var(--text-muted)]">{tx.date || tx.posted_date || ''}</span>
                </li>
              ))}
              {transactions.length === 0 && <p className="text-[10px] text-[var(--text-muted)]">No transactions</p>}
            </ul>
          </div>
        </div>
      </div>
    </div>
    </ErrorBoundary>
  );
}
