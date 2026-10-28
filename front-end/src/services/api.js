import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      // Don't auto-logout for banking API 401s. These are typically
      // signing/verification failures (cryptographic proof of intent), not
      // auth/session failures. Let the banking components surface an error
      // message instead of logging the user out.
      if (url.includes('/api/banking/')) {
        return Promise.reject(error);
      }
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export const login = (email, password) =>
  api.post('/api/auth/login', { email, password });

export const register = (userData) =>
  api.post('/api/auth/register', userData);

export const uploadDocuments = (formData) =>
  api.post('/api/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const getDocuments = (params) =>
  api.get('/api/documents', { params });

export const getDocument = (id) =>
  api.get(`/api/documents/${id}`);

export const updateDocumentClassification = (id, documentType) =>
  api.patch(`/api/documents/${id}/classification`, { document_type: documentType });

export const deleteDocument = (id) =>
  api.delete(`/api/documents/${id}`);

export const runAnalysis = (data) =>
  api.post('/api/analysis/run', data);

export const getAnalyses = (params) =>
  api.get('/api/analysis', { params });

export const getAnalysis = (id) =>
  api.get(`/api/analysis/${id}`);

export const askCFO = (data) =>
  api.post('/api/ask-cfo', data);

export const getChatHistory = (analysisId) =>
  api.get(`/api/analysis/${encodeURIComponent(analysisId)}/chat`);

export const clearChatHistory = (analysisId) =>
  api.delete(`/api/analysis/${encodeURIComponent(analysisId)}/chat`);

export const getDashboardCharts = (analysisId) =>
  api.get(`/api/dashboard/charts/${analysisId}`);

export const generateDashboardInsights = (data) =>
  api.post('/api/dashboard/insights', data);

export const checkHealth = () =>
  api.get('/api/health');

export const getProcessingMode = (opts) =>
  api.get('/api/settings/mode', opts ? { signal: opts.signal } : undefined);

export const setProcessingMode = (mode) =>
  api.put('/api/settings/mode', { mode });

// BillFlow local ledger & billing
export const getBillFlowOverview = () => api.get('/api/billflow/overview');
export const getBillFlowCategories = () => api.get('/api/billflow/categories');
export const importBillFlowCsv = (formData, dryRun = false) =>
  api.post(`/api/billflow/import${dryRun ? '?dry_run=true' : ''}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
export const getBillFlowTransactions = (params) =>
  api.get('/api/billflow/transactions', { params });
export const updateBillFlowTransaction = (id, data) =>
  api.patch(`/api/billflow/transactions/${id}`, data);
export const categorizeBillFlow = () => api.post('/api/billflow/categorize');
export const getBillFlowAnomalies = (data = { types: ['all'] }) =>
  api.post('/api/billflow/anomalies', data);
export const getBillFlowSummary = (params) =>
  api.get('/api/billflow/summary', { params });
export const askBillFlowMoneyGone = (data = {}) =>
  api.post('/api/billflow/ask', data);

// TrueWealth-inspired portfolio metrics
export const analyzePortfolio = (data) =>
  api.post('/api/portfolio/analyze', data);

// Zero-Trust banking security layer (backend bridge over okgate + SecureBankGate)
export const getBankingTools = (data, config) => api.get('/api/banking/tools', config || {});
export const bankingCall = (data, config) => api.post('/api/banking/call', data, config);
export const getBankingStatus = (data, config) => api.get('/api/banking/status', config || {});
export const getBankingSpend = (data, config) => api.get('/api/banking/spend', config || {});
export const getBankingTier = (tool, amount) =>
  api.get('/api/banking/tier', { params: { tool, amount } });
export const getBankingAudit = (data, config) => api.get('/api/banking/audit', config || {});
export const verifyBankingAudit = (data, config) => api.get('/api/banking/audit/verify', config || {});
export const getBankingApprovals = (data, config) => api.get('/api/banking/approvals', config || {});

export const prepareBankingTransfer = (data, config) =>
  api.post('/api/banking/transfer/prepare', data, config);
export const executeBankingTransfer = (data, config) =>
  api.post('/api/banking/transfer/execute', data, config);
export const approveBankingTransfer = (data, config) =>
  api.post(`/api/banking/transfer/execute/${encodeURIComponent(config?.intentId || '')}/approve`, data, config);

export const startMfaChallenge = (data, config) =>
  api.post('/api/banking/mfa/challenge', data, config);
export const getMfaCode = (challengeId, config) =>
  api.get(`/api/banking/mfa/code/${encodeURIComponent(challengeId)}`, config);
export const verifyMfaCode = (data, config) =>
  api.post('/api/banking/mfa/verify', data, config);

export const killBanking = (data, config) => api.post('/api/banking/kill', data, config);
export const resumeBanking = (data, config) => api.post('/api/banking/resume', data, config);

export default api;
