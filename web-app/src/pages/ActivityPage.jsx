import { Activity as ActivityIcon } from 'lucide-react'
import { accountRows, formatMoney, transactionDate, transactionRows, useDemoBankData } from '../services/useDemoBankData.js'
import { useLanguage } from '../context/LanguageContext.jsx'

export default function ActivityPage() {
  const { t, language } = useLanguage()
  const { data, loading, error } = useDemoBankData()
  const accounts = accountRows(data)
  const transactions = transactionRows(data)
  const currency = accounts[0]?.currency || 'CNY'

  return <section className="activity-page">
    <header className="welcome activity-welcome"><div><h1>{t('Activity')}<span className="orange">.</span></h1><p className="subhead">{t('Demo transactions from the banking sandbox.')}</p></div></header>
    {loading ? <section className="contacts-empty-state activity-empty-state"><div className="empty-illustration"><span className="empty-avatar"><ActivityIcon size={25}/></span></div><h2>{t('Loading activity')}</h2></section> : transactions.length ? <section className="demo-transaction-list activity-demo-list">{transactions.map((transaction) => <div className="demo-transaction" key={transaction.id}><span className={`transaction-icon ${Number(transaction.amount) >= 0 ? 'incoming' : ''}`}><ActivityIcon size={17}/></span><span className="transaction-copy"><b>{transaction.description || transaction.counterparty?.name || t('Transaction')}</b><small>{transactionDate(transaction, language)}</small></span><b className={`demo-amount ${Number(transaction.amount) >= 0 ? 'positive' : ''}`}>{formatMoney(transaction.amount, transaction.currency || currency, language)}</b></div>)}</section> : <section className="contacts-empty-state activity-empty-state"><div className="empty-illustration"><span className="empty-orbit orbit-one"/><span className="empty-orbit orbit-two"/><span className="empty-avatar"><ActivityIcon size={25}/></span></div><h2>{error || t('No activity yet')}</h2><p className="empty-description">{t('The demo banking service did not return transactions.')}</p></section>}
  </section>
}
