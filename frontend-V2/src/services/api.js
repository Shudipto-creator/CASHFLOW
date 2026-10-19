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

export const getProcessingMode = () =>
  api.get('/api/settings/mode');

export const setProcessingMode = (mode) =>
  api.put('/api/settings/mode', { mode });

export default api;
