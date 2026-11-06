import { ArrowLeftRight, Bot, FileText, Send, Wallet, Activity, ArrowDownLeft, ArrowUpRight } from 'lucide-react'
import { accountRows, currencyLabel, formatMoney, transactionDate, transactionRows, useDemoBankData } from '../services/useDemoBankData.js'
import { useLanguage } from '../context/LanguageContext.jsx'

export default function HomePage({ onNavigate, onNotice }) {
  const { t, language } = useLanguage()
  const { data, loading, error } = useDemoBankData()
  const accounts = accountRows(data)
  const transactions = transactionRows(data)
  const primaryAccount = accounts.find((account) => account.accountType !== 'Credit') || accounts[0]
  const currency = primaryAccount?.currency || 'CNY'
  const rawAccountType = primaryAccount?.product || (primaryAccount?.accountType !== 'Other' ? primaryAccount?.accountType : '')
  const accountType = rawAccountType ? String(rawAccountType).replaceAll('_', ' ') : ''
  const accountIsActive = ['active', 'enabled'].includes(String(primaryAccount?.status || '').toLowerCase())

  return <>
    <section className="home-intro"><h1 className="home-tagline">{t('Your finances')}<span>.</span></h1><p className="home-subtagline">{t('With a little more clarity')}</p></section>
    <section className="balance-card"><div className="balance-top"><div><p className="label">{t('AVAILABLE BALANCE')}</p></div><span className="currency-label">{currencyLabel(currency)}</span></div><p className="balance">{loading ? t('Loading…') : primaryAccount ? formatMoney(primaryAccount.availableBalance ?? primaryAccount.balance, currency, language) : '—'}</p><div className="balance-bottom"><span className="balance-note"><Wallet size={13}/> {error ? t('Bank unavailable') : primaryAccount ? (t(accountType) || primaryAccount.id || t('Account')) : t('No account available')}</span>{accountIsActive&&<span className="active-status"><i/>{t('Active')}</span>}</div></section>
    <section className="scenario-section"><div className="section-heading"><div><p className="eyebrow">{t('QUICK ACTIONS')}</p></div></div><div className="quick-actions"><button onClick={()=>onNavigate('cfo-ai')}><span className="action-icon orange-icon"><Bot size={19}/></span><b>{t('Ask FINN')}</b></button><button onClick={()=>onNavigate('bills-analysis')}><span className="action-icon"><FileText size={19}/></span><b>{t('Analyze bill')}</b></button><button onClick={()=>onNavigate('subscriptions')}><span className="action-icon"><ArrowLeftRight size={19}/></span><b>{t('Subscriptions')}</b></button><button onClick={()=>onNavigate('contacts')}><span className="action-icon"><Send size={19}/></span><b>{t('Contacts')}</b></button></div></section>
    <section className="activity-section"><div className="section-heading"><div><p className="eyebrow">{t('LATEST MOVEMENT')}</p><h2>{t('Recent activity')}</h2></div></div>{loading ? <div className="activity-empty-inline"><Activity size={18}/><span>{t('Loading activity…')}</span></div> : transactions.length ? <div className="demo-transaction-list">{transactions.slice(0, 3).map((transaction) => <div className="demo-transaction" key={transaction.id}><span className={`transaction-icon ${Number(transaction.amount) >= 0 ? 'incoming' : ''}`}>{Number(transaction.amount) >= 0 ? <ArrowDownLeft size={17}/> : <ArrowUpRight size={17}/>}</span><span className="transaction-copy"><b>{transaction.description || transaction.counterparty?.name || t('Transaction')}</b><small>{transactionDate(transaction, language)}</small></span><b className={`demo-amount ${Number(transaction.amount) >= 0 ? 'positive' : ''}`}>{formatMoney(transaction.amount, transaction.currency || currency, language)}</b></div>)}</div> : <div className="activity-empty-inline"><Activity size={18}/><span>{error || t('No demo transactions available')}</span></div>}</section>
  </>
}
