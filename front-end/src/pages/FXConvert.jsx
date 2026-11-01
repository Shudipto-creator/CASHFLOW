import React, { useState } from 'react';
import { getBankingToolsFX as getFXRates, convertCurrency } from '../services/api';
import { useSignedBankingApi } from '../hooks/useSignedBankingApi';

export default function FXConvert() {
  const [fromCurrency, setFromCurrency] = useState('CNY');
  const [toCurrency, setToCurrency] = useState('USD');
  const [amount, setAmount] = useState('');
  const [result, setResult] = useState(null);
  const [sending, setSending] = useState(false);
  const [rate, setRate] = useState(null);
  const [error, setError] = useState('');
  const { registerPublicKey, signedRequest } = useSignedBankingApi();

  React.useEffect(() => {
    registerPublicKey().catch(() => setError('Unable to initialize secure banking access'));
  }, [registerPublicKey]);

  const currencies = [
    { code: 'CNY', name: 'CNY - Chinese Yuan' },
    { code: 'USD', name: 'USD - US Dollar' },
    { code: 'EUR', name: 'EUR - Euro' },
    { code: 'JPY', name: 'JPY - Japanese Yen' },
  ];

  const fetchRate = async () => {
    try {
      const res = await signedRequest(
        getFXRates,
        null,
        {
          url: '/api/banking/fx/rates',
          method: 'GET',
          params: { from_currency: fromCurrency, to_currency: toCurrency },
        },
      );
      setRate(res.data.rate);
    } catch (err) {
      setError(`Failed to fetch rate: ${err.message}`);
    }
  };

  const handleConvert = async (e) => {
    e.preventDefault();
    if (!amount || parseFloat(amount) <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    setSending(true);
    setError('');

    try {
      const response = await signedRequest(
        convertCurrency,
        { from_currency: fromCurrency, to_currency: toCurrency, amount: Number(amount) },
        { url: '/api/banking/fx/convert', method: 'POST' },
      );
      setResult(response.data.conversion);
      setRate(response.data.conversion.rate);
    } catch (err) {
      setError(`Conversion failed: ${err.message}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="surface-card p-6">
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <div className="w-12 h-12 rounded-lg bg-[var(--primary-accent)] flex items-center justify-center">
            <svg className="w-6 h-6 text-white" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-medium text-[var(--text-primary)]">Currency Conversion</h3>
            <p className="text-xs text-[var(--text-muted)]">Convert between CNY, USD, EUR, and JPY</p>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex-1">
            <label className="text-xs font-medium text-[var(--text-muted)] mb-1">From Currency</label>
            <select
              value={fromCurrency}
              onChange={(e) => setFromCurrency(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none text-xs"
            >
              {currencies.map((c) => (
                <option key={c.code} value={c.code}>{c.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-[var(--text-muted)]">to</span>
            <select
              value={toCurrency}
              onChange={(e) => setToCurrency(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none text-xs"
            >
              {currencies.map((c) => (
                <option key={c.code} value={c.code}>{c.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <div className="relative">
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Enter amount"
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
            onClick={handleConvert}
            disabled={sending || !amount || parseFloat(amount) <= 0}
            className={`btn-primary text-[var(--text-primary)] disabled:opacity-50 disabled:pointer-events-none flex-1 py-2 px-4 text-xs uppercase tracking-[0.1em] w-full ${sending || !amount || parseFloat(amount) <= 0 ? 'opacity-50 disabled:pointer-events-none' : 'bg-[var(--primary-accent)] text-white hover:bg-[var(--primary-accent)]/90'}`}
          >
            {sending ? 'Converting...' : 'Convert'}
          </button>
        </div>

        <button type="button" onClick={fetchRate} disabled={sending} className="text-xs text-[var(--primary-accent)]">
          {rate ? `Current rate: 1 ${fromCurrency} = ${rate} ${toCurrency}` : 'Check current rate'}
        </button>

        {result && (
          <div className={`mt-3 p-3 rounded-md border border-[var(--positive-color)]/40 bg-[var(--positive-color)]/10 text-[var(--positive-color)] text-xs`}>
            <div className="flex flex-col gap-2">
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Source:</span>
                <span className="font-mono">{result.original_amount} {result.currency_from}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Converted:</span>
                <span className="font-mono">{result.converted_amount} {result.currency_to}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Exchange Rate:</span>
                <span className="font-mono">{result.rate}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">Fee (1%):</span>
                <span className="font-mono">{result.fee.toFixed(2)} {result.currency_from}</span>
              </div>
              <div className="flex justify-between text-[var(--text-primary)]">
                <span className="text-[var(--text-primary)]">Total:</span>
                <span className="font-mono">{result.total_charged.toFixed(2)} {result.currency_from}</span>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-3 p-3 rounded-md border border-[var(--negative-color)]/30 bg-[var(--negative-color)]/5 text-[var(--negative-color)] text-xs">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}