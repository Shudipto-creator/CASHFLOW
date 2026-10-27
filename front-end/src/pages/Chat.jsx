import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Square, Volume2 } from 'lucide-react';
import { askCFO, clearChatHistory, getChatHistory } from '../services/api';
import { useMode } from '../context/ModeContext';
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
  const messagesEndRef = useRef(null);
  const audioRef = useRef(null);
  const synthesisRef = useRef(null);
  const utteranceRef = useRef(null);
  const recognitionRef = useRef(null);

  const isVoiceSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  const isRecognitionSupported = typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);
  const hasPendingMessage = messages.some((message) => message.status === 'pending');

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
      setError(err.response?.data?.detail || err.response?.data?.error?.message || 'Failed to send message');
    } finally {
      setSending(false);
    }
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

        {analysisId && messages.map((msg, idx) => (
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
        {analysisId && (
          <form onSubmit={handleSend} className="flex gap-3">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
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
        )}
        {!analysisId && (
          <p className="text-[var(--text-muted)] font-mono text-xs uppercase tracking-widest">
            Open a report to start asking questions
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
