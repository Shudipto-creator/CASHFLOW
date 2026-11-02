import { Bell } from 'lucide-react'

export default function AppHeader({ onHome, onNotify }) {
  return <header className="topbar"><a className="brand" href="#home" onClick={onHome} aria-label="FINN home"><span className="brand-mark">F</span><span>FINN</span></a><button className="icon-button notification" aria-label="Notifications" onClick={onNotify}><Bell size={19}/><i/></button></header>
}
