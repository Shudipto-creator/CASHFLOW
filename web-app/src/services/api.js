const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

async function request(path, body, token) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    const message = Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail || data.message
    throw new Error(message || 'Could not connect to the FINN server.')
  }
  return data
}

export const login = (email, password) => request('/api/auth/login', { email, password })
// The existing backend stores the display name in its legacy company_name field.
export const register = ({ name, ...userData }) => request('/api/auth/register', { ...userData, company_name: name })
export const requestPasswordRecovery = (email) =>
  request('/api/auth/password-recovery/request', { email })
export const completePasswordRecovery = ({ email, challenge_id, code, new_password }) =>
  request('/api/auth/password-recovery/complete', { email, challenge_id, code, new_password })
export const chatWithCfoAi = (message, token, options = {}) => request('/api/banking/agent/chat', { message, ...options }, token)
export const approveSandboxTransfer = (intent_id, approval_id, token) =>
  request('/api/banking/agent/transfer/approve', { intent_id, approval_id }, token)

async function billflowRequest(path, token, options = {}) {
  const response = await fetch(`${API_BASE_URL}/api/billflow${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    const message = Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail || data.message
    throw new Error(message || 'Could not load your bills.')
  }
  return data
}

export const getBillflowOverview = (token) => billflowRequest('/overview', token)
export const getBillflowTransactions = (token, limit = 100) =>
  billflowRequest(`/transactions?limit=${encodeURIComponent(limit)}`, token)
export const getBillflowAnomalies = (token, types = ['all']) =>
  billflowRequest('/anomalies', token, {
    method: 'POST',
    body: JSON.stringify({ types }),
  })
export const categorizeBillflowTransactions = (token) =>
  billflowRequest('/categorize', token, { method: 'POST', body: JSON.stringify({}) })
export const importBillflowStatement = (file, token) => {
  const body = new FormData()
  body.append('file', file)
  return billflowRequest('/import', token, { method: 'POST', body })
}

async function contactsRequest(path, token, options = {}) {
  const response = await fetch(`${API_BASE_URL}/api/contacts${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (response.status === 204) return null
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join(', ')
      : detail || data.error?.message || data.message
    if (response.status === 404 && message === 'Not Found') {
      throw new Error('Contacts service not available. Restart the backend, then refresh this page.')
    }
    throw new Error(message || 'Could not load your contacts.')
  }
  return data
}

export const getContacts = (token) => contactsRequest('', token)
export const searchContactCustomers = (name, token) =>
  contactsRequest(`/search?name=${encodeURIComponent(name)}`, token)
export const addContact = (customerId, token) =>
  contactsRequest('', token, {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId }),
  })
export const addContactByUserId = (userId, token) =>
  contactsRequest('/by-user-id', token, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  })
export const previewContactByUserId = (userId, token) =>
  contactsRequest('/by-user-id/preview', token, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  })
export const removeContact = (customerId, token) =>
  contactsRequest(`/${encodeURIComponent(customerId)}`, token, { method: 'DELETE' })

export async function getDemoBankData(token, count = 10) {
  const response = await fetch(`${API_BASE_URL}/api/banking/demo-data?count=${encodeURIComponent(count)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.detail || 'Could not load the demo bank data.')
  }
  return data
}
