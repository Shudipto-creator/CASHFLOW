import { Bell } from 'lucide-react'
import { navigation } from '../../features/index.js'
import { useLanguage } from '../../context/LanguageContext.jsx'

export default function BottomNavigation({ active, onSelect, onNotify }) {
  const { t } = useLanguage()
  return <>
    <aside className="desktop-sidebar">
      <a className="desktop-brand" href="#home" onClick={()=>onSelect('home')} aria-label="FINN home"><span className="brand-mark">F</span><span><b>FINN</b><small>{t('AI BANKING ASSISTANT')}</small></span></a>
      <p className="desktop-nav-label">{t('TOOLS')}</p>
      <nav className="desktop-nav" aria-label={t('Main navigation')}>{navigation.map(({id,label,icon:Icon})=><button key={id} className={active===id?'selected':''} onClick={()=>onSelect(id)}><Icon size={17}/><span>{t(label)}</span></button>)}</nav>
      <button className="desktop-notification" onClick={onNotify}><Bell size={17}/><span>{t('Notifications')}</span><i/></button>
    </aside>
    <nav className="bottom-nav" aria-label={t('Mobile navigation')}>{navigation.map(({id,label,icon:Icon})=><button key={id} className={active===id?'selected':''} onClick={()=>onSelect(id)}><Icon size={19}/><span>{t(label)}</span></button>)}</nav>
  </>
}
