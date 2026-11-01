import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, FileSearch, Repeat2, Send, Sparkles } from 'lucide-react'

const suggestions = [
  { label: 'Transfer to @', prompt: 'I’d like to make a transfer. Help me choose a contact and review the details.', icon: ArrowUpRight },
  { label: 'Analyze my bills', prompt: 'Analyze my recent bills and point out anything unusual.', icon: FileSearch },
  { label: 'Cancel unused subscriptions', prompt: 'Help me find subscriptions I may not be using. Ask me before taking any action.', icon: Repeat2 },
]

export default function CfoChatPage({ onNotice }) {
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const threadRef = useRef(null)

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

  function submitMessage(event) {
    event.preventDefault()
    if (!draft.trim()) return
    setMessages((current) => [...current, { id: `${Date.now()}-${current.length}`, text: draft.trim() }])
    setDraft('')
    const input = event.currentTarget.querySelector('textarea')
    if (input) input.style.height = '38px'
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
      <div className="chat-welcome"><span className="message-time">CFO AI · JUST NOW</span><div className="welcome-bubble"><p>Hi there, I’m CFO AI, your financial navigator. Tell me what you need and I’ll help you with it. I’ll always ask before doing anything risky.</p></div></div>
      {messages.map(({ id, text }) => <div className="user-message" key={id}><span>{text}</span></div>)}
    </div>
    <form className="chat-composer" onSubmit={submitMessage}><textarea rows="1" value={draft} onChange={updateDraft} placeholder="Ask CFO AI…" aria-label="Message CFO AI"/><button type="submit" disabled={!draft.trim()} aria-label="Send message"><Send size={17}/></button></form>
  </section>
}

