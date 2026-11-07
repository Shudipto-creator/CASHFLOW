import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, FileSearch, Repeat2, Send, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { useLanguage } from '../context/LanguageContext.jsx'
import { approveSandboxTransfer, chatWithCfoAi, getCfoConversation, getContacts } from '../services/api.js'
import { refreshDemoBankData } from '../services/useDemoBankData.js'

const suggestions = [
  { label: 'Transfer to @', prompt: 'I’d like to make a transfer. Help me choose a contact and review the details.', icon: ArrowUpRight },
  { label: 'Analyze my bills', prompt: 'Analyze my recent bills and point out anything unusual.', icon: FileSearch },
  { label: 'Cancel unused subscriptions', prompt: 'Help me find subscriptions I may not be using. Ask me before taking any action.', icon: Repeat2 },
]

function formatMessageTime(timestamp, language) {
  return new Intl.DateTimeFormat(language === 'zh' ? 'zh-CN' : 'en', { hour: 'numeric', minute: '2-digit' }).format(new Date(timestamp))
}

function loadChatHistory(storageKey) {
  if (!storageKey) return []
  try {
    const saved = localStorage.getItem(storageKey)
    if (!saved) return []
    const parsed = JSON.parse(saved)
    if (!Array.isArray(parsed)) throw new TypeError('Saved FINN chat history is not a message list.')
    return parsed
      .filter((message) =>
        message &&
        typeof message.id === 'string' &&
        ['user', 'assistant'].includes(message.role) &&
        typeof message.text === 'string' &&
        Number.isFinite(message.timestamp)
      )
      .map((message) => ({
        id: message.id,
        role: message.role,
        text: message.text,
        timestamp: message.timestamp,
        transferPreview: message.transferPreview || null,
        transferActionExpired: Boolean(message.transferAction || message.transferActionExpired),
      }))
  } catch (error) {
    console.error('Could not restore FINN chat history.', error)
    return []
  }
}

function saveChatHistory(storageKey, messages) {
  if (!storageKey) return
  try {
    const history = messages.map(({ transferAction, ...message }) => message)
    localStorage.setItem(storageKey, JSON.stringify(history))
  } catch (error) {
    console.error('Could not save FINN chat history.', error)
  }
}

function loadConversationId(storageKey) {
  if (!storageKey) return null
  try {
    return localStorage.getItem(storageKey) || null
  } catch {
    return null
  }
}

function saveConversationId(storageKey, conversationId) {
  if (!storageKey || !conversationId) return
  try {
    localStorage.setItem(storageKey, conversationId)
  } catch (error) {
    console.error('Could not save the FINN conversation id.', error)
  }
}

function serverMessageToUi(message) {
  const timestamp = new Date(message.created_at).getTime()
  return {
    id: `server-${message.id}`,
    role: message.role,
    text: message.content,
    timestamp: Number.isFinite(timestamp) ? timestamp : Date.now(),
    transferPreview: null,
    transferActionExpired: false,
  }
}

export default function CfoChatPage({ onNotice, isActive = true }) {
  const { token, user } = useAuth()
  const { t, language } = useLanguage()
  const userId = user?.user_id || user?.id || user?.email
  const historyKey = userId ? `finn-chat-history:${encodeURIComponent(userId)}` : null
  const conversationKey = userId ? `finn-chat-conversation:${encodeURIComponent(userId)}` : null
  const [messages, setMessages] = useState(() => loadChatHistory(historyKey))
  const [historyOwner, setHistoryOwner] = useState(historyKey)
  const [conversationId, setConversationId] = useState(() => loadConversationId(conversationKey))
  const [conversationOwner, setConversationOwner] = useState(conversationKey)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [mfaCodes, setMfaCodes] = useState({})
  const [recipients, setRecipients] = useState([])
  const [recipientLoadError, setRecipientLoadError] = useState('')
  const [mentionQuery, setMentionQuery] = useState(null)
  const [selectedRecipient, setSelectedRecipient] = useState(null)
  const threadRef = useRef(null)
  const messagesRef = useRef(messages)
  const [welcomeTime] = useState(() => Date.now())

  useEffect(() => {
    if (!isActive || !token) return undefined
    let active = true
    getContacts(token)
      .then((result) => {
        if (active) {
          setRecipients(result.items || [])
          setRecipientLoadError('')
        }
      })
      .catch((error) => {
        if (active) setRecipientLoadError(error.message || t('Could not load contacts.'))
      })
    return () => {
      active = false
    }
  }, [isActive, token, t])

  useEffect(() => {
    if (historyOwner === historyKey) return
    setHistoryOwner(historyKey)
    setMessages(loadChatHistory(historyKey))
    setMfaCodes({})
  }, [historyKey, historyOwner])

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  useEffect(() => {
    if (conversationOwner === conversationKey) return
    setConversationOwner(conversationKey)
    setConversationId(loadConversationId(conversationKey))
  }, [conversationKey, conversationOwner])

  // The backend keeps the durable transcript so the model sees earlier turns.
  // Local storage stays the offline fallback and keeps pending transfer actions.
  useEffect(() => {
    if (!isActive || !token) return undefined
    let active = true
    getCfoConversation(token, conversationId)
      .then((result) => {
        if (!active || !result) return
        if (result.conversation_id && result.conversation_id !== conversationId) {
          setConversationId(result.conversation_id)
          saveConversationId(conversationKey, result.conversation_id)
        }
        if (!messagesRef.current.length && Array.isArray(result.messages) && result.messages.length) {
          setMessages(result.messages.map(serverMessageToUi))
        }
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [isActive, token, conversationId, conversationKey])

  useEffect(() => {
    if (historyOwner === historyKey) saveChatHistory(historyKey, messages)
  }, [historyKey, historyOwner, messages])

  useEffect(() => {
    if (isActive) threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, isActive])

  function startPrompt(prompt) {
    setDraft(prompt)
    setMentionQuery(null)
    setSelectedRecipient(null)
    const input = document.querySelector('.chat-composer textarea')
    if (input) {
      input.style.height = 'auto'
      input.style.height = `${Math.min(input.scrollHeight, 112)}px`
      input.focus()
    }
  }

  function rememberConversation(result) {
    if (!result?.conversation_id) return
    setConversationId(result.conversation_id)
    saveConversationId(conversationKey, result.conversation_id)
  }

  function assistantMessage(result, originalText, recipientCustomerId = null) {
    const execution = result.execution || {}
    const isTransfer = result.operation_id === 'prepare-transfer' && execution.transfer_preview
    let transferAction = null
    if (isTransfer && execution.needs_approval && execution.intent_id && execution.approval_id) {
      transferAction = { kind: 'approve', intentId: execution.intent_id, approvalId: execution.approval_id }
    } else if (isTransfer && ['CONFIRMATION_REQUIRED', 'MFA_REQUIRED'].includes(execution.code)) {
      transferAction = {
        kind: 'confirm', originalText,
        recipientCustomerId,
        requiresMfa: execution.code === 'MFA_REQUIRED' || execution.needs_mfa,
        challengeId: execution.mfa_challenge_id,
        confirmationId: execution.confirmation_id,
      }
    }
    return {
      id: `${Date.now()}-assistant`, role: 'assistant', text: t(result.message),
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
        ...(conversationId ? { conversation_id: conversationId } : {}),
        ...(message.transferAction.recipientCustomerId ? { recipient_customer_id: message.transferAction.recipientCustomerId } : {}),
        ...(message.transferAction.confirmationId ? { confirmation_id: message.transferAction.confirmationId } : {}),
        ...(message.transferAction.requiresMfa ? {
          mfa_challenge_id: message.transferAction.challengeId,
          mfa_code: code,
        } : {}),
      })
      rememberConversation(result)
      setMessages((current) => [...current, assistantMessage(
        result,
        message.transferAction.originalText,
        message.transferAction.recipientCustomerId,
      )])
    } catch (error) {
      setMessages((current) => [...current, { id: `${Date.now()}-error`, role: 'assistant',       text: error.message || t('I could not prepare that transfer.'), timestamp: Date.now() }])
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
        text: t(result.message || (result.ok ? 'Transfer completed successfully.' : 'The transfer was not completed.')),
        timestamp: Date.now(), transferPreview: message.transferPreview,
      }])
      if (result.ok) refreshDemoBankData()
    } catch (error) {
      setMessages((current) => [...current, { id: `${Date.now()}-error`, role: 'assistant',       text: error.message || t('I could not complete that transfer.'), timestamp: Date.now() }])
    } finally {
      setSending(false)
    }
  }

  async function submitMessage(event) {
    event.preventDefault()
    const message = draft.trim()
    if (!message || sending) return
    const leadingWhitespace = draft.length - draft.trimStart().length
    const recipientCustomerId = selectedRecipient &&
      draft.slice(selectedRecipient.start, selectedRecipient.end) === selectedRecipient.label
      && message.slice(selectedRecipient.start - leadingWhitespace, selectedRecipient.end - leadingWhitespace) === selectedRecipient.label
      ? selectedRecipient.customer_id
      : null
    setMessages((current) => [...current, { id: `${Date.now()}-user`, role: 'user', text: message, timestamp: Date.now() }])
    setDraft('')
    setSelectedRecipient(null)
    setMentionQuery(null)
    const input = event.currentTarget.querySelector('textarea')
    if (input) input.style.height = '38px'
    setSending(true)
    try {
      const result = await chatWithCfoAi(message, token, {
        ...(recipientCustomerId ? { recipient_customer_id: recipientCustomerId } : {}),
        ...(conversationId ? { conversation_id: conversationId } : {}),
      })
      rememberConversation(result)
      setMessages((current) => [...current, assistantMessage(result, message, recipientCustomerId)])
    } catch (error) {
      setMessages((current) => [...current, {
        id: `${Date.now()}-error`,
        role: 'assistant',
        text: error.message || t('I could not reach FINN AI. Please try again.'),
        timestamp: Date.now(),
      }])
    } finally {
      setSending(false)
    }
  }

  function updateDraft(event) {
    const value = event.target.value
    const cursor = event.target.selectionStart
    setDraft(value)
    event.target.style.height = 'auto'
    event.target.style.height = `${Math.min(event.target.scrollHeight, 112)}px`
    const selected = selectedRecipient &&
      value.slice(selectedRecipient.start, selectedRecipient.end) === selectedRecipient.label
    if (!selected) setSelectedRecipient(null)

    const atIndex = value.lastIndexOf('@', cursor - 1)
    const hasMentionBoundary = atIndex >= 0 && (atIndex === 0 || /\s/.test(value[atIndex - 1]))
    const query = hasMentionBoundary ? value.slice(atIndex + 1, cursor) : ''
    const nextMention = hasMentionBoundary && !/[,\n]/.test(query)
      ? { start: atIndex, query }
      : null
    setMentionQuery(
      selected && nextMention?.start === selectedRecipient.start &&
        nextMention.query.startsWith(selectedRecipient.label.slice(1))
        ? null
        : nextMention,
    )
  }

  function selectRecipient(recipient) {
    if (!mentionQuery) return
    const label = `@${recipient.name}`
    const nextDraft = `${draft.slice(0, mentionQuery.start)}${label}${draft.slice(
      mentionQuery.start + mentionQuery.query.length + 1,
    )}`
    const start = mentionQuery.start
    const end = start + label.length
    setDraft(nextDraft)
    setSelectedRecipient({ customer_id: recipient.customer_id, label, start, end })
    setMentionQuery(null)
    requestAnimationFrame(() => {
      const input = document.querySelector('.chat-composer textarea')
      if (input) {
        input.focus()
        input.setSelectionRange(end, end)
      }
    })
  }

  const mentionMatches = mentionQuery
    ? recipients.filter((recipient) =>
        recipient.name.toLocaleLowerCase().startsWith(mentionQuery.query.trim().toLocaleLowerCase())
      )
    : []

  return <section className="chat-page">
    <div className="chat-thread" ref={threadRef}>
      <div className="chat-thread-content">
      <div className="suggestion-intro"><Sparkles size={14}/><span>{t('HERE ARE A FEW THINGS I CAN HELP WITH')}</span></div>
      <div className="chat-suggestions">{suggestions.map(({label,prompt,icon:Icon})=><button className="suggestion-card" key={label} onClick={()=>startPrompt(t(prompt))}><span><Icon size={17}/></span><b>{t(label)}</b><i>↗</i></button>)}</div>
      <div className="chat-welcome"><time className="message-time" dateTime={new Date(welcomeTime).toISOString()}>FINN AI · {formatMessageTime(welcomeTime, language)}</time><div className="welcome-bubble"><p>{t('Hi there, I’m FINN, your financial navigator. Tell me what you need and I’ll help you with it. I’ll always ask before doing anything risky.')}</p></div></div>
      {messages.map((message) => {
        if (message.role === 'user') return <div className="user-message" key={message.id}><time className="message-time user-message-time" dateTime={new Date(message.timestamp).toISOString()}>{formatMessageTime(message.timestamp, language)}</time><span>{message.text}</span></div>
        return <div className="chat-welcome assistant-message" key={message.id}>
          <time className="message-time" dateTime={new Date(message.timestamp).toISOString()}>FINN AI · {formatMessageTime(message.timestamp, language)}</time>
          <div className="welcome-bubble">
            <p>{message.text}</p>
            {message.transferActionExpired && <p className="transfer-mfa-hint">{t('This pending transfer step expired after refreshing. Please start the transfer again.')}</p>}
            {message.transferPreview && <div className="transfer-preview">
              <div><span>{t('From')}</span><b>{message.transferPreview.source_account_name}</b></div>
              <div><span>{t('To')}</span><b>{message.transferPreview.recipient_name}</b></div>
              <div><span>{t('Amount')}</span><b>{message.transferPreview.currency === 'CNY' ? `¥${Number(message.transferPreview.amount).toLocaleString(language === 'zh' ? 'zh-CN' : 'en')}` : `${message.transferPreview.amount} ${message.transferPreview.currency}`}</b></div>
            </div>}
            {message.transferAction?.kind === 'confirm' && <>
              {message.transferAction.requiresMfa && <p className="transfer-mfa-hint">{t('For this local demo, the simulated verification code is printed in the backend terminal. SMS delivery is not configured.')}</p>}
              <div className="transfer-actions">
                {message.transferAction.requiresMfa && <input aria-label={t('Verification code')} inputMode="numeric" autoComplete="one-time-code" maxLength="6" placeholder={t('6-digit code')} value={mfaCodes[message.id] || ''} onChange={(event) => setMfaCodes((current) => ({ ...current, [message.id]: event.target.value }))} />}
                <button type="button" disabled={sending || (message.transferAction.requiresMfa && !(mfaCodes[message.id] || '').trim())} onClick={() => confirmTransfer(message)}>{t('Confirm transfer')}</button>
              </div>
            </>}
            {message.transferAction?.kind === 'approve' && <div className="transfer-actions"><button type="button" disabled={sending} onClick={() => approveTransfer(message)}>{t('Approve and send')}</button></div>}
          </div>
        </div>
      })}
      {sending && <div className="chat-welcome assistant-message" role="status"><span className="message-time">FINN AI · {t('THINKING')}</span><div className="welcome-bubble"><p>{t('One moment…')}</p></div></div>}
      </div>
    </div>
    <form className="chat-composer" onSubmit={submitMessage}>
      {mentionQuery && <div className="chat-mention-menu" role="listbox" aria-label={t('Saved recipients')}>
        {recipientLoadError
          ? <p className="chat-mention-empty">{recipientLoadError}</p>
          : mentionMatches.length
            ? mentionMatches.slice(0, 8).map((recipient) => <button
                type="button"
                className="chat-mention-option"
                key={recipient.customer_id}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectRecipient(recipient)}
                role="option"
              >
                <span className="chat-mention-avatar">{recipient.name.slice(0, 1).toUpperCase()}</span>
                <span className="chat-mention-copy"><b>@{recipient.name}</b><small>{recipient.customer_id.slice(-6)}</small></span>
              </button>)
            : <p className="chat-mention-empty">{t(recipients.length ? 'No saved recipient matches this name.' : 'Save a recipient in Contacts to mention them here.')}</p>}
      </div>}
      <textarea rows="1" value={draft} onChange={updateDraft} placeholder={t('Message FINN… Type @ to tag a saved recipient')} aria-label="Message FINN AI" disabled={sending}/>
      <button type="submit" disabled={!draft.trim() || sending} aria-label="Send message"><Send size={17}/></button>
    </form>
  </section>
}
