import { ChevronRight, FileText, Repeat2, Wallet, SlidersHorizontal, LogOut } from 'lucide-react'

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
  return <section className="me-screen">
    <button className="me-profile" onClick={() => onNotice('Profile details can be connected to your account later.')}>
      <span className="me-profile-avatar">{(user?.company_name || user?.email || 'C').slice(0, 1).toUpperCase()}</span>
      <span className="me-profile-copy"><b>{user?.company_name || 'Your business'}</b><small>{user?.email || user?.user_id}</small></span>
      <ChevronRight size={17}/>
    </button>
    <div className="me-menu-groups">{menuSections.map((section,index)=><div className="me-menu-group" key={index}>{section.map(({id,label,icon:Icon,value})=><button className="me-menu-row" key={id} onClick={()=>id==='parameters'?onNavigate('parameters'):onNotice(id==='currency'?'Chinese Yuan (CNY) is selected.':`${label} is ready to connect.`)}><Icon className="me-menu-icon" size={18}/><span className="me-menu-label">{label}</span>{value&&<span className="me-menu-value">{value}</span>}<ChevronRight className="me-menu-chevron" size={16}/></button>)}</div>)}<div className="me-menu-group"><button className="me-menu-row" onClick={onSignOut}><LogOut className="me-menu-icon" size={18}/><span className="me-menu-label">Sign out</span></button></div></div>
  </section>
}

