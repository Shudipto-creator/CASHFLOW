import React, { useState, useRef, useEffect } from "react";
import { askCFO } from "../../services/api";

/**
 * AskCFOChat Component
 *
 * Chat interface for AgentCFO – CEO asks financial questions
 * about the generated report, gets CFO-level strategic guidance.
 *
 * Props:
 *   analysisId  – The completed analysis ID (required for context)
 *   reportData  – Optional report data for display context
 */
const AskCFOChat = ({ analysisId, reportData, selectedContext = null }) => {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hello! I'm **AgentCFO**, your financial advisor. Ask me anything about this report—cash runway, profit margins, funding strategy, expense optimization, or financial risks.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [listening, setListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [activeSelectionContext, setActiveSelectionContext] = useState(null);
  const bottomRef = useRef(null);
  const recognitionRef = useRef(null);
  const activeAudioRef = useRef(null);
  const textareaRef = useRef(null);

  // Auto-scroll to newest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!selectedContext?.id || !selectedContext?.text) return;

    setActiveSelectionContext({
      text: selectedContext.text,
      section: selectedContext.section || "Financial Analysis Report",
    });

    const trimmedText = selectedContext.text.trim();
    const preview =
      trimmedText.length > 240
        ? `${trimmedText.slice(0, 240)}...`
        : trimmedText;

    setInput(
      `Regarding this selected text from ${selectedContext.section || "the report"}: "${preview}"\n\nCan you explain what this means and what action I should take?`,
    );

    setTimeout(() => {
      textareaRef.current?.focus();
    }, 120);
  }, [selectedContext?.id]);

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    setSpeechSupported(Boolean(SpeechRecognition));

    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onstart = () => {
      setListening(true);
      setError(null);
    };

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        transcript += event.results[i][0].transcript;
      }
      setInput(transcript.trim());
    };

    recognition.onerror = (event) => {
      setListening(false);
      if (event.error !== "no-speech") {
        setError(`Voice input error: ${event.error}`);
      }
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (activeAudioRef.current) {
        activeAudioRef.current.pause();
        activeAudioRef.current = null;
      }
      window.speechSynthesis?.cancel();
    };
  }, []);

  const stopActiveSpeech = () => {
    if (activeAudioRef.current) {
      activeAudioRef.current.pause();
      activeAudioRef.current = null;
    }
    window.speechSynthesis?.cancel();
    setIsSpeaking(false);
  };

  const playAssistantVoice = (text, audioBase64, audioMimeType) => {
    if (!voiceEnabled) return;

    stopActiveSpeech();

    if (audioBase64) {
      const binary = atob(audioBase64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }

      const blob = new Blob([bytes], { type: audioMimeType || "audio/mpeg" });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      activeAudioRef.current = audio;
      setIsSpeaking(true);

      audio.onended = () => {
        setIsSpeaking(false);
        URL.revokeObjectURL(url);
        activeAudioRef.current = null;
      };
      audio.onerror = () => {
        setIsSpeaking(false);
        URL.revokeObjectURL(url);
        activeAudioRef.current = null;
      };
      audio.play().catch(() => {
        setIsSpeaking(false);
        URL.revokeObjectURL(url);
        activeAudioRef.current = null;
      });
      return;
    }

    if ("speechSynthesis" in window) {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-US";
      utterance.rate = 0.95;
      utterance.pitch = 1;
      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utterance);
    }
  };

  const handleVoiceInput = () => {
    if (!speechSupported || !recognitionRef.current || loading) return;

    if (listening) {
      recognitionRef.current.stop();
      return;
    }

    setInput("");
    recognitionRef.current.start();
  };

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading) return;

    setError(null);
    const userMessage = { role: "user", content: question };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      // Build chat history (exclude system greeting and latest user turn)
      const historyForAPI = messages
        .filter((m) => m.role !== "system")
        .map((m) => ({ role: m.role, content: m.content }));

      const payload = {
        question,
        analysis_id: analysisId,
        chat_history: historyForAPI,
        voice_response: voiceEnabled,
        voice_id: "Matthew",
        selected_text: activeSelectionContext?.text || undefined,
        selected_section: activeSelectionContext?.section || undefined,
      };

      const response = await askCFO(payload);
      const assistantMessage = {
        role: "assistant",
        content: response.data.answer,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      playAssistantVoice(
        response.data.answer,
        response.data.audio_base64,
        response.data.audio_mime_type,
      );
      setActiveSelectionContext(null);
    } catch (err) {
      const errMsg =
        err.response?.data?.detail ||
        err.response?.data?.error?.message ||
        "Failed to get AgentCFO response. Please try again.";
      setError(errMsg);
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Suggested questions for executive-level inquiries
  const suggestedQuestions = [
    "How can we improve our profit margin?",
    "What is our biggest financial risk?",
    "Should we raise funding right now?",
    "How can we extend our runway?",
    "Which expenses should we cut first?",
    "Is our burn rate dangerous?",
  ];

  const handleSuggestion = (q) => {
    setInput(q);
  };

  return (
    <div
      className="surface-card flex flex-col overflow-hidden rounded-sm"
      style={{ height: "700px", borderTop: "1px solid var(--border-color)" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-color)] flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-gradient-to-br from-[var(--primary-accent)] to-[var(--secondary-accent)] flex items-center justify-center">
            <span className="font-mono text-[10px] font-bold text-[var(--bg-color)]">
              CFO
            </span>
          </div>
          <div>
            <h2 className="font-display text-base font-semibold text-[var(--text-primary)]">
              AgentCFO
            </h2>
            <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase">
              Financial Strategic Advisor
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isSpeaking && (
            <span className="font-mono text-[9px] tracking-widest text-[var(--primary-accent)] uppercase">
              Speaking
            </span>
          )}
          <span className="w-2 h-2 rounded-full bg-[var(--positive-color)] animate-pulse"></span>
          <span className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase">
            Ready
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 scrollbar-thin">
        {messages.map((msg, idx) => (
          <MessageBubble key={idx} message={msg} />
        ))}

        {/* Typing indicator */}
        {loading && (
          <div className="flex items-end gap-2">
            <div className="w-6 h-6 rounded-sm bg-[var(--surface-color)] border border-[var(--border-color)] flex items-center justify-center flex-shrink-0">
              <span className="font-mono text-[7px] text-[var(--primary-accent)]">
                CFO
              </span>
            </div>
            <div className="bg-[var(--surface-color)] border border-[var(--border-color)] rounded-sm px-4 py-3">
              <div className="flex gap-1 items-center h-4">
                <span
                  className="w-1.5 h-1.5 rounded-full bg-[var(--primary-accent)] animate-bounce"
                  style={{ animationDelay: "0ms" }}
                ></span>
                <span
                  className="w-1.5 h-1.5 rounded-full bg-[var(--primary-accent)] animate-bounce"
                  style={{ animationDelay: "150ms" }}
                ></span>
                <span
                  className="w-1.5 h-1.5 rounded-full bg-[var(--primary-accent)] animate-bounce"
                  style={{ animationDelay: "300ms" }}
                ></span>
              </div>
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="font-mono text-[11px] text-[var(--negative-color)] border border-[var(--negative-color)] bg-[rgba(255,59,59,0.05)] rounded-sm px-4 py-3">
            ⚠ {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Suggested Questions (show only when there's just the greeting) */}
      {messages.length === 1 && (
        <div className="px-6 pb-3 flex flex-wrap gap-2 flex-shrink-0">
          {suggestedQuestions.slice(0, 4).map((q, i) => (
            <button
              key={i}
              onClick={() => handleSuggestion(q)}
              className="font-mono text-[9px] tracking-wider px-3 py-1.5 border border-[var(--border-color)] text-[var(--text-muted)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)] transition-colors rounded-sm whitespace-nowrap"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div className="px-6 py-4 border-t border-[var(--border-color)] flex items-end gap-3 flex-shrink-0">
        <button
          type="button"
          onClick={handleVoiceInput}
          disabled={!speechSupported || loading}
          className={`h-full px-4 py-3 border rounded-sm font-mono text-[10px] tracking-widest uppercase transition-colors flex items-center gap-2 flex-shrink-0 ${
            listening
              ? "border-[var(--negative-color)] text-[var(--negative-color)] bg-[rgba(255,59,59,0.06)]"
              : "border-[var(--border-color)] text-[var(--text-muted)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)]"
          } disabled:opacity-40 disabled:cursor-not-allowed`}
          title={
            speechSupported
              ? "Voice input"
              : "Speech recognition is not supported in this browser"
          }
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 1v11m0 0a4 4 0 004-4V5a4 4 0 10-8 0v3a4 4 0 004 4zm0 0v4m-6 0h12"
            />
          </svg>
          <span className="hidden sm:inline">
            {listening ? "Listening" : "Mic"}
          </span>
        </button>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask AgentCFO... (Enter to send)"
          rows={2}
          disabled={loading}
          className="flex-1 resize-none bg-[var(--bg-color)] border border-[var(--border-color)] rounded-sm px-4 py-3 font-mono text-[12px] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--primary-accent)] transition-colors disabled:opacity-50"
        />
        <button
          type="button"
          onClick={() => {
            if (voiceEnabled) {
              stopActiveSpeech();
            }
            setVoiceEnabled((prev) => !prev);
          }}
          className={`h-full px-4 py-3 border rounded-sm font-mono text-[10px] tracking-widest uppercase transition-colors flex items-center gap-2 flex-shrink-0 ${
            voiceEnabled
              ? "border-[var(--secondary-accent)] text-[var(--secondary-accent)]"
              : "border-[var(--border-color)] text-[var(--text-muted)] hover:border-[var(--secondary-accent)] hover:text-[var(--secondary-accent)]"
          }`}
          title="Toggle voice replies"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 10l4.55-2.27A1 1 0 0121 8.62v6.76a1 1 0 01-1.45.9L15 14m-8-6h4l4-3v14l-4-3H7a2 2 0 01-2-2v-4a2 2 0 012-2z"
            />
          </svg>
          <span className="hidden sm:inline">
            {voiceEnabled ? "Voice On" : "Voice Off"}
          </span>
        </button>
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          className="h-full px-5 py-3 bg-[var(--primary-accent)] text-[var(--bg-color)] font-mono text-[11px] tracking-widest uppercase rounded-sm hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 flex-shrink-0"
        >
          {loading ? (
            <svg
              className="animate-spin w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
              />
            </svg>
          ) : (
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          )}
          <span className="hidden sm:inline">Send</span>
        </button>
      </div>
    </div>
  );
};

// =====================================================================
// Individual message bubble with markdown-like formatting
// =====================================================================

const MessageBubble = ({ message }) => {
  const isUser = message.role === "user";

  // Simple markdown rendering (**text** → bold)
  const renderContent = (text) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      // Render line breaks
      return part.split("\n").map((line, j) => (
        <React.Fragment key={`${i}-${j}`}>
          {line}
          {j < part.split("\n").length - 1 && <br />}
        </React.Fragment>
      ));
    });
  };

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-[var(--primary-accent)] text-[var(--bg-color)] rounded-sm px-4 py-3">
          <p className="font-mono text-[12px] leading-relaxed">
            {message.content}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-end gap-2">
      <div className="w-6 h-6 rounded-sm bg-[var(--surface-color)] border border-[var(--border-color)] flex items-center justify-center flex-shrink-0 mb-0.5">
        <span className="font-mono text-[7px] text-[var(--primary-accent)]">
          CFO
        </span>
      </div>
      <div className="max-w-[85%] bg-[var(--surface-color)] border border-[var(--border-color)] rounded-sm px-4 py-3">
        <p className="font-mono text-[12px] leading-relaxed text-[var(--text-secondary)]">
          {renderContent(message.content)}
        </p>
      </div>
    </div>
  );
};

export default AskCFOChat;
