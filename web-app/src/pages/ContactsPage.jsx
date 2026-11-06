import { useCallback, useEffect, useState } from 'react'
import { Loader2, Plus, Search, Trash2, Users } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { useLanguage } from '../context/LanguageContext.jsx'
import { addContact, addContactByUserId, getContacts, previewContactByUserId, removeContact, searchContactCustomers } from '../services/api.js'

export default function ContactsPage() {
  const { token } = useAuth()
  const { t } = useLanguage()
  const [contacts, setContacts] = useState([])
  const [matches, setMatches] = useState([])
  const [query, setQuery] = useState('')
  const [userId, setUserId] = useState('')
  const [addFormOpen, setAddFormOpen] = useState(false)
  const [recipientPreview, setRecipientPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [addingByUserId, setAddingByUserId] = useState(false)
  const [lookingUpUserId, setLookingUpUserId] = useState(false)
  const [workingId, setWorkingId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const loadContacts = useCallback(async () => {
    setError('')
    try {
      const result = await getContacts(token)
      setContacts(result.items || [])
    } catch (loadError) {
      setError(loadError.message || t('Could not load contacts.'))
    } finally {
      setLoading(false)
    }
  }, [token, t])

  useEffect(() => {
    loadContacts()
  }, [loadContacts])

  async function searchCustomers(event) {
    event.preventDefault()
    const name = query.trim()
    if (name.length < 2) {
      setMatches([])
      setError(t('Enter at least 2 characters to search.'))
      return
    }
    setSearching(true)
    setError('')
    setNotice('')
    try {
      const result = await searchContactCustomers(name, token)
      setMatches(result.items || [])
    } catch (searchError) {
      setError(searchError.message || t('Could not search FINN customers.'))
    } finally {
      setSearching(false)
    }
  }

  async function previewRecipientByUserId(event) {
    event.preventDefault()
    const recipientId = userId.trim()
    if (!recipientId) {
      setError(t('Enter the recipient FINN ID.'))
      return
    }

    setLookingUpUserId(true)
    setError('')
    setNotice('')
    try {
      const result = await previewContactByUserId(recipientId, token)
      setRecipientPreview(result)
    } catch (previewError) {
      setError(previewError.message || t('Could not find that FINN account.'))
    } finally {
      setLookingUpUserId(false)
    }
  }

  async function confirmAddRecipient() {
    if (!recipientPreview) return
    setAddingByUserId(true)
    setError('')
    setNotice('')
    try {
      await addContactByUserId(recipientPreview.user_id, token)
      setNotice(t('Contact saved. You can now transfer to them by name in FINN chat.'))
      setUserId('')
      setRecipientPreview(null)
      setAddFormOpen(false)
      await loadContacts()
    } catch (saveError) {
      setError(saveError.message || t('Could not save this contact.'))
    } finally {
      setAddingByUserId(false)
    }
  }

  async function saveContact(candidate) {
    setWorkingId(candidate.customer_id)
    setError('')
    setNotice('')
    try {
      await addContact(candidate.customer_id, token)
      setNotice(t('Contact saved. You can now transfer to them by name in FINN chat.'))
      setMatches((current) => current.filter((item) => item.customer_id !== candidate.customer_id))
      await loadContacts()
    } catch (saveError) {
      setError(saveError.message || t('Could not save this contact.'))
    } finally {
      setWorkingId('')
    }
  }

  async function deleteContact(contact) {
    setWorkingId(contact.customer_id)
    setError('')
    setNotice('')
    try {
      await removeContact(contact.customer_id, token)
      setContacts((current) => current.filter((item) => item.customer_id !== contact.customer_id))
      setNotice(t('Contact removed.'))
    } catch (removeError) {
      setError(removeError.message || t('Could not remove this contact.'))
    } finally {
      setWorkingId('')
    }
  }

  return <>
    <section className="welcome contacts-welcome"><div><h1>{t('Contacts')}<span className="orange">.</span></h1><p className="subhead">{t('Save FINNDB customers as recipients for name-based transfers.')}</p></div></section>
    <section className="contacts-page">
      <button className="contact-search-button add-recipient-toggle" type="button" onClick={() => {
        setAddFormOpen((open) => !open)
        setRecipientPreview(null)
        setUserId('')
        setError('')
        setNotice('')
      }}>
        <Plus size={16}/><span>{t('Add contact (recipient)')}</span>
      </button>

      {addFormOpen && <div className="recipient-modal-backdrop" onMouseDown={(event) => {
        if (event.target === event.currentTarget && !addingByUserId && !lookingUpUserId) {
          setAddFormOpen(false)
          setRecipientPreview(null)
          setError('')
        }
      }}>
        <section className="recipient-modal" role="dialog" aria-modal="true" aria-labelledby="recipient-modal-title">
          <div className="recipient-modal-heading">
            <h2 id="recipient-modal-title">{t('Add contact (recipient)')}</h2>
            <button type="button" className="recipient-modal-close" onClick={() => {
              setAddFormOpen(false)
              setRecipientPreview(null)
              setError('')
            }} aria-label={t('Close')} disabled={addingByUserId || lookingUpUserId}>×</button>
          </div>
          {!recipientPreview ? <form className="recipient-modal-form" onSubmit={previewRecipientByUserId}>
            <label className="recipient-id-label" htmlFor="recipient-user-id">{t('Recipient FINN ID')}</label>
            <input
              id="recipient-user-id"
              className="recipient-id-input"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              placeholder={t('Enter recipient FINN ID')}
              autoComplete="off"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck="false"
              autoFocus
            />
            {error && !addFormOpen && <p className="contacts-feedback contacts-error" role="alert">{error}</p>}
            <button className="contact-add-button recipient-modal-primary" type="submit" disabled={lookingUpUserId}>
              {lookingUpUserId ? <Loader2 className="spin" size={16}/> : null}
              <span>{t('OK')}</span>
            </button>
          </form> : <div className="recipient-modal-confirm">
            <p>{t('Check that this is the right recipient:')}</p>
            <div className="recipient-preview-field"><span>{t('FINN ID')}</span><code>{recipientPreview.user_id}</code></div>
            <div className="recipient-preview-field"><span>{t('Name')}</span><b>{recipientPreview.name}</b></div>
            {error && <p className="contacts-feedback contacts-error" role="alert">{error}</p>}
            <div className="recipient-modal-actions">
              <button type="button" className="recipient-modal-secondary" onClick={() => {
                setRecipientPreview(null)
                setError('')
              }} disabled={addingByUserId}>{t('Back')}</button>
              <button type="button" className="contact-add-button" onClick={confirmAddRecipient} disabled={addingByUserId}>
                {addingByUserId ? <Loader2 className="spin" size={16}/> : <Plus size={16}/>}
                <span>{t('Confirm')}</span>
              </button>
            </div>
          </div>}
        </section>
      </div>}

      <form className="contact-search-form" onSubmit={searchCustomers}>
        <label className="contact-search"><Search size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('Search FINNDB customers by name')} aria-label={t('Search FINNDB customers by name')}/></label>
        <button className="contact-search-button" type="submit" disabled={searching}>{searching ? <Loader2 className="spin" size={16}/> : <Search size={16}/>}<span>{t('Search')}</span></button>
      </form>

      {error && <p className="contacts-feedback contacts-error" role="alert">{error}</p>}
      {notice && <p className="contacts-feedback" role="status">{notice}</p>}

      {!!matches.length && <section className="contacts-card">
        <div className="section-heading"><div><p className="eyebrow">{t('SEARCH RESULTS')}</p><h2>{t('FINNDB customers')}</h2></div></div>
        <div className="saved-contact-list">{matches.map((candidate) => <article className="saved-contact-row" key={candidate.customer_id}>
          <span className="saved-contact-avatar">{candidate.name.slice(0, 1).toUpperCase()}</span>
          <div className="saved-contact-copy"><b>{candidate.name}</b><small>{t('FINNDB customer')}</small></div>
          <button className="contact-add-button" disabled={workingId === candidate.customer_id} onClick={() => saveContact(candidate)}>{workingId === candidate.customer_id ? <Loader2 className="spin" size={16}/> : <Plus size={16}/>}<span>{t('Add')}</span></button>
        </article>)}</div>
      </section>}
      {!searching && query.trim().length >= 2 && !matches.length && !error && <div className="contacts-empty-inline"><Users size={18}/><span>{t('No matching FINNDB customers found.')}</span></div>}

      <section className="contacts-card">
        <div className="section-heading"><div><p className="eyebrow">{t('SAVED RECIPIENTS')}</p><h2>{t('Your contacts')}</h2></div><span className="billflow-count">{contacts.length}</span></div>
        {loading ? <div className="contacts-empty-inline"><Loader2 className="spin" size={18}/><span>{t('Loading contacts…')}</span></div> : contacts.length ? <div className="saved-contact-list">{contacts.map((contact) => <article className="saved-contact-row" key={contact.customer_id}>
          <span className="saved-contact-avatar">{contact.name.slice(0, 1).toUpperCase()}</span>
          <div className="saved-contact-copy"><b>{contact.name}</b><small>{t('FINNDB customer · ready for transfer')}</small></div>
          <button className="contact-remove-button" disabled={workingId === contact.customer_id} onClick={() => deleteContact(contact)} aria-label={`${t('Remove')} ${contact.name}`}>{workingId === contact.customer_id ? <Loader2 className="spin" size={16}/> : <Trash2 size={16}/>}</button>
        </article>)}</div> : <div className="contacts-empty-inline"><Users size={18}/><span>{t('No contacts yet. Search for another FINNDB customer by name to add them.')}</span></div>}
      </section>
      <p className="contacts-transfer-note">{t('To send money, open FINN chat and mention a saved recipient by name.')}</p>
    </section>
  </>
}
