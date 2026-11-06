import { ChevronLeft, FileText } from 'lucide-react'
import { useLanguage } from '../context/LanguageContext.jsx'
import { transactionDate, transactionRows, useDemoBankData } from '../services/useDemoBankData.js'

function money(value, language) {
  return `¥${new Intl.NumberFormat(language === 'zh' ? 'zh-CN' : 'en', {
    maximumFractionDigits: 2,
  }).format(Number(value) || 0)}`
}

export default function BillsPage({ onBack, backLabel = 'Me' }) {
  const { t, language } = useLanguage()
  const { data, loading, error } = useDemoBankData()
  const transactions = transactionRows(data)

  const spending = transactions.reduce((total, transaction) => {
    const amount = Number(transaction.amount)
    return Number.isFinite(amount) && amount < 0 ? total + Math.abs(amount) : total
  }, 0)
  const income = transactions.reduce((total, transaction) => {
    const amount = Number(transaction.amount)
    return Number.isFinite(amount) && amount > 0 ? total + amount : total
  }, 0)

  return <section className="billflow-page">
    <header className="welcome billflow-welcome">
      <button className="parameters-back" onClick={onBack} aria-label={t(`Back to ${backLabel}`)}><ChevronLeft size={20}/><span>{t(backLabel)}</span></button>
      <div><h1>{t('Bills')}<span className="orange">.</span></h1><p className="subhead">{t('Review your recent transactions.')}</p></div>
    </header>

    {error && <p className="billflow-feedback billflow-error" role="alert">{error}</p>}

    {loading && !data ? <div className="billflow-empty"><span>{t('Loading transactions…')}</span></div> : <>
      <div className="billflow-metrics">
        <article className="billflow-metric"><span>{t('Total spending')}</span><strong>{money(spending, language)}</strong><small>{t('{count} transactions').replace('{count}', String(transactions.filter((transaction) => Number(transaction.amount) < 0).length))}</small></article>
        <article className="billflow-metric"><span>{t('Income')}</span><strong>{money(income, language)}</strong><small>{t('Net')}: {money(income - spending, language)}</small></article>
      </div>

      <section className="billflow-card">
        <div className="section-heading"><div><p className="eyebrow">{t('LATEST')}</p><h2>{t('Recent transactions')}</h2></div><span className="billflow-count">{transactions.length}</span></div>
        {transactions.length ? <div className="billflow-transactions">{transactions.slice(0, 8).map((transaction) => <article className="billflow-transaction" key={transaction.id}>
          <span className="billflow-transaction-icon"><FileText size={16}/></span>
          <div><b>{transaction.description || t('Transaction')}</b><small>{transaction.categoryId ? t(transaction.categoryId) : t('Transaction')} · {transactionDate(transaction, language)}</small></div>
          <strong>{Number(transaction.amount) < 0 ? '−' : '+'}{money(Math.abs(Number(transaction.amount) || 0), language)}</strong>
        </article>)}</div> : <div className="billflow-empty"><FileText size={18}/><span>{t('No transactions to show yet.')}</span></div>}
      </section>
    </>}
  </section>
}
