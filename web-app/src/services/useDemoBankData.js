import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { getDemoBankData } from './api.js'

export function useDemoBankData() {
  const { token } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    getDemoBankData(token)
      .then((result) => { if (active) setData(result) })
      .catch((err) => { if (active) setError(err.message || 'Could not load demo bank data.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token])

  return { data, loading, error }
}

export function accountRows(data) {
  const accounts = data?.accounts
  return Array.isArray(accounts) ? accounts : Array.isArray(accounts?.items) ? accounts.items : []
}

export function transactionRows(data) {
  const transactions = data?.transactions
  return Array.isArray(transactions) ? transactions : Array.isArray(transactions?.items) ? transactions.items : []
}

export function formatMoney(amount, currency = 'CNY') {
  const value = Number(amount)
  if (!Number.isFinite(value)) return '—'
  if (currency === 'CNY') {
    return `¥${new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)}`
  }
  return `${new Intl.NumberFormat('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)} ${currency}`
}

export function transactionDate(transaction) {
  const raw = transaction.date || transaction.bookingDate || transaction.valueDate || transaction.createdAt
  if (!raw) return ''
  const date = new Date(raw)
  return Number.isNaN(date.getTime()) ? String(raw) : date.toLocaleDateString()
}
