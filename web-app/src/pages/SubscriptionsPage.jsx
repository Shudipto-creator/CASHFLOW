import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, BellRing, ChevronLeft, RefreshCw, Repeat2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { useLanguage } from '../context/LanguageContext.jsx'
import { getBillflowAnomalies, getBillflowTransactions } from '../services/api.js'

function money(value, language) {
  return new Intl.NumberFormat(language === 'zh' ? 'zh-CN' : 'en', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(Number(value) || 0)
}

function recurringGroups(transactions) {
  const grouped = new Map()
  for (const transaction of transactions) {
    if (!transaction.is_recurring) continue
    const name = String(transaction.description || 'Subscription').trim()
    const key = name.toLocaleLowerCase()
    const current = grouped.get(key) || { name, rows: [], total: 0 }
    current.rows.push(transaction)
    current.total += Math.abs(Number(transaction.amount) || 0)
    grouped.set(key, current)
  }
  return [...grouped.values()]
    .map((group) => ({
      ...group,
      average: group.total / group.rows.length,
      lastDate: group.rows.map((row) => row.date).filter(Boolean).sort().at(-1),
      count: group.rows.length,
    }))
    .sort((a, b) => b.average - a.average)
}

export default function SubscriptionsPage({ onBack, backLabel = 'Me' }) {
  const { token } = useAuth()
  const { t, language } = useLanguage()
  const [transactions, setTransactions] = useState([])
  const [findings, setFindings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadSubscriptions = useCallback(async () => {
    setError('')
    try {
      const [transactionResult, anomalyResult] = await Promise.all([
        getBillflowTransactions(token, 500),
        getBillflowAnomalies(token, ['forgotten_subscriptions']),
      ])
      setTransactions(transactionResult.transactions || [])
      setFindings(anomalyResult.forgotten_subscriptions || [])
    } catch (loadError) {
      setError(loadError.message || t('Could not load subscription activity.'))
    } finally {
      setLoading(false)
    }
  }, [token, t])

  useEffect(() => {
    loadSubscriptions()
  }, [loadSubscriptions])

  const subscriptions = recurringGroups(transactions)
  const monthlyEstimate = subscriptions.reduce((sum, item) => sum + item.average, 0)
  const annualEstimate = monthlyEstimate * 12

  return <section className="billflow-page">
    <header className="welcome billflow-welcome">
      <button className="parameters-back" onClick={onBack} aria-label={t(`Back to ${backLabel}`)}><ChevronLeft size={20}/><span>{t(backLabel)}</span></button>
      <div><h1>{t('Subscriptions')}<span className="orange">.</span></h1><p className="subhead">{t('Find recurring charges and review what may be unused.')}</p></div>
    </header>

    <div className="billflow-actions">
      <button className="billflow-secondary-action" disabled={loading} onClick={loadSubscriptions}><RefreshCw size={16}/>{t('Refresh detection')}</button>
    </div>
    {error && <p className="billflow-feedback billflow-error" role="alert">{error}</p>}

    {loading ? <div className="billflow-empty"><RefreshCw size={18}/><span>{t('Checking recurring charges…')}</span></div> : <>
      <div className="billflow-metrics">
        <article className="billflow-metric"><span>{t('Detected subscriptions')}</span><strong>{subscriptions.length}</strong><small>{t('Based on repeated statement charges')}</small></article>
        <article className="billflow-metric"><span>{t('Estimated monthly total')}</span><strong>{money(monthlyEstimate, language)}</strong><small>{t('Estimated yearly')}: {money(annualEstimate, language)}</small></article>
      </div>

      <section className="billflow-card">
        <div className="section-heading"><div><p className="eyebrow">{t('RECURRING CHARGES')}</p><h2>{t('Detected subscriptions')}</h2></div><span className="billflow-count">{subscriptions.length}</span></div>
        {subscriptions.length ? <div className="billflow-transactions">{subscriptions.map((subscription) => <article className="billflow-transaction subscription-transaction" key={subscription.name.toLocaleLowerCase()}>
          <span className="billflow-transaction-icon"><Repeat2 size={16}/></span>
          <div><b>{subscription.name}</b><small>{t('{count} observed charges').replace('{count}', String(subscription.count))}{subscription.lastDate ? ` · ${t('Last seen')} ${subscription.lastDate}` : ''}</small></div>
          <strong>{money(subscription.average, language)}<small>{t('per charge')}</small></strong>
        </article>)}</div> : <div className="billflow-empty"><BellRing size={18}/><span>{t('No recurring charges found yet. Import a statement with repeated payments to detect subscriptions.')}</span></div>}
      </section>

      <section className="billflow-card">
        <div className="section-heading"><div><p className="eyebrow">{t('REVIEW')}</p><h2>{t('Possible forgotten subscriptions')}</h2></div><span className="billflow-count">{findings.length}</span></div>
        {findings.length ? <div className="billflow-findings">{findings.map((finding, index) => <article className="billflow-finding" key={`${finding.merchant}-${index}`}>
          <span className="billflow-finding-icon"><AlertCircle size={17}/></span>
          <div><b>{finding.description || finding.merchant}</b><p>{finding.reason}</p></div>
          <strong>{money(finding.annual_cost_estimate || finding.potential_savings, language)}<small>{t('per year est.')}</small></strong>
        </article>)}</div> : <p className="billflow-empty-copy">{t('No potentially forgotten subscriptions were detected.')}</p>}
      </section>

      <p className="billflow-disclaimer">{t('Detection and estimates only. FINN cannot cancel subscriptions through the connected banking service.')}</p>
    </>}
  </section>
}
