import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const csrf = document.cookie.match(/cf_csrf=([^;]+)/)?.[1];
  if (csrf && !['GET', 'HEAD', 'OPTIONS'].includes(config.method?.toUpperCase())) {
    config.headers['X-CSRF-Token'] = decodeURIComponent(csrf);
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      if (!url.includes('/api/auth/')) {
        localStorage.removeItem('user');
      }
    }
    return Promise.reject(error);
  }
);

export const login = (email, password) => api.post('/api/auth/login', { email, password });
export const register = (userData) => api.post('/api/auth/register', userData);
export const logout = () => api.post('/api/auth/logout');
export const getMe = () => api.get('/api/auth/me');
export const getCsrf = () => api.post('/api/auth/csrf-token');

export const listAccounts = (params) => api.get('/api/accounts', { params });
export const createAccount = (data) => api.post('/api/accounts', data);
export const updateAccount = (id, data) => api.patch(`/api/accounts/${id}`, data);
export const deleteAccount = (id) => api.delete(`/api/accounts/${id}`);

export const listTransactions = (params) => api.get('/api/transactions', { params });
export const createTransaction = (data) => api.post('/api/transactions', data);
export const updateTransaction = (id, data) => api.patch(`/api/transactions/${id}`, data);
export const deleteTransaction = (id) => api.delete(`/api/transactions/${id}`);

export const listInvoices = (params) => api.get('/api/invoices', { params });
export const createInvoice = (data) => api.post('/api/invoices', data);
export const updateInvoice = (id, data) => api.patch(`/api/invoices/${id}`, data);
export const deleteInvoice = (id) => api.delete(`/api/invoices/${id}`);

export const listDocuments = (params) => api.get('/api/documents', { params });
export const uploadDocument = (formData) => api.post('/api/documents', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
export const deleteDocument = (id) => api.delete(`/api/documents/${id}`);

export const runForecast = (data) => api.post('/api/forecasts/run', data);
export const listForecasts = (params) => api.get('/api/forecasts', { params });

export const listAlerts = (params) => api.get('/api/alerts', { params });
export const listAlertRules = (params) => api.get('/api/alerts/rules', { params });
export const createAlertRule = (data) => api.post('/api/alerts/rules', data);
export const updateAlert = (id, data) => api.patch(`/api/alerts/${id}`, data);

export const listFinancingProducts = (params) => api.get('/api/financing/products', { params });
export const getFinancingRecommendations = (data) => api.post('/api/financing/recommendations', data);

export const listProposedActions = (params) => api.get('/api/approvals', { params });
export const decideAction = (id, data) => api.post(`/api/approvals/${id}/decide`, data);

export const listAuditEvents = (params) => api.get('/api/audit', { params });
export const verifyAudit = () => api.post('/api/audit/verify');

export const listGoals = (params) => api.get('/api/goals', { params });
export const createGoal = (data) => api.post('/api/goals', data);
export const updateGoal = (id, data) => api.patch(`/api/goals/${id}`, data);
export const deleteGoal = (id) => api.delete(`/api/goals/${id}`);

export const askCFO = (data) => api.post('/api/ask', data);

export const getOrg = () => api.get('/api/organizations/me');
export const exportData = () => api.get('/api/settings/export');
export const createSupportTicket = (data) => api.post('/api/support', data);

export default api;
