import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { askCFO } from '../services/api';
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
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [voiceResponse, setVoiceResponse] = useState(true);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const messagesEndRef = useRef(null);
  const audioRef = useRef(null);
  const synthesisRef = useRef(null);
  const recognitionRef = useRef(null);

  const isVoiceSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  const isRecognitionSupported = typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

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

  useEffect(() => {
    if (selectedText) {
      setMessages([
        {
          role: 'user',
          content: `Selected text from "${selectedSection || 'report'}":\n\n${selectedText}`,
        },
      ]);
    }
  }, [selectedText, selectedSection]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const speakText = (text) => {
    if (!voiceResponse || !isVoiceSupported || !synthesisRef.current) return;
    synthesisRef.current.cancel();
    const utterance = new window.SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 1;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    synthesisRef.current.speak(utterance);
  };

  const playAudio = (audioBase64) => {
    if (!audioBase64) return;
    try {
      const audio = audioRef.current || new Audio();
      audioRef.current = audio;
      audio.src = `data:audio/mpeg;base64,${audioBase64}`;
      audio.play().catch(() => {});
    } catch (err) {
      console.warn('Audio playback failed:', err);
    }
  };

  const stopSpeaking = () => {
    if (synthesisRef.current) {
      synthesisRef.current.cancel();
    }
    setSpeaking(false);
  };

  const handleSend = async (e) => {
    e.preventDefault();
    const question = inputValue.trim();
    if (!question || sending) return;

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
        chat_history: messages.slice(0, -1),
        selected_text: selectedText || undefined,
        selected_section: selectedSection || undefined,
        voice_response: voiceResponse && mode === 'aws',
      });

      const data = response.data;
      setMessages((prev) => [...prev, { role: 'assistant', content: data.answer }]);
      playAudio(data.audio_base64);
      if (!data.audio_base64) {
        speakText(data.answer);
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

  const handleClear = () => {
    setMessages([]);
    setError(null);
    stopSpeaking();
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
            disabled={sending || messages.length === 0}
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

        {analysisId && messages.length === 0 && (
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
              {msg.role === 'assistant' && isVoiceSupported && !speaking && (
                <button
                  onClick={() => {
                    stopSpeaking();
                    speakText(msg.content);
                  }}
                  className="absolute top-2 right-2 text-[10px] font-medium text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors uppercase tracking-widest"
                >
                  Speak
                </button>
              )}
            </div>
          </div>
        ))}

        {error && (
          <div className="p-4 border border-[var(--negative-color)] bg-[rgba(185,28,28,0.05)] rounded-sm">
            <p className="font-mono text-sm text-[var(--negative-color)]">{error}</p>
          </div>
        )}

        {sending && (
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
              disabled={sending}
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
              disabled={sending || !inputValue.trim()}
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
