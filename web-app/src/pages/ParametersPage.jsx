import { ChevronLeft, ChevronRight, Languages, Moon, Sun } from 'lucide-react'

export default function ParametersPage({ onNotice, theme, onThemeChange, onBack }) {
  const ThemeIcon = theme === 'dark' ? Moon : Sun
  return <section className="parameters-screen">
    <header className="welcome parameters-welcome"><button className="parameters-back" onClick={onBack} aria-label="Back to Me"><ChevronLeft size={20}/><span>Me</span></button></header>
    <div className="me-menu-groups">
      <div className="me-menu-group">
        <button className="me-menu-row" onClick={()=>onThemeChange(theme==='dark'?'light':'dark')}><ThemeIcon className="me-menu-icon" size={18}/><span className="me-menu-label">Theme</span><span className="me-menu-value">{theme==='dark'?'Dark':'Light'}</span><ChevronRight className="me-menu-chevron" size={16}/></button>
        <button className="me-menu-row" onClick={()=>onNotice('Language selection will be available later.')}><Languages className="me-menu-icon" size={18}/><span className="me-menu-label">Language</span><span className="me-menu-value">English</span><ChevronRight className="me-menu-chevron" size={16}/></button>
      </div>
    </div>
  </section>
}
