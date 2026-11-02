import { useCallback, useEffect, useRef, useState } from 'react'
import { FileText, Upload, ShieldCheck, AlertTriangle, Copy, TrendingUp, Repeat2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { getBillFlowOverview, importBillFlowFile } from '../services/api.js'

const ACCEPTED = '.csv,.txt,.xlsx,.xls,.pdf,.docx,.png,.jpg,.jpeg'

const IMPORT_STATUS_LABELS = {
  imported: 'Statement imported',
  preview: 'Preview only — nothing was saved',
  duplicate_file: 'Duplicate file',
  no_transactions: 'No transactions found',
  rejected: 'File rejected',
}

function formatAmount(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `¥${new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Math.abs(number))}`
}

export default function BillsPage({ onNotice }) {
  const { token } = useAuth()
  const fileInput = useRef(null)
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    getBillFlowOverview(token)
      .then((data) => { setOverview(data); setError('') })
      .catch((err) => setError(err.message || 'Could not load bill analysis.'))
      .finally(() => setLoading(false))
  }, [token])

  useEffect(load, [load])

  async function handleImport(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size === 0) {
      setImportResult({ status: 'rejected', message: 'That file is empty. Export a bank statement with at least one transaction row.' })
      return
    }
    setImporting(true)
    setImportResult(null)
    try {
      const result = await importBillFlowFile(file, token)
      setImportResult(result)
      if (result.status === 'imported') {
        onNotice(`Imported ${result.transaction_count} transactions from ${file.name}.`)
        load()
      }
    } catch (err) {
      setImportResult({ status: 'rejected', message: err.message || 'Import failed.' })
    } finally {
      setImporting(false)
    }
  }

  const totals = overview?.totals || {}
  const byCategory = overview?.by_category || []
  const anomalySummary = overview?.anomaly_summary || {}
  const topAnomalies = overview?.top_anomalies || []
  const imports = overview?.imports || []
  const hasData = Boolean(overview) && (imports.length > 0 || byCategory.length > 0)

  return <section className="bills-page">
    <header className="welcome activity-welcome"><div><h1>Bills<span className="orange">.</span></h1><p className="subhead">Import a bank statement and FINN reviews the bills for you.</p></div></header>

    <div className="bills-import-card">
      <div className="bills-import-copy">
        <b>Import bank statement</b>
        <small>CSV, XLSX, PDF or image. Parsing, categorization and anomaly math all run locally — nothing is uploaded to a third party.</small>
      </div>
      <input ref={fileInput} type="file" accept={ACCEPTED} onChange={handleImport} hidden disabled={importing} />
      <button className="bills-import-button" onClick={() => fileInput.current?.click()} disabled={importing}>
        <Upload size={15}/> {importing ? 'Analyzing…' : 'Choose file'}
      </button>
    </div>

    {importResult && <div className={`bills-import-result status-${importResult.status}`}>
      <b>{IMPORT_STATUS_LABELS[importResult.status] || importResult.status}</b>
      <p>{importResult.message || (importResult.status === 'imported'
        ? `${importResult.inserted} transactions saved, ${importResult.skipped_duplicates} duplicate rows skipped.`
        : 'Review the file and try again.')}</p>
      {Array.isArray(importResult.errors) && importResult.errors.length > 0 && <ul>{importResult.errors.slice(0, 4).map((item, index) => <li key={index}>{typeof item === 'string' ? item : item.message || JSON.stringify(item)}</li>)}</ul>}
    </div>}

    {loading ? <section className="contacts-empty-state activity-empty-state"><div className="empty-illustration"><span className="empty-avatar"><FileText size={25}/></span></div><h2>Loading bill analysis</h2></section>
      : error ? <section className="contacts-empty-state activity-empty-state"><div className="empty-illustration"><span className="empty-avatar"><AlertTriangle size={25}/></span></div><h2>BillFlow unavailable</h2><p className="empty-description">{error}</p></section>
      : !hasData ? <section className="contacts-empty-state activity-empty-state"><div className="empty-illustration"><span className="empty-orbit orbit-one"/><span className="empty-orbit orbit-two"/><span className="empty-avatar"><FileText size={25}/></span></div><h2>No bills analyzed yet</h2><p className="empty-description">Import a bank statement CSV above. FINN will categorize spending, flag duplicates and unusual spikes, and detect recurring charges you may have forgotten.</p></section>
      : <>
        <div className="bills-stat-grid">
          <div><small>TOTAL SPENDING</small><b>{formatAmount(totals.spending)}</b></div>
          <div><small>TOTAL INCOME</small><b className="positive">{formatAmount(totals.income)}</b></div>
          <div><small>TRANSACTIONS</small><b>{totals.transaction_count ?? imports.reduce((sum, item) => sum + (item.transaction_count || 0), 0)}</b></div>
        </div>

        <div className="bills-section">
          <div className="section-heading"><div><p className="eyebrow">WHERE THE MONEY WENT</p><h2>Spending by category</h2></div></div>
          <div className="bills-category-list">
            {byCategory.map((row) => <div className="bills-category-row" key={row.category}>
              <span className="bills-category-name">{row.category}</span>
              <span className="bills-category-bar"><i style={{ width: `${Math.min(100, Number(row.share_pct) || 0)}%` }}/></span>
              <b>{formatAmount(row.total)}</b>
              <small>{row.share_pct}%</small>
            </div>)}
            {!byCategory.length && <p className="bills-empty-line">No categorized spending yet.</p>}
          </div>
        </div>

        <div className="bills-section">
          <div className="section-heading"><div><p className="eyebrow">ANOMALY SCAN</p><h2>Unusual charges</h2></div><span className="section-count">{(anomalySummary.total_flags ?? topAnomalies.length)} flagged</span></div>
          <div className="bills-anomaly-chips">
            <span><Copy size={13}/> {anomalySummary.duplicate_count ?? 0} duplicates</span>
            <span><TrendingUp size={13}/> {anomalySummary.spike_count ?? 0} spikes</span>
            <span><Repeat2 size={13}/> {anomalySummary.forgotten_subscription_count ?? 0} forgotten subscriptions</span>
          </div>
          {topAnomalies.length > 0 && <div className="bills-anomaly-list">{topAnomalies.map((finding, index) => <div className="bills-anomaly-row" key={index}>
            <span className={`anomaly-severity severity-${finding.severity || 'medium'}`}/>
            <span className="bills-anomaly-copy"><b>{finding.merchant || finding.description || finding.type}</b><small>{finding.reason}</small></span>
            {finding.amount !== undefined && <b className="bills-anomaly-amount">{formatAmount(finding.amount)}</b>}
          </div>)}</div>}
          {!topAnomalies.length && <p className="bills-empty-line">No duplicates, spikes or forgotten subscriptions detected.</p>}
        </div>

        {imports.length > 0 && <div className="bills-section">
          <div className="section-heading"><div><p className="eyebrow">STATEMENTS</p><h2>Recent imports</h2></div></div>
          <div className="contact-list">{imports.map((item) => <div className="contact-row" key={item.import_id}>
            <span className="contact-avatar"><FileText size={16}/></span>
            <span className="contact-info"><b>{item.filename}</b><small>{item.bank || 'bank'} · {item.transaction_count} transactions{item.imported_at ? ` · ${new Date(item.imported_at).toLocaleDateString()}` : ''}</small></span>
          </div>)}</div>
        </div>}
      </>}

    <div className="security-note bills-review-note"><span><ShieldCheck size={16}/></span><div><b>Review-only</b><small>Bill analysis never moves money. Transfers stay in the FINN chat with the full zero-trust approval flow.</small></div></div>
  </section>
}
