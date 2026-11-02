import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, FileSearch, Repeat2, Send, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { approveSandboxTransfer, chatWithCfoAi } from '../services/api.js'

const suggestions = [
  { label: 'Transfer to @', prompt: 'I’d like to make a transfer. Help me choose a contact and review the details.', icon: ArrowUpRight },
  { label: 'Analyze my bills', prompt: 'Analyze my recent bills and point out anything unusual.', icon: FileSearch },
  { label: 'Cancel unused subscriptions', prompt: 'Help me find subscriptions I may not be using. Ask me before taking any action.', icon: Repeat2 },
]

function formatMessageTime(timestamp) {
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date(timestamp))
}

export default function CfoChatPage({ onNotice, isActive = true }) {
  const { token } = useAuth()
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [mfaCodes, setMfaCodes] = useState({})
  const threadRef = useRef(null)
  const [welcomeTime] = useState(() => Date.now())

  useEffect(() => {
    if (isActive) threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isActive])

  function startPrompt(prompt) {
    setDraft(prompt)
    const input = document.querySelector('.chat-composer textarea')
    if (input) {
      input.style.height = 'auto'
      input.style.height = `${Math.min(input.scrollHeight, 112)}px`
      input.focus()
    }
  }

  function assistantMessage(result, originalText) {
    const execution = result.execution || {}
    const isTransfer = result.operation_id === 'prepare-transfer' && execution.transfer_preview
    let transferAction = null
    if (isTransfer && execution.needs_approval && execution.intent_id && execution.approval_id) {
      transferAction = { kind: 'approve', intentId: execution.intent_id, approvalId: execution.approval_id }
    } else if (isTransfer && ['CONFIRMATION_REQUIRED', 'MFA_REQUIRED'].includes(execution.code)) {
      transferAction = {
        kind: 'confirm', originalText,
        requiresMfa: execution.code === 'MFA_REQUIRED' || execution.needs_mfa,
        challengeId: execution.mfa_challenge_id,
      }
    }
    return {
      id: `${Date.now()}-assistant`, role: 'assistant', text: result.message,
      timestamp: Date.now(), transferPreview: isTransfer ? execution.transfer_preview : null,
      transferAction,
    }
  }

  async function confirmTransfer(message) {
    if (sending) return
    const code = (mfaCodes[message.id] || '').trim()
    if (message.transferAction.requiresMfa && !code) return
    setSending(true)
    try {
      const result = await chatWithCfoAi(message.transferAction.originalText, token, {
        confirmed: true,
        ...(message.transferAction.requiresMfa ? {
          mfa_challenge_id: message.transferAction.challengeId,
          mfa_code: code,
        } : {}),
      })
      setMessages((current) => [...current, assistantMessage(result, message.transferAction.originalText)])
    } catch (error) {
      setMessages((current) => [...current, { id: `${Date.now()}-error`, role: 'assistant', text: error.message || 'I could not prepare that transfer.', timestamp: Date.now() }])
    } finally {
      setSending(false)
    }
  }

  async function approveTransfer(message) {
    if (sending) return
    setSending(true)
    try {
      const result = await approveSandboxTransfer(message.transferAction.intentId, message.transferAction.approvalId, token)
      setMessages((current) => [...current, {
        id: `${Date.now()}-assistant`, role: 'assistant',
        text: result.ok ? (result.message || 'Transfer completed successfully.') : (result.message || 'The transfer was not completed.'),
        timestamp: Date.now(), transferPreview: message.transferPreview,
      }])
      if (result.ok) window.dispatchEvent(new Event('finn:bank-data-refresh'))
    } catch (error) {
      setMessages((current) => [...current, { id: `${Date.now()}-error`, role: 'assistant', text: error.message || 'I could not complete that transfer.', timestamp: Date.now() }])
    } finally {
      setSending(false)
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
      setMessages((current) => [...current, assistantMessage(result, message)])
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
      {messages.map((message) => {
        if (message.role === 'user') return <div className="user-message" key={message.id}><time className="message-time user-message-time" dateTime={new Date(message.timestamp).toISOString()}>{formatMessageTime(message.timestamp)}</time><span>{message.text}</span></div>
        return <div className="chat-welcome assistant-message" key={message.id}>
          <time className="message-time" dateTime={new Date(message.timestamp).toISOString()}>FINN AI · {formatMessageTime(message.timestamp)}</time>
          <div className="welcome-bubble">
            <p>{message.text}</p>
            {message.transferPreview && <div className="transfer-preview">
              <div><span>From</span><b>{message.transferPreview.source_account_name}</b></div>
              <div><span>To</span><b>{message.transferPreview.recipient_name}</b></div>
              <div><span>Amount</span><b>{message.transferPreview.currency === 'CNY' ? `¥${Number(message.transferPreview.amount).toLocaleString()}` : `${message.transferPreview.amount} ${message.transferPreview.currency}`}</b></div>
            </div>}
            {message.transferAction?.kind === 'confirm' && <>
              {message.transferAction.requiresMfa && <p className="transfer-mfa-hint">For this local demo, the simulated verification code is printed in the backend terminal. SMS delivery is not configured.</p>}
              <div className="transfer-actions">
                {message.transferAction.requiresMfa && <input aria-label="Verification code" inputMode="numeric" autoComplete="one-time-code" maxLength="6" placeholder="6-digit code" value={mfaCodes[message.id] || ''} onChange={(event) => setMfaCodes((current) => ({ ...current, [message.id]: event.target.value }))} />}
                <button type="button" disabled={sending || (message.transferAction.requiresMfa && !(mfaCodes[message.id] || '').trim())} onClick={() => confirmTransfer(message)}>Confirm transfer</button>
              </div>
            </>}
            {message.transferAction?.kind === 'approve' && <div className="transfer-actions"><button type="button" disabled={sending} onClick={() => approveTransfer(message)}>Approve and send</button></div>}
          </div>
        </div>
      })}
      {sending && <div className="chat-welcome assistant-message" role="status"><span className="message-time">FINN AI · THINKING</span><div className="welcome-bubble"><p>One moment…</p></div></div>}
    </div>
    <form className="chat-composer" onSubmit={submitMessage}><textarea rows="1" value={draft} onChange={updateDraft} placeholder="Ask FINN…" aria-label="Message FINN AI" disabled={sending}/><button type="submit" disabled={!draft.trim() || sending} aria-label="Send message"><Send size={17}/></button></form>
  </section>
}
