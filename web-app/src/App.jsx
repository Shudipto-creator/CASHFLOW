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
import BillsPage from './pages/BillsPage.jsx'
import SubscriptionsPage from './pages/SubscriptionsPage.jsx'
import AuthPage from './pages/AuthPage.jsx'
import { useAuth } from './context/AuthContext.jsx'
import { useLanguage } from './context/LanguageContext.jsx'
import { refreshDemoBankData } from './services/useDemoBankData.js'

export default function App() {
  const { isAuthenticated, user, signOut } = useAuth()
  const [active, setActive] = useState(() => {
    const saved = sessionStorage.getItem('cashflow-active-screen')
    return ['home', 'contacts', 'cfo-ai', 'activity', 'me', 'parameters', 'bills-analysis', 'subscriptions'].includes(saved) ? saved : 'home'
  })
  const [billflowReturnScreen, setBillflowReturnScreen] = useState('me')
  const [notice, setNotice] = useState('')
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('cashflow-theme')
    return saved === 'light' ? 'light' : 'dark'
  })
  const { t } = useLanguage()
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('cashflow-theme', theme)
  }, [theme])
  useEffect(() => {
    sessionStorage.setItem('cashflow-active-screen', active)
  }, [active])
  const notify = (message) => showNotice(setNotice, t(message))
  function changeTheme(nextTheme) {
    const next = nextTheme === 'light' ? 'light' : 'dark'
    localStorage.setItem('cashflow-theme', next)
    setTheme(next)
  }
  function handleSignOut() {
    setActive('home')
    sessionStorage.setItem('cashflow-active-screen', 'home')
    signOut()
  }
  function navigate(id) {
    if (id === 'bills-analysis' || id === 'subscriptions') setBillflowReturnScreen(active)
    setActive(id)
    refreshDemoBankData()
    if (id === 'activity') notify('Activity history is ready to connect.')
  }
  function returnFromBillflow() {
    navigate(billflowReturnScreen)
  }

  if (!isAuthenticated) return <AuthPage />
  return <main className={`app-shell ${active === 'cfo-ai' ? 'chat-mode' : ''}`}>
    <AppHeader onHome={() => navigate('home')} onNotify={() => notify('You’re all caught up.')} />
    <div className="screen-panel" hidden={active !== 'home'}><HomePage onNavigate={navigate} onNotice={notify} /></div>
    <div className="screen-panel" hidden={active !== 'contacts'}><ContactsPage onNotice={notify} /></div>
    <div className="screen-panel" hidden={active !== 'cfo-ai'}><CfoChatPage isActive={active === 'cfo-ai'} onNotice={notify} /></div>
    <div className="screen-panel" hidden={active !== 'activity'}><ActivityPage onNotice={notify} /></div>
    <div className="screen-panel" hidden={active !== 'me'}><MePage onNotice={notify} onNavigate={navigate} user={user} onSignOut={handleSignOut} /></div>
    <div className="screen-panel" hidden={active !== 'parameters'}><ParametersPage theme={theme} onThemeChange={changeTheme} onBack={()=>setActive('me')} /></div>
    <div className="screen-panel" hidden={active !== 'bills-analysis'}><BillsPage onBack={returnFromBillflow} backLabel={billflowReturnScreen === 'home' ? 'Home' : 'Me'} /></div>
    <div className="screen-panel" hidden={active !== 'subscriptions'}><SubscriptionsPage onBack={returnFromBillflow} backLabel={billflowReturnScreen === 'home' ? 'Home' : 'Me'} /></div>
    <BottomNavigation active={active === 'parameters' ? 'me' : active} onSelect={navigate} onNotify={() => notify('You’re all caught up.')} />
    <Toast message={notice} />
  </main>
}
