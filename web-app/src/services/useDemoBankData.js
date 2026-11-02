import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { getDemoBankData } from './api.js'

const bankDataByToken = new Map()
const bankRequestsByToken = new Map()

function loadBankData(token) {
  if (bankDataByToken.has(token)) return Promise.resolve(bankDataByToken.get(token))
  if (bankRequestsByToken.has(token)) return bankRequestsByToken.get(token)

  const request = getDemoBankData(token)
    .then((result) => {
      bankDataByToken.set(token, result)
      return result
    })
    .finally(() => bankRequestsByToken.delete(token))
  bankRequestsByToken.set(token, request)
  return request
}

export function useDemoBankData() {
  const { token } = useAuth()
  const [state, setState] = useState(() => ({
    token,
    data: token ? bankDataByToken.get(token) || null : null,
    loading: token ? !bankDataByToken.has(token) : false,
    error: '',
  }))

  useEffect(() => {
    let active = true
    if (!token) {
      setState({ token, data: null, loading: false, error: '' })
      return () => { active = false }
    }

    const cached = bankDataByToken.get(token)
    if (cached) {
      setState({ token, data: cached, loading: false, error: '' })
    } else {
      setState({ token, data: null, loading: true, error: '' })
      loadBankData(token)
        .then((data) => { if (active) setState({ token, data, loading: false, error: '' }) })
        .catch((err) => {
          if (active) setState({ token, data: null, loading: false, error: err.message || 'Could not load demo bank data.' })
        })
    }
    return () => { active = false }
  }, [token])

  return state.token === token
    ? state
    : { token, data: null, loading: Boolean(token), error: '' }
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
  // The local Postman preview uses COSMIC_COINS. For the UI preview only,
  // present that seed unit as yuan while preserving the API's raw amount.
  if (currency === 'COS' || currency === 'COSMIC_COINS') {
    return `¥${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value)}`
  }
  const demoCurrencies = { COS: 'COSMIC_COINS', GAL: 'GALAXY_GOLD', MOO: 'MOON_BUCKS' }
  const label = demoCurrencies[currency] || currency
  const digits = demoCurrencies[currency] ? 0 : 2
  return `${new Intl.NumberFormat('en', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)} ${label}`
}

export function currencyLabel(currency = 'CNY') {
  if (currency === 'COS' || currency === 'COSMIC_COINS') return 'CNY'
  return { GAL: 'GALAXY_GOLD', MOO: 'MOON_BUCKS' }[currency] || currency
}

export function transactionDate(transaction) {
  const raw = transaction.date || transaction.bookingDate || transaction.valueDate || transaction.createdAt
  if (!raw) return ''
  const date = new Date(raw)
  return Number.isNaN(date.getTime()) ? String(raw) : date.toLocaleDateString()
}
