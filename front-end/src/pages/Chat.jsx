import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Square, Volume2 } from 'lucide-react';
import {
  askCFO,
  bankingCall,
  clearChatHistory,
  executeBankingTransfer,
  getChatHistory,
  getMfaCode,
  prepareBankingTransfer,
  approveBankingTransfer,
  startMfaChallenge,
} from '../services/api';
import { useMode } from '../context/ModeContext';
import { useSignedBankingApi } from '../hooks/useSignedBankingApi';
import LoadingSpinner from '../components/Common/LoadingSpinner';

const Chat = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { mode, loading: modeLoading } = useMode();

  const query = new URLSearchParams(location.search);
  const analysisId = query.get('analysis_id') || '';
  const selectedText = query.get('selected_text') || '';
  const selectedSection = query.get('selected_section') || '';

  const [messages, setMessages] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(Boolean(analysisId));
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [voiceResponse, setVoiceResponse] = useState(true);
  const [listening, setListening] = useState(false);
  const [speakingMessageId, setSpeakingMessageId] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [transfer, setTransfer] = useState(null);
  const [transferLoading, setTransferLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const audioRef = useRef(null);
  const synthesisRef = useRef(null);
  const utteranceRef = useRef(null);
  const recognitionRef = useRef(null);
  const { registerPublicKey, signedRequest } = useSignedBankingApi();

  const isVoiceSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  const isRecognitionSupported = typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);
  const hasPendingMessage = messages.some((message) => message.status === 'pending');

  useEffect(() => {
    let active = true;
    registerPublicKey();
    signedRequest(bankingCall, { tool: 'get-accounts', args: {} }, { url: '/api/banking/call' })
      .then((response) => {
        if (!active) return;
        const value = response.data.value || {};
        setAccounts(value.items || value.accounts || []);
      })
      .catch(() => {
        if (active) setAccounts([]);
      })
      .finally(() => {
        if (active) setAccountsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [registerPublicKey, signedRequest]);

  const accountSuggestions = accounts.slice(0, 5);

  const useAccountSuggestion = (account) => {
    const label = account.name || account.owner || account.id || account.account_id || 'this account';
    setInputValue(`Show me the balance and recent transactions for ${label}`);
  };

  const parseTransferRequest = (question) => {
    const match = question.match(
      /^(?:please\s+)?transfer\s+(?:¥|\$)?([\d,]+(?:\.\d{1,2})?)\s+(?:cny\s+)?to\s+(.+?)(?:\s+account(?:\s*(?:number|no\.?)?)?\s*[:#-]?\s*([\w -]+))?$/i,
    );
    if (!match) return null;
    return {
      amount: Number(match[1].replace(/,/g, '')),
      creditorName: match[2].trim(),
      creditorAccount: match[3]?.trim() || '',
    };
  };

  const appendAssistantMessage = (content) => {
    setMessages((prev) => [...prev, { id: `local-${Date.now()}`, role: 'assistant', content }]);
  };

  const prepareChatTransfer = async (draft, confirmed = false, mfa = {}) => {
    if (!draft.creditorAccount) {
      appendAssistantMessage('I need the recipient account number before I can prepare this transfer.');
      return;
    }
    setTransferLoading(true);
    setError(null);
    try {
      const response = await signedRequest(
        prepareBankingTransfer,
        {
          debtor_account_id: draft.debtorAccountId,
          creditor: {
            name: draft.creditorName,
            accountIdentifier: {
              type: 'accountNumber',
              accountNumber: draft.creditorAccount,
              country: 'CN',
            },
          },
          amount: draft.amount,
          currency: 'CNY',
          rail: 'swift',
          confirmed,
          ...mfa,
        },
        { url: '/api/banking/transfer/prepare' },
      );
      const data = response.data;
      setTransfer((current) => ({ ...current, ...draft, ...data, stage: data.needs_mfa ? 'mfa' : data.needs_confirmation ? 'confirmation' : data.ok ? 'prepared' : 'error' }));
      if (data.needs_mfa) {
        const challenge = await signedRequest(
          startMfaChallenge,
          { subject: 'account-holder', purpose: 'strong verification for a chat transfer' },
          { url: '/api/banking/mfa/challenge' },
        );
        const code = await signedRequest(getMfaCode, challenge.data.challenge_id, {
          url: `/api/banking/mfa/code/${challenge.data.challenge_id}`,
        });
        setTransfer((current) => ({
          ...current,
          challengeId: challenge.data.challenge_id,
          deliveredCode: code.data.code,
          stage: 'mfa',
        }));
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Transfer preparation failed');
    } finally {
      setTransferLoading(false);
    }
  };

  const executeChatTransfer = async () => {
    if (!transfer?.intent_id) return;
    setTransferLoading(true);
    try {
      const response = await signedRequest(
        executeBankingTransfer,
        { intent_id: transfer.intent_id },
        { url: '/api/banking/transfer/execute' },
      );
      const data = response.data;
      setTransfer((current) => ({ ...current, ...data, stage: data.needs_approval ? 'approval' : data.ok ? 'settled' : 'error' }));
    } catch (err) {
      setError(err.response?.data?.detail || 'Transfer execution failed');
    } finally {
      setTransferLoading(false);
    }
  };

  const approveChatTransfer = async () => {
    if (!transfer?.intent_id || !transfer?.approval_id) return;
    setTransferLoading(true);
    try {
      await signedRequest(
        approveBankingTransfer,
        { approval_id: transfer.approval_id },
        { url: `/api/banking/transfer/execute/${encodeURIComponent(transfer.intent_id)}/approve` },
      );
      await executeChatTransfer();
    } catch (err) {
      setError(err.response?.data?.detail || 'Transfer approval failed');
      setTransferLoading(false);
    }
  };

  const verifyChatMfa = async () => {
    if (!transfer?.challengeId || !transfer?.mfaCode) return;
    await prepareChatTransfer(
      transfer,
      true,
      { mfa_challenge_id: transfer.challengeId, mfa_code: transfer.mfaCode },
    );
  };

  useEffect(() => {
    synthesisRef.current = window.speechSynthesis;
    if ('SpeechRecognition' in window) {
      recognitionRef.current = new window.SpeechRecognition();
    } else if ('webkitSpeechRecognition' in window) {
      recognitionRef.current = new window.webkitSpeechRecognition();
    }
    const rec = recognitionRef.current;
    if (rec) {
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = 'en-US';
      rec.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputValue(transcript);
        setListening(false);
      };
      rec.onerror = () => setListening(false);
      rec.onend = () => setListening(false);
    }
  }, []);

  useEffect(() => () => {
    synthesisRef.current?.cancel();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!analysisId) {
      setMessages([]);
      setLoadingHistory(false);
      return undefined;
    }

    let active = true;
    setMessages([]);
    setLoadingHistory(true);
    setError(null);

    getChatHistory(analysisId)
      .then((response) => {
        if (active) setMessages(response.data.messages || []);
      })
      .catch((err) => {
        if (active) {
          setError(err.response?.data?.detail || 'Failed to load chat history');
        }
      })
      .finally(() => {
        if (active) setLoadingHistory(false);
      });

    return () => {
      active = false;
    };
  }, [analysisId]);

  useEffect(() => {
    if (!analysisId || !hasPendingMessage) return undefined;

    const intervalId = setInterval(() => {
      getChatHistory(analysisId)
        .then((response) => setMessages(response.data.messages || []))
        .catch((err) => {
          setError(err.response?.data?.detail || 'Failed to refresh chat history');
        });
    }, 2000);

    return () => clearInterval(intervalId);
  }, [analysisId, hasPendingMessage]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const stopSpeaking = () => {
    const audio = audioRef.current;
    audioRef.current = null;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }

    utteranceRef.current = null;
    synthesisRef.current?.cancel();
    setSpeakingMessageId(null);
  };

  const speakText = (text, messageId) => {
    if (!isVoiceSupported || !synthesisRef.current) return;
    stopSpeaking();
    const utterance = new window.SpeechSynthesisUtterance(text);
    utteranceRef.current = utterance;
    utterance.lang = 'en-US';
    utterance.rate = 1;
    setSpeakingMessageId(messageId);
    const clearSpeakingState = () => {
      if (utteranceRef.current !== utterance) return;
      utteranceRef.current = null;
      setSpeakingMessageId(null);
    };
    utterance.onend = clearSpeakingState;
    utterance.onerror = clearSpeakingState;
    synthesisRef.current.speak(utterance);
  };

  const playAudio = (audioBase64, messageId) => {
    if (!audioBase64) return;
    try {
      stopSpeaking();
      const audio = new Audio();
      audioRef.current = audio;
      audio.src = `data:audio/mpeg;base64,${audioBase64}`;
      setSpeakingMessageId(messageId);
      const clearSpeakingState = () => {
        if (audioRef.current !== audio) return;
        audioRef.current = null;
        setSpeakingMessageId(null);
      };
      audio.onended = clearSpeakingState;
      audio.onerror = clearSpeakingState;
      audio.play().catch(clearSpeakingState);
    } catch (err) {
      console.warn('Audio playback failed:', err);
      setSpeakingMessageId(null);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    const question = inputValue.trim();
    if (!question || sending || hasPendingMessage) return;

    const transferDraft = parseTransferRequest(question);
    if (transferDraft) {
    if (!transferDraft.amount || transferDraft.amount <= 0) {
      setError('Enter a transfer amount greater than zero.');
      return;
    }
    if (!transferDraft.creditorAccount) {
      setMessages((prev) => [...prev, { role: 'user', content: question }]);
      appendAssistantMessage('Tell me the recipient account number too. Example: “Transfer 25 to Alex account 123456”.');
      setInputValue('');
      return;
    }
    setMessages((prev) => [...prev, { role: 'user', content: question }]);
    setInputValue('');
    setTransfer({
      ...transferDraft,
      debtorAccountId: '',
      stage: 'draft',
    });
    return;
    }

    const userMessage = { role: 'user', content: question };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setError(null);
    setSending(true);
    stopSpeaking();

    try {
      const response = await askCFO({
        question,
        analysis_id: analysisId || undefined,
        selected_text: selectedText || undefined,
        selected_section: selectedSection || undefined,
        voice_response: voiceResponse && mode === 'aws',
      });

      const data = response.data;
      const assistantMessage = {
        id: data.message_id,
        role: 'assistant',
        content: data.answer,
      };

      setMessages((prev) => (
        prev.some((message) => message.id === assistantMessage.id)
          ? prev
          : [...prev, assistantMessage]
      ));
      if (data.audio_base64) {
        playAudio(data.audio_base64, assistantMessage.id);
      } else if (voiceResponse) {
        speakText(data.answer, assistantMessage.id);
      }
    } catch (err) {
      setError(
        err.code === 'ECONNABORTED'
          ? 'The request timed out. Please check the backend and try again.'
          : err.response?.data?.detail || err.response?.data?.error?.message || 'Failed to send message',
      );
    } finally {
      setSending(false);
    }
  };

  const handleInputKeyDown = (e) => {
    if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey) e.preventDefault();
  };

  const handleStartListening = () => {
    if (!isRecognitionSupported || !recognitionRef.current || listening) return;
    setListening(true);
    recognitionRef.current.start();
  };

  const handleClear = async () => {
    if (!analysisId || hasPendingMessage) return;
    if (!window.confirm('Clear the saved conversation for this analysis?')) return;
    try {
      await clearChatHistory(analysisId);
      setMessages([]);
      setError(null);
      stopSpeaking();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to clear chat history');
    }
  };

  const handleBack = () => {
    navigate(`/report/${analysisId}`);
  };

  const isVoiceEnabled = isVoiceSupported && !modeLoading;

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-[var(--border-color)] p-6 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-wide">AI CFO</h1>
          <p className="font-mono text-sm text-[var(--text-muted)] tracking-wide uppercase mt-1">
            Financial advisory chat
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={handleClear}
            disabled={sending || loadingHistory || hasPendingMessage || messages.length === 0}
            className="px-3 py-1.5 border border-[var(--border-color)] text-[10px] font-medium uppercase tracking-widest text-[var(--text-muted)] rounded-sm disabled:opacity-50 hover:bg-[var(--surface-card)] transition-colors"
          >
            Clear
          </button>
          <label className="flex items-center space-x-2 text-[var(--text-muted)] font-mono text-xs uppercase tracking-widest cursor-pointer">
            <input
              type="checkbox"
              checked={voiceResponse && isVoiceEnabled}
              onChange={(e) => setVoiceResponse(e.target.checked)}
              disabled={!isVoiceEnabled}
              className="w-4 h-4 text-[var(--primary-accent)] border-[var(--border-color)] rounded-sm focus:ring-[var(--primary-accent)]"
            />
            Voice response
          </label>
          {!isVoiceEnabled && (
            <span className="font-mono text-[10px] text-[var(--text-muted)] uppercase tracking-widest">
              Voice unavailable
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4" ref={messagesEndRef}>
        {!analysisId && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <p className="font-mono text-sm text-[var(--text-muted)] tracking-wide uppercase mb-4">
              Start from a report
            </p>
            <p className="text-[var(--text-secondary)] font-mono text-xs mb-6">
              Open a completed analysis report to ask AI CFO questions about it.
            </p>
            <button
              onClick={() => navigate('/analysis')}
              className="px-6 py-3 border border-[var(--border-color)] rounded-sm text-sm font-medium uppercase tracking-wider text-[var(--text-primary)] hover:bg-[var(--surface-card)] transition-colors"
            >
              Go to Analysis
            </button>
          </div>
        )}

        {analysisId && loadingHistory && (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="small" />
            <span className="ml-3 font-mono text-[10px] text-[var(--text-muted)] uppercase tracking-widest">
              Loading conversation
            </span>
          </div>
        )}

        {analysisId && !loadingHistory && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <p className="font-mono text-sm text-[var(--text-muted)] tracking-wide uppercase mb-4">
              Ask a financial question
            </p>
            <p className="font-mono text-[10px] text-[var(--text-muted)] uppercase tracking-widest">
              Context: analysis {analysisId}
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] p-4 rounded-sm font-mono text-sm leading-relaxed relative ${
                msg.role === 'user'
                  ? 'bg-[var(--primary-accent)] text-[var(--bg-color)] text-right'
                  : 'bg-[var(--surface-card)] border border-[var(--border-color)] text-[var(--text-primary)]'
              }`}
            >
              {msg.content}
              {msg.role === 'assistant' && (isVoiceSupported || speakingMessageId === msg.id) && (
                <button
                  type="button"
                  onClick={() => (
                    speakingMessageId === msg.id
                      ? stopSpeaking()
                      : speakText(msg.content, msg.id)
                  )}
                  aria-label={speakingMessageId === msg.id ? 'Stop speaking' : 'Speak message'}
                  title={speakingMessageId === msg.id ? 'Stop speaking' : 'Speak message'}
                  className="mt-3 inline-flex h-7 items-center gap-1.5 border border-[var(--border-color)] px-2 text-[10px] font-medium text-[var(--text-muted)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)] transition-colors uppercase tracking-widest"
                >
                  {speakingMessageId === msg.id
                    ? <Square className="h-3 w-3 fill-current" aria-hidden="true" />
                    : <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />}
                  <span>{speakingMessageId === msg.id ? 'Stop speaking' : 'Speak'}</span>
                </button>
              )}
            </div>
          </div>
        ))}

        {transfer && (
          <div className="rounded-sm border border-[var(--primary-accent)]/50 bg-[var(--surface-card)] p-4">
            <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--primary-accent)]">
              Zero-trust transfer
            </p>
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <dt className="text-[var(--text-muted)]">Recipient</dt>
              <dd className="text-[var(--text-primary)]">{transfer.creditorName}</dd>
              <dt className="text-[var(--text-muted)]">Account</dt>
              <dd className="font-mono text-[var(--text-primary)]">{transfer.creditorAccount}</dd>
              <dt className="text-[var(--text-muted)]">Amount</dt>
              <dd className="text-[var(--text-primary)]">{transfer.amount} CNY</dd>
              <dt className="text-[var(--text-muted)]">From account</dt>
              <dd>
                <select
                  value={transfer.debtorAccountId}
                  onChange={(e) => setTransfer((current) => ({ ...current, debtorAccountId: e.target.value }))}
                  disabled={transfer.stage !== 'draft'}
                  className="w-full rounded-sm border border-[var(--border-color)] bg-transparent px-2 py-1 text-xs text-[var(--text-primary)]"
                >
                  <option value="">Select source account</option>
                  {accounts.map((account) => {
                    const id = String(account.id || account.account_id || '');
                    return <option key={id} value={id}>{account.name || account.owner || id} · {id}</option>;
                  })}
                </select>
              </dd>
              <dt className="text-[var(--text-muted)]">Stage</dt>
              <dd className="text-[var(--text-primary)]">{transfer.stage}</dd>
            </dl>
            {transfer.stage === 'draft' && (
              <button
                type="button"
                onClick={() => prepareChatTransfer(transfer)}
                disabled={transferLoading || !transfer.debtorAccountId}
                className="mt-4 rounded-sm border border-[var(--primary-accent)] px-4 py-2 text-xs uppercase tracking-widest text-[var(--primary-accent)] disabled:opacity-50"
              >
                {transferLoading ? 'Preparing…' : 'Review and prepare'}
              </button>
            )}
            {transfer.stage === 'confirmation' && (
              <button
                type="button"
                onClick={() => prepareChatTransfer(transfer, true)}
                disabled={transferLoading}
                className="mt-4 rounded-sm border border-[var(--primary-accent)] px-4 py-2 text-xs uppercase tracking-widest text-[var(--primary-accent)] disabled:opacity-50"
              >
                {transferLoading ? 'Confirming…' : 'Confirm transfer details'}
              </button>
            )}
            {transfer.stage === 'mfa' && (
              <div className="mt-4 flex gap-2">
                <input
                  value={transfer.mfaCode || ''}
                  onChange={(e) => setTransfer((current) => ({ ...current, mfaCode: e.target.value.replace(/\D/g, '') }))}
                  placeholder="6-digit MFA code"
                  maxLength="6"
                  className="min-w-0 flex-1 rounded-sm border border-[var(--border-color)] bg-transparent px-3 py-2 text-xs text-[var(--text-primary)]"
                />
                <button
                  type="button"
                  onClick={verifyChatMfa}
                  disabled={transferLoading || (transfer.mfaCode || '').length !== 6}
                  className="rounded-sm border border-[var(--primary-accent)] px-3 py-2 text-xs uppercase tracking-widest text-[var(--primary-accent)] disabled:opacity-50"
                >
                  Verify MFA
                </button>
              </div>
            )}
            {transfer.deliveredCode && transfer.stage === 'mfa' && (
              <p className="mt-2 text-[10px] text-[var(--text-muted)]">
                Demo MFA code: <span className="font-mono">{transfer.deliveredCode}</span>
              </p>
            )}
            {transfer.stage === 'prepared' && (
              <button
                type="button"
                onClick={executeChatTransfer}
                disabled={transferLoading}
                className="mt-4 rounded-sm border border-[var(--primary-accent)] px-4 py-2 text-xs uppercase tracking-widest text-[var(--primary-accent)] disabled:opacity-50"
              >
                {transferLoading ? 'Submitting…' : 'Execute transfer'}
              </button>
            )}
            {transfer.stage === 'approval' && (
              <button
                type="button"
                onClick={approveChatTransfer}
                disabled={transferLoading}
                className="mt-4 rounded-sm border border-[var(--primary-accent)] px-4 py-2 text-xs uppercase tracking-widest text-[var(--primary-accent)] disabled:opacity-50"
              >
                {transferLoading ? 'Approving…' : 'Approve and execute'}
              </button>
            )}
            {transfer.stage === 'settled' && (
              <p className="mt-4 text-xs text-[var(--positive-color)]">Transfer settled successfully.</p>
            )}
          </div>
        )}

        {error && (
          <div className="p-4 border border-[var(--negative-color)] bg-[rgba(248,113,113,0.08)] rounded-sm">
            <p className="font-mono text-sm text-[var(--negative-color)]">{error}</p>
          </div>
        )}

        {(sending || hasPendingMessage) && (
          <div className="flex justify-center items-center py-4">
            <LoadingSpinner size="small" />
            <span className="ml-3 font-mono text-[10px] text-[var(--text-muted)] uppercase tracking-widest">
              AgentCFO is typing
            </span>
          </div>
        )}
      </div>

      <div className="border-t border-[var(--border-color)] p-4">
        <>
          {accountsLoading && (
            <p className="mb-3 text-[10px] text-[var(--text-muted)]">Loading secure bank accounts…</p>
          )}
          {!accountsLoading && accountSuggestions.length > 0 && (
            <div className="mb-3">
              <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">
                Postman bank accounts
              </p>
              <div className="flex flex-wrap gap-2">
                {accountSuggestions.map((account) => {
                  const id = account.id || account.account_id;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => useAccountSuggestion(account)}
                      className="rounded-sm border border-[var(--border-color)] px-3 py-2 text-left text-xs text-[var(--text-secondary)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)]"
                    >
                      {account.name || account.owner || 'Account'} <span className="font-mono text-[10px]">#{id}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          <form onSubmit={handleSend} className="flex gap-3">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="Ask AI CFO a financial question\u2026"
              disabled={sending || hasPendingMessage || loadingHistory}
              className="flex-1 bg-transparent border border-[var(--border-color)] text-[var(--text-primary)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--primary-accent)] disabled:opacity-50"
            />
            {isRecognitionSupported && (
              <button
                type="button"
                onClick={handleStartListening}
                disabled={sending || listening}
                className={`px-3 py-2 border rounded-sm text-sm font-medium uppercase tracking-widest transition-colors ${
                  listening
                    ? 'bg-[var(--primary-accent)] text-[var(--bg-color)] border-[var(--primary-accent)]'
                    : 'bg-transparent border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--primary-accent)]'
                }`}
              >
                {listening ? 'Listening...' : 'Mic'}
              </button>
            )}
            <button
              type="submit"
              disabled={sending || hasPendingMessage || loadingHistory || !inputValue.trim()}
              className="px-4 py-2 border border-[var(--border-color)] text-[var(--text-primary)] text-sm font-medium uppercase tracking-widest rounded-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--surface-card)] transition-colors"
            >
              Send
            </button>
          </form>
        </>
        {analysisId && (
          <p className="mt-2 text-[10px] text-[var(--text-muted)]">
            Click Send to submit. Enter stays in the field.
          </p>
        )}
      </div>

      <div className="border-t border-[var(--border-color)] p-4 text-center">
        <button
          onClick={handleBack}
          disabled={!analysisId}
          className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-[10px] uppercase tracking-widest"
        >
          {analysisId ? 'Back to Report' : 'Back to Analysis'}
        </button>
      </div>
    </div>
  );
};

export default Chat;
