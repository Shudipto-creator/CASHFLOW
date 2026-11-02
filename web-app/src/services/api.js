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
export const chatWithCfoAi = (message, token, options = {}) => request('/api/banking/agent/chat', { message, ...options }, token)
export const approveSandboxTransfer = (intent_id, approval_id, token) =>
  request('/api/banking/agent/transfer/approve', { intent_id, approval_id }, token)

export async function getDemoBankData(token) {
  const response = await fetch(`${API_BASE_URL}/api/banking/demo-data`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.detail || 'Could not load the demo bank data.')
  }
  return data
}

async function billflowRequest(path, { method = 'GET', body, formData, token } = {}) {
  const headers = { ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    ...(formData ? { body: formData } : body !== undefined ? { body: JSON.stringify(body) } : {}),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    const message = Array.isArray(detail) ? detail.map((item) => item.msg).join(', ') : detail || data.message
    throw new Error(message || 'Could not reach the BillFlow service.')
  }
  return data
}

export const getBillFlowOverview = (token) => billflowRequest('/api/billflow/overview', { token })

export const importBillFlowFile = (file, token) => {
  const formData = new FormData()
  formData.append('file', file)
  return billflowRequest('/api/billflow/import', { method: 'POST', formData, token })
}

export const getBillFlowTransactions = (params = {}, token) => {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  ).toString()
  return billflowRequest(`/api/billflow/transactions${query ? `?${query}` : ''}`, { token })
}

export const runBillFlowAnomalies = (types, token) =>
  billflowRequest('/api/billflow/anomalies', { method: 'POST', body: { types }, token })
