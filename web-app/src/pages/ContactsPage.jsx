import { Plus, Users } from 'lucide-react'

export default function ContactsPage({ onNotice }) {
  return <>
    <section className="welcome contacts-welcome"><div><h1>Contacts<span className="orange">.</span></h1><p className="subhead">Your saved contacts will appear here.</p></div></section>
    <section className="contacts-empty-state"><div className="empty-illustration"><span className="empty-orbit orbit-one"/><span className="empty-orbit orbit-two"/><span className="empty-avatar"><Users size={29}/></span></div><h2>No contacts yet</h2><button className="empty-cta" onClick={() => onNotice('Contact management will be added later.')}><Plus size={16}/>Add contact</button></section>
  </>
}
