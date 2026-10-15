import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add token to requests
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
  }
);

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Unauthorized - redirect to login
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const login = (email, password) =>
  api.post('/api/auth/login', { email, password });

export const register = (userData) =>
  api.post('/api/auth/register', userData);

// Documents API
export const uploadDocuments = (formData) =>
  api.post('/api/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const getDocuments = (params) =>
  api.get('/api/documents', { params });

export const getDocument = (id) =>
  api.get(`/api/documents/${id}`);

export const deleteDocument = (id) =>
  api.delete(`/api/documents/${id}`);

// Analysis API
export const runAnalysis = (data) =>
  api.post('/api/analysis/run', data);

export const getAnalyses = (params) =>
  api.get('/api/analysis', { params });

export const getAnalysis = (id) =>
  api.get(`/api/analysis/${id}`);

// Ask CFO
export const askCFO = (data) =>
  api.post('/api/ask-cfo', data);

// Financial Intelligence Dashboard
export const getDashboardCharts = (analysisId) =>
  api.get(`/api/dashboard/charts/${analysisId}`);

export const generateDashboardInsights = (data) =>
  api.post('/api/dashboard/insights', data);

// Health Check
export const checkHealth = () =>
  api.get('/api/health');

export default api;
