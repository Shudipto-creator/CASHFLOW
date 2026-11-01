import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useSignedBankingApi } from '../hooks/useSignedBankingApi';

export function WeComBotWidget() {
  const { user } = useAuth();
  const { signedRequest } = useSignedBankingApi();
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [response, setResponse] = useState('');
  const [error, setError] = useState('');

  const handleSend = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;

    setSending(true);
    setError('');
    setResponse('');

    try {
      // Parse message: "¥600 to John" or "转账 ¥600 给 小明"
      const msg = message.trim();
      let amountStr, creditorName;

      // Try English format: "¥600 to John"
      const englishMatch = message.match(/¥([\d,.]+)\s+to\s+(.+)/i);
      if (englishMatch) {
        amountStr = englishMatch[1].replace(/,/g, '');
        creditorName = englishMatch[2].trim();
      } else {
        // Try Chinese format: "转账 ¥600 给 小明"
        const chineseMatch = message.match(/¥([\d,.]+)\s+给\s+(.+)/i);
        if (chineseMatch) {
          amountStr = chineseMatch[1].replace(/,/g, '');
          creditorName = chineseMatch[2].trim();
        } else {
          setError('Invalid format. Use: "transfer ¥600 to John" or "转账 ¥600 给 小明"');
          return;
        }
      }

      const amount = parseFloat(amountStr);
      if (isNaN(amount) || amount <= 0) {
        setError('Invalid amount. Please enter a valid number.');
        return;
      }

      setSending(true);
      setError('');

      try {
        const result = await signedRequest(bankingCall, {
          debtor_account_id: 'acc_cmb_001',
          creditor: {
            name: creditorName,
            accountIdentifier: {
              type: 'accountNumber',
              accountNumber: '1234567890',
              country: 'CN',
            },
          },
          amount,
          currency: 'CNY',
          rail: 'swift',
          confirmed: true,
        }, {
          url: '/api/banking/transfer/prepare',
        });

        if (response.ok) {
          setResponse(`✅ Transfer prepared!\nIntent ID: ${response.data.intent_id || 'N/A'}\nMessage: ${response.data.message || 'Transfer prepared successfully'}`);
        } else {
          setResponse(`❌ Transfer refused: ${response.data.message || 'Unknown error'}`);
        }
      } catch (err) {
        setError(`Connection error: ${err.message}`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="surface-card p-5">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <div className="w-12 h-12 rounded-lg bg-[var(--primary-accent)] flex items-center justify-center">
            <svg className="w-6 h-6 text-white" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-medium text-[var(--text-primary)]">WeChat Work (WeCom)</h3>
            <p className="text-xs text-[var(--text-muted)]">Send transfers via WeChat Work bot</p>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <div className="relative">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Enter transfer command (e.g., 'transfer ¥600 to John')"
              className="w-full px-3 py-2 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none text-xs"
              disabled={sending}
            />
            {sending && (
              <div className="absolute right-3 top-2.5">
                <div className="w-4 h-4 border-2 border-[var(--border-color)] border-t-[var(--primary-accent)] rounded-full animate-spin"></div>
              </div>
            )}
          </div>
          <button
            onClick={handleSend}
            disabled={sending || !message.trim()}
            className={`text-xs px-4 py-2 rounded-md uppercase tracking-[0.1em] ${sending || !message.trim() ? 'disabled:opacity-50 disabled:pointer-events-none border-[var(--border-color)] text-[var(--text-muted)]' : 'btn-primary text-[var(--text-primary)] border-[var(--primary-accent)] bg-[var(--primary-accent)] text-white hover:bg-[var(--primary-accent)]/90'}`}
          >
            {sending ? 'Sending...' : 'Send'}
          </button>
        </div>

        {response && (
          <div className={`mt-3 p-3 rounded-md text-xs ${response.startsWith('✅') ? 'bg-[var(--positive-color)]/10 border border-[var(--positive-color)]/30 text-[var(--positive-color)]' : 'bg-[var(--negative-color)]/10 border border-[var(--negative-color)]/30 text-[var(--negative-color)]'}`}>
            {response}
          </div>
        )}

        {error && (
          <div className="mt-3 p-3 rounded-md border border-[var(--border-color)]/30 bg-[var(--negative-color)]/5 text-[var(--negative-color)] text-xs">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}