import { useEffect, useState } from 'react'
import { navigation } from './features/index.js'
import { showNotice } from './services/notifications.js'
import AppHeader from './components/layout/AppHeader.jsx'
import BottomNavigation from './components/layout/BottomNavigation.jsx'
import Toast from './components/common/Toast.jsx'
import HomePage from './pages/HomePage.jsx'
import ContactsPage from './pages/ContactsPage.jsx'
import CfoChatPage from './pages/CfoChatPage.jsx'
import MePage from './pages/MePage.jsx'
import ActivityPage from './pages/ActivityPage.jsx'
import ParametersPage from './pages/ParametersPage.jsx'
import AuthPage from './pages/AuthPage.jsx'
import { useAuth } from './context/AuthContext.jsx'

export default function App() {
  const { isAuthenticated, user, signOut } = useAuth()
  const [active, setActive] = useState(() => {
    const saved = sessionStorage.getItem('cashflow-active-screen')
    return ['home', 'contacts', 'cfo-ai', 'activity', 'me', 'parameters'].includes(saved) ? saved : 'home'
  })
  const [notice, setNotice] = useState('')
  const [theme, setTheme] = useState(() => localStorage.getItem('cashflow-theme') || 'dark')
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('cashflow-theme', theme)
  }, [theme])
  useEffect(() => {
    sessionStorage.setItem('cashflow-active-screen', active)
  }, [active])
  const notify = (message) => showNotice(setNotice, message)
  function navigate(id) {
    setActive(id)
    if (id === 'me') notify('Me area is ready for your team to build.')
    if (id === 'activity') notify('Activity history is ready to connect.')
  }

  if (!isAuthenticated) return <AuthPage />
  return <main className={`app-shell ${active === 'cfo-ai' ? 'chat-mode' : ''}`}>
    <AppHeader onHome={() => setActive('home')} onNotify={() => notify('You’re all caught up.')} />
    <div className="screen-panel" hidden={active !== 'home'}><HomePage onNavigate={navigate} onNotice={notify} /></div>
    <div className="screen-panel" hidden={active !== 'contacts'}><ContactsPage onNotice={notify} /></div>
    <div className="screen-panel" hidden={active !== 'cfo-ai'}><CfoChatPage isActive={active === 'cfo-ai'} onNotice={notify} /></div>
    <div className="screen-panel" hidden={active !== 'activity'}><ActivityPage onNotice={notify} /></div>
    <div className="screen-panel" hidden={active !== 'me'}><MePage onNotice={notify} onNavigate={navigate} user={user} onSignOut={signOut} /></div>
    <div className="screen-panel" hidden={active !== 'parameters'}><ParametersPage onNotice={notify} theme={theme} onThemeChange={setTheme} onBack={()=>setActive('me')} /></div>
    <BottomNavigation active={active === 'parameters' ? 'me' : active} onSelect={navigate} onNotify={() => notify('You’re all caught up.')} />
    <Toast message={notice} />
  </main>
}
