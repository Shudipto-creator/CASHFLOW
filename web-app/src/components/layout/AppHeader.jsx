import { Bell } from 'lucide-react'

export default function AppHeader({ onHome, onNotify }) {
  return <header className="topbar"><a className="brand" href="#home" onClick={onHome} aria-label="CASHFLOW home"><span className="brand-mark">C</span><span>CASHFLOW<span className="brand-dot">.</span></span></a><button className="icon-button notification" aria-label="Notifications" onClick={onNotify}><Bell size={19}/><i/></button></header>
}
