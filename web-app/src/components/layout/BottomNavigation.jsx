import { Bell } from 'lucide-react'
import { navigation } from '../../features/index.js'

export default function BottomNavigation({ active, onSelect, onNotify }) {
  return <>
    <aside className="desktop-sidebar">
      <a className="desktop-brand" href="#home" onClick={()=>onSelect('home')}><span className="brand-mark">C</span><span><b>C.A.S.H.F.L.O.W</b><small>AI CFO CONSOLE</small></span></a>
      <p className="desktop-nav-label">TOOLS</p>
      <nav className="desktop-nav" aria-label="Main navigation">{navigation.map(({id,label,icon:Icon})=><button key={id} className={active===id?'selected':''} onClick={()=>onSelect(id)}><Icon size={17}/><span>{label}</span></button>)}</nav>
      <button className="desktop-notification" onClick={onNotify}><Bell size={17}/><span>Notifications</span><i/></button>
    </aside>
    <nav className="bottom-nav" aria-label="Mobile navigation">{navigation.map(({id,label,icon:Icon})=><button key={id} className={active===id?'selected':''} onClick={()=>onSelect(id)}><Icon size={19}/><span>{label}</span></button>)}</nav>
  </>
}
