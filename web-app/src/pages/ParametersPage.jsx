import { ChevronLeft, ChevronRight, Languages, Moon, Sun } from 'lucide-react'
import { useLanguage } from '../context/LanguageContext.jsx'

export default function ParametersPage({ theme, onThemeChange, onBack }) {
  const { language, setLanguage, t } = useLanguage()
  const ThemeIcon = theme === 'dark' ? Moon : Sun
  return <section className="parameters-screen">
    <header className="welcome parameters-welcome"><button className="parameters-back" onClick={onBack} aria-label={t('Back to Me')}><ChevronLeft size={20}/><span>{t('Me')}</span></button></header>
    <div className="me-menu-groups">
      <div className="me-menu-group">
        <button className="me-menu-row" onClick={()=>onThemeChange(theme==='dark'?'light':'dark')}><ThemeIcon className="me-menu-icon" size={18}/><span className="me-menu-label">{t('Theme')}</span><span className="me-menu-value">{t(theme==='dark'?'Dark':'Light')}</span><ChevronRight className="me-menu-chevron" size={16}/></button>
        <button className="me-menu-row" onClick={()=>setLanguage(language==='en'?'zh':'en')}><Languages className="me-menu-icon" size={18}/><span className="me-menu-label">{t('Language')}</span><span className="me-menu-value">{t(language==='en'?'English':'Chinese')}</span><ChevronRight className="me-menu-chevron" size={16}/></button>
      </div>
    </div>
  </section>
}
