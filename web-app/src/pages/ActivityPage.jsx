import { Activity as ActivityIcon } from 'lucide-react'

export default function ActivityPage() {
  return <section className="activity-page">
    <header className="welcome activity-welcome"><div><h1>Activity<span className="orange">.</span></h1><p className="subhead">Your transactions will appear here.</p></div></header>
    <section className="contacts-empty-state activity-empty-state"><div className="empty-illustration"><span className="empty-orbit orbit-one"/><span className="empty-orbit orbit-two"/><span className="empty-avatar"><ActivityIcon size={25}/></span></div><h2>No activity yet</h2><p className="empty-description">Connect an account to see your transactions.</p></section>
  </section>
}
