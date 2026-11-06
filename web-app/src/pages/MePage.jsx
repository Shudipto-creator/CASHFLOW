import { ChevronRight, Copy, FileText, Repeat2, Wallet, SlidersHorizontal, LogOut } from 'lucide-react'
import { useLanguage } from '../context/LanguageContext.jsx'

const menuSections = [
  [
    { id: 'bills-analysis', label: 'Bills', icon: FileText },
    { id: 'subscriptions', label: 'Subscriptions', icon: Repeat2 },
  ],
  [
    { id: 'currency', label: 'Display currency', icon: Wallet, value: 'CNY' },
  ],
  [
    { id: 'parameters', label: 'Parameters', icon: SlidersHorizontal },
  ],
]

export default function MePage({ onNotice, onNavigate, user, onSignOut }) {
  const { t } = useLanguage()

  function copyUserIdWithFallback() {
    const field = document.createElement('textarea')
    field.value = user.user_id
    field.setAttribute('readonly', '')
    field.setAttribute('aria-hidden', 'true')
    field.style.position = 'fixed'
    field.style.top = '0'
    field.style.left = '0'
    field.style.width = '1px'
    field.style.height = '1px'
    field.style.padding = '0'
    field.style.border = '0'
    field.style.opacity = '0'
    field.style.fontSize = '16px'
    document.body.appendChild(field)
    field.focus()
    field.select()
    field.setSelectionRange(0, field.value.length)

    try {
      return document.execCommand('copy')
    } finally {
      field.remove()
    }
  }

  async function copyUserId() {
    if (!user?.user_id) return

    try {
      if (navigator.clipboard?.writeText) {
        try {
          await navigator.clipboard.writeText(user.user_id)
          onNotice(t('FINN ID copied.'))
          return
        } catch {
          // Mobile browsers may expose the Clipboard API but reject it outside a secure context.
        }
      }
      if (!copyUserIdWithFallback()) throw new Error('Clipboard copy was rejected.')
      onNotice(t('FINN ID copied.'))
    } catch {
      onNotice(t('Could not copy your FINN ID.'))
    }
  }

  return <section className="me-screen">
    <button className="me-profile" onClick={() => onNotice(t('Profile details can be connected to your account later.'))}>
      <span className="me-profile-avatar">{(user?.company_name || user?.email || 'C').slice(0, 1).toUpperCase()}</span>
      <span className="me-profile-copy"><b>{user?.company_name || t('Your business')}</b><small>{user?.email || user?.user_id}</small></span>
      <ChevronRight size={17}/>
    </button>
    {user?.user_id && <div className="me-user-id">
      <div className="me-user-id-copy"><span>{t('Your FINN ID')}</span><code>{user.user_id}</code></div>
      <button className="me-user-id-copy-button" type="button" onClick={copyUserId} aria-label={t('Copy FINN ID')} title={t('Copy FINN ID')}>
        <Copy size={16}/>
      </button>
    </div>}
    <div className="me-menu-groups">{menuSections.map((section,index)=><div className="me-menu-group" key={index}>{section.map(({id,label,icon:Icon,value})=><button className="me-menu-row" key={id} onClick={()=>['parameters','bills-analysis','subscriptions'].includes(id)?onNavigate(id):onNotice(t(id==='currency'?'Chinese Yuan (CNY) is selected.':`${label} is ready to connect.`))}><Icon className="me-menu-icon" size={18}/><span className="me-menu-label">{t(label)}</span>{value&&<span className="me-menu-value">{value}</span>}<ChevronRight className="me-menu-chevron" size={16}/></button>)}</div>)}<div className="me-menu-group"><button className="me-menu-row" onClick={onSignOut}><LogOut className="me-menu-icon" size={18}/><span className="me-menu-label">{t('Sign out')}</span></button></div></div>
  </section>
}
