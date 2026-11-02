import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, FileSearch, Repeat2, Send, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { chatWithCfoAi } from '../services/api.js'

const suggestions = [
  { label: 'Transfer to @', prompt: 'I’d like to make a transfer. Help me choose a contact and review the details.', icon: ArrowUpRight },
  { label: 'Analyze my bills', prompt: 'Analyze my recent bills and point out anything unusual.', icon: FileSearch },
  { label: 'Cancel unused subscriptions', prompt: 'Help me find subscriptions I may not be using. Ask me before taking any action.', icon: Repeat2 },
]

function formatMessageTime(timestamp) {
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(timestamp))
}

export default function CfoChatPage({ onNotice }) {
  const { token } = useAuth()
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const threadRef = useRef(null)
  const [welcomeTime] = useState(() => Date.now())

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  function startPrompt(prompt) {
    setDraft(prompt)
    const input = document.querySelector('.chat-composer textarea')
    if (input) {
      input.style.height = 'auto'
      input.style.height = `${Math.min(input.scrollHeight, 112)}px`
      input.focus()
    }
  }

  async function submitMessage(event) {
    event.preventDefault()
    const message = draft.trim()
    if (!message || sending) return
    setMessages((current) => [...current, { id: `${Date.now()}-user`, role: 'user', text: message, timestamp: Date.now() }])
    setDraft('')
    const input = event.currentTarget.querySelector('textarea')
    if (input) input.style.height = '38px'
    setSending(true)
    try {
      const result = await chatWithCfoAi(message, token)
      setMessages((current) => [...current, {
        id: `${Date.now()}-assistant`,
        role: 'assistant',
        text: result.message,
        timestamp: Date.now(),
      }])
    } catch (error) {
      setMessages((current) => [...current, {
        id: `${Date.now()}-error`,
        role: 'assistant',
        text: error.message || 'I could not reach FINN AI. Please try again.',
        timestamp: Date.now(),
      }])
    } finally {
      setSending(false)
    }
  }

  function updateDraft(event) {
    setDraft(event.target.value)
    event.target.style.height = 'auto'
    event.target.style.height = `${Math.min(event.target.scrollHeight, 112)}px`
  }

  return <section className="chat-page">
    <div className="chat-thread" ref={threadRef}>
      <div className="suggestion-intro"><Sparkles size={14}/><span>HERE ARE A FEW THINGS I CAN HELP WITH</span></div>
      <div className="chat-suggestions">{suggestions.map(({label,prompt,icon:Icon})=><button className="suggestion-card" key={label} onClick={()=>startPrompt(prompt)}><span><Icon size={17}/></span><b>{label}</b><i>↗</i></button>)}</div>
      <div className="chat-welcome"><time className="message-time" dateTime={new Date(welcomeTime).toISOString()}>FINN AI · {formatMessageTime(welcomeTime)}</time><div className="welcome-bubble"><p>Hi there, I’m FINN, your financial navigator. Tell me what you need and I’ll help you with it. I’ll always ask before doing anything risky.</p></div></div>
      {messages.map(({ id, role, text, timestamp }) => role === 'user'
        ? <div className="user-message" key={id}><time className="message-time user-message-time" dateTime={new Date(timestamp).toISOString()}>{formatMessageTime(timestamp)}</time><span>{text}</span></div>
        : <div className="chat-welcome assistant-message" key={id}><time className="message-time" dateTime={new Date(timestamp).toISOString()}>FINN AI · {formatMessageTime(timestamp)}</time><div className="welcome-bubble"><p>{text}</p></div></div>)}
      {sending && <div className="chat-welcome assistant-message" role="status"><span className="message-time">FINN AI · THINKING</span><div className="welcome-bubble"><p>One moment…</p></div></div>}
    </div>
    <form className="chat-composer" onSubmit={submitMessage}><textarea rows="1" value={draft} onChange={updateDraft} placeholder="Ask FINN…" aria-label="Message FINN AI" disabled={sending}/><button type="submit" disabled={!draft.trim() || sending} aria-label="Send message"><Send size={17}/></button></form>
  </section>
}

