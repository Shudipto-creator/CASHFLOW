import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/Common/ProtectedRoute';
import ThemeLayout from './components/Layout/ThemeLayout';

// Pages
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Documents from './pages/Documents';
import Analysis from './pages/Analysis';
import Report from './pages/Report';
import FinancialIntelligence from './pages/FinancialIntelligence';
import Reports from './pages/Reports';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route
            element={
              <ProtectedRoute>
                <ThemeLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/financial-intelligence" element={<FinancialIntelligence />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/report/:analysisId" element={<Report />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
