import { useCallback, useEffect, useState } from 'react'
import { Repeat2, ShieldCheck, AlertTriangle, CalendarClock } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { getBillFlowTransactions, runBillFlowAnomalies } from '../services/api.js'

const DAY_MS = 86400000

function formatAmount(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `¥${new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(number)}`
}

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString()
}

function median(numbers) {
  if (!numbers.length) return 0
  const sorted = [...numbers].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function snapCycle(days) {
  const buckets = [[7, 'Weekly'], [14, 'Every 2 weeks'], [30, 'Monthly'], [90, 'Quarterly'], [365, 'Yearly']]
  for (const [bucket, label] of buckets) {
    if (Math.abs(days - bucket) <= Math.max(2, bucket * 0.12)) return { days: bucket, label }
  }
  return { days: Math.max(1, Math.round(days)), label: `Every ${Math.max(1, Math.round(days))} days` }
}

function merchantKey(description = '') {
  return description.replace(/\d+/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase() || 'unknown merchant'
}

/** Group recurring charges per merchant and estimate the next renewal date. */
export function estimateRenewals(transactions) {
  const byMerchant = new Map()
  for (const txn of transactions) {
    const isSubscription = txn.is_recurring || (txn.category || '') === 'Subscriptions'
    if (!isSubscription) continue
    const amount = Number(txn.amount)
    if (!Number.isFinite(amount) || amount === 0) continue
    if ((txn.category || '') === 'Income' || (txn.category || '') === 'Transfer') continue
    const key = merchantKey(txn.description)
    if (!byMerchant.has(key)) byMerchant.set(key, [])
    byMerchant.get(key).push({ date: String(txn.date).slice(0, 10), amount: Math.abs(amount), description: txn.description })
  }

  const plans = []
  for (const [key, charges] of byMerchant.entries()) {
    charges.sort((a, b) => a.date.localeCompare(b.date))
    const amount = median(charges.map((c) => c.amount))
    const last = charges[charges.length - 1]
    const gaps = []
    for (let i = 1; i < charges.length; i += 1) {
      const gap = Math.round((new Date(charges[i].date) - new Date(charges[i - 1].date)) / DAY_MS)
      if (gap > 0) gaps.push(gap)
    }
    const cycle = snapCycle(gaps.length ? median(gaps) : 30)
    const nextRenewal = new Date(new Date(last.date).getTime() + cycle.days * DAY_MS)
    while (nextRenewal.getTime() < Date.now()) nextRenewal.setTime(nextRenewal.getTime() + cycle.days * DAY_MS)
    plans.push({
      key,
      merchant: last.description || key,
      chargeCount: charges.length,
      amount: Math.round(amount * 100) / 100,
      cycleDays: cycle.days,
      cycleLabel: charges.length > 1 ? cycle.label : 'Monthly (assumed)',
      lastCharge: last.date,
      nextRenewal: nextRenewal.toISOString().slice(0, 10),
      monthlyCost: Math.round(((amount * 30) / cycle.days) * 100) / 100,
      annualCost: Math.round(((amount * 365) / cycle.days) * 100) / 100,
    })
  }
  plans.sort((a, b) => b.monthlyCost - a.monthlyCost)
  return plans
}

export default function SubscriptionsPage({ onNotice }) {
  const { token } = useAuth()
  const [state, setState] = useState({ loading: true, error: '', plans: [], forgotten: [], scanned: false })

  const load = useCallback(() => {
    if (!token) return
    setState((prev) => ({ ...prev, loading: true }))
    Promise.all([
      getBillFlowTransactions({ limit: 500 }, token),
      runBillFlowAnomalies(['forgotten_subscriptions'], token).catch(() => null),
    ])
      .then(([txnData, anomalyData]) => {
        const transactions = txnData?.transactions || []
        setState({
          loading: false,
          error: '',
          plans: estimateRenewals(transactions),
          forgotten: anomalyData?.forgotten_subscriptions || [],
          scanned: transactions.length > 0,
        })
      })
      .catch((err) => setState({ loading: false, error: err.message || 'Could not load subscriptions.', plans: [], forgotten: [], scanned: false }))
  }, [token])

  useEffect(load, [load])

  const { loading, error, plans, forgotten, scanned } = state
  const monthlyTotal = plans.reduce((sum, plan) => sum + plan.monthlyCost, 0)
  const annualTotal = plans.reduce((sum, plan) => sum + plan.annualCost, 0)
  const potentialSavings = forgotten.reduce((sum, item) => sum + Number(item.potential_savings || 0), 0)

  return <section className="subscriptions-page">
    <header className="welcome activity-welcome"><div><h1>Subscriptions<span className="orange">.</span></h1><p className="subhead">Recurring charges and upcoming renewal estimates from your imported statements.</p></div></header>

    {loading ? <section className="contacts-empty-state activity-empty-state"><div className="empty-illustration"><span className="empty-avatar"><Repeat2 size={25}/></span></div><h2>Scanning recurring charges</h2></section>
      : error ? <section className="contacts-empty-state activity-empty-state"><div className="empty-illustration"><span className="empty-avatar"><AlertTriangle size={25}/></span></div><h2>BillFlow unavailable</h2><p className="empty-description">{error}</p></section>
      : !scanned || !plans.length ? <section className="contacts-empty-state activity-empty-state"><div className="empty-illustration"><span className="empty-orbit orbit-one"/><span className="empty-orbit orbit-two"/><span className="empty-avatar"><Repeat2 size={25}/></span></div><h2>No subscriptions detected</h2><p className="empty-description">{scanned ? 'No recurring charges were found in the imported transactions yet.' : 'Import a bank statement on the Bills screen first. FINN then detects recurring charges and estimates renewal dates automatically.'}</p></section>
      : <>
        <div className="bills-stat-grid">
          <div><small>EST. MONTHLY</small><b>{formatAmount(monthlyTotal)}</b></div>
          <div><small>EST. ANNUAL</small><b>{formatAmount(annualTotal)}</b></div>
          <div><small>ACTIVE PLANS</small><b>{plans.length}</b></div>
        </div>

        <div className="bills-section">
          <div className="section-heading"><div><p className="eyebrow">RENEWAL SCHEDULE</p><h2>Upcoming renewals</h2></div></div>
          <div className="subscription-list">{plans.map((plan) => <div className="subscription-card" key={plan.key}>
            <span className="subscription-icon"><Repeat2 size={16}/></span>
            <span className="subscription-copy">
              <b>{plan.merchant}</b>
              <small>{plan.cycleLabel} · last charge {formatDate(plan.lastCharge)} · {plan.chargeCount} charges seen</small>
            </span>
            <span className="subscription-figures">
              <b>{formatAmount(plan.amount)}</b>
              <small><CalendarClock size={11}/> renews {formatDate(plan.nextRenewal)}</small>
            </span>
          </div>)}</div>
        </div>

        {forgotten.length > 0 && <div className="bills-section">
          <div className="section-heading"><div><p className="eyebrow">REVIEW</p><h2>Possibly forgotten</h2></div><span className="section-count">{formatAmount(potentialSavings)}/yr</span></div>
          <div className="bills-anomaly-list">{forgotten.map((item, index) => <div className="bills-anomaly-row" key={index}>
            <span className={`anomaly-severity severity-${item.severity || 'medium'}`}/>
            <span className="bills-anomaly-copy"><b>{item.merchant || item.description}</b><small>{item.reason}</small></span>
            <b className="bills-anomaly-amount">{formatAmount(Math.abs(Number(item.amount) || 0))}</b>
          </div>)}</div>
        </div>}
      </>}

    <div className="security-note bills-review-note"><span><ShieldCheck size={16}/></span><div><b>Review-only estimates</b><small>Renewal dates are estimates from past charges. Cancelling a subscription stays with the merchant — FINN never moves money from this screen.</small></div></div>
  </section>
}
