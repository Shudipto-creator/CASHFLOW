import { ArrowLeftRight, Bot, FileText, Send, Wallet, Activity } from 'lucide-react'

export default function HomePage({ onNavigate, onNotice }) {
  return <>
    <section className="home-intro"><h1 className="home-tagline">Your finances<span>.</span></h1><p className="home-subtagline">With a little more clarity</p></section>
    <section className="balance-card"><div className="balance-top"><div><p className="label">AVAILABLE BALANCE</p></div><span className="currency-label">CNY</span></div><p className="balance balance-empty">—</p><div className="balance-bottom"><span className="balance-note"><Wallet size={13}/> No account connected</span></div></section>
    <section className="scenario-section"><div className="section-heading"><div><p className="eyebrow">QUICK ACTIONS</p></div></div><div className="quick-actions"><button onClick={()=>onNavigate('cfo-ai')}><span className="action-icon orange-icon"><Bot size={19}/></span><b>Ask CFO AI</b></button><button onClick={()=>onNotice('Bill analysis flow is ready to connect.')}><span className="action-icon"><FileText size={19}/></span><b>Analyze bill</b></button><button onClick={()=>onNotice('Recurring payment view is ready to connect.')}><span className="action-icon"><ArrowLeftRight size={19}/></span><b>Subscriptions</b></button><button onClick={()=>onNavigate('contacts')}><span className="action-icon"><Send size={19}/></span><b>Contacts</b></button></div></section>
    <section className="activity-section"><div className="section-heading"><div><p className="eyebrow">LATEST MOVEMENT</p><h2>Recent activity</h2></div></div><div className="activity-empty-inline"><Activity size={18}/><span>No transactions to show yet</span></div></section>
  </>
}

