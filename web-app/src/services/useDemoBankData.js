import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { getDemoBankData } from './api.js'

const bankDataByToken = new Map()
const bankRequestsByToken = new Map()
const bankRefreshRequestsByToken = new Map()
const bankDataVersionsByToken = new Map()

export function refreshDemoBankData() {
  window.dispatchEvent(new Event('finn:bank-data-refresh'))
}

function loadBankData(token, force = false) {
  if (!force && bankDataByToken.has(token)) return Promise.resolve(bankDataByToken.get(token))
  if (!force && bankRequestsByToken.has(token)) return bankRequestsByToken.get(token)
  if (force && bankRefreshRequestsByToken.has(token)) return bankRefreshRequestsByToken.get(token)

  const version = (bankDataVersionsByToken.get(token) || 0) + 1
  bankDataVersionsByToken.set(token, version)
  const request = getDemoBankData(token, 500)
    .then((result) => {
      if (bankDataVersionsByToken.get(token) === version) bankDataByToken.set(token, result)
      return result
    })
    .finally(() => {
      if (bankRequestsByToken.get(token) === request) bankRequestsByToken.delete(token)
      if (bankRefreshRequestsByToken.get(token) === request) bankRefreshRequestsByToken.delete(token)
    })
  if (force) bankRefreshRequestsByToken.set(token, request)
  else bankRequestsByToken.set(token, request)
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

    let lastRefresh = 0
    const load = (force = false, showLoading = false) => {
      if (showLoading) {
        setState((current) => current.token === token
          ? { ...current, loading: true, error: '' }
          : current)
      } else if (!bankDataByToken.has(token)) {
        setState({ token, data: null, loading: true, error: '' })
      }
      loadBankData(token, force)
        .then((data) => {
          if (active) setState({ token, data, loading: false, error: '' })
        })
        .catch((err) => {
          if (active) setState((current) => ({
            ...current,
            token,
            loading: false,
            error: err.message || 'Could not load demo bank data.',
          }))
        })
    }
    const refresh = () => {
      if (document.visibilityState !== 'visible') return
      const now = Date.now()
      if (now - lastRefresh < 1000) return
      lastRefresh = now
      load(true, false)
    }
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') refresh()
    }

    load(false, true)
    window.addEventListener('finn:bank-data-refresh', refresh)
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', onVisibilityChange)
    const refreshInterval = window.setInterval(refresh, 5000)
    return () => {
      active = false
      window.clearInterval(refreshInterval)
      window.removeEventListener('finn:bank-data-refresh', refresh)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
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

export function formatMoney(amount, currency = 'CNY', language = 'en') {
  const value = Number(amount)
  if (!Number.isFinite(value)) return '—'
  if (currency === 'CNY') {
    return `¥${new Intl.NumberFormat(language === 'zh' ? 'zh-CN' : 'en', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)}`
  }
  // The local Postman preview uses COSMIC_COINS. For the UI preview only,
  // present that seed unit as yuan while preserving the API's raw amount.
  if (currency === 'COS' || currency === 'COSMIC_COINS') {
    return `¥${new Intl.NumberFormat(language === 'zh' ? 'zh-CN' : 'en', { maximumFractionDigits: 0 }).format(value)}`
  }
  const demoCurrencies = { COS: 'COSMIC_COINS', GAL: 'GALAXY_GOLD', MOO: 'MOON_BUCKS' }
  const label = demoCurrencies[currency] || currency
  const digits = demoCurrencies[currency] ? 0 : 2
  return `${new Intl.NumberFormat(language === 'zh' ? 'zh-CN' : 'en', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)} ${label}`
}

export function currencyLabel(currency = 'CNY') {
  if (currency === 'COS' || currency === 'COSMIC_COINS') return 'CNY'
  return { GAL: 'GALAXY_GOLD', MOO: 'MOON_BUCKS' }[currency] || currency
}

export function transactionDate(transaction, language = 'en') {
  const raw = transaction.date || transaction.bookingDate || transaction.valueDate || transaction.createdAt
  if (!raw) return ''
  const date = new Date(raw)
  return Number.isNaN(date.getTime()) ? String(raw) : date.toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en')
}
