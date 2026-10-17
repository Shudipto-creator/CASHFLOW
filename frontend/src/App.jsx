import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/Common/ProtectedRoute';
import ThemeLayout from './components/Layout/ThemeLayout';

import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Ask from './pages/Ask';
import Scenarios from './pages/Scenarios';
import Alerts from './pages/Alerts';
import Financing from './pages/Financing';
import Approvals from './pages/Approvals';
import Accounts from './pages/Accounts';
import Transactions from './pages/Transactions';
import Documents from './pages/Documents';
import Goals from './pages/Goals';
import Audit from './pages/Audit';
import Settings from './pages/Settings';
import NotFound from './pages/NotFound';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Register />} />
          <Route path="/register" element={<Navigate to="/signup" replace />} />
          <Route path="/security" element={<Landing />} />
          <Route path="/privacy" element={<Landing />} />
          <Route path="/terms" element={<Landing />} />
          <Route path="/contact" element={<Landing />} />

          <Route element={<ProtectedRoute><ThemeLayout /></ProtectedRoute>}>
            <Route path="/app" element={<Dashboard />} />
            <Route path="/app/ask" element={<Ask />} />
            <Route path="/app/scenarios" element={<Scenarios />} />
            <Route path="/app/alerts" element={<Alerts />} />
            <Route path="/app/financing" element={<Financing />} />
            <Route path="/app/approvals" element={<Approvals />} />
            <Route path="/app/accounts" element={<Accounts />} />
            <Route path="/app/transactions" element={<Transactions />} />
            <Route path="/app/documents" element={<Documents />} />
            <Route path="/app/goals" element={<Goals />} />
            <Route path="/app/audit" element={<Audit />} />
            <Route path="/app/settings" element={<Settings />} />
            {/* redirects */}
            <Route path="/dashboard" element={<Navigate to="/app" replace />} />
            <Route path="/analysis" element={<Navigate to="/app" replace />} />
            <Route path="/financial-intelligence" element={<Navigate to="/app" replace />} />
            <Route path="/reports" element={<Navigate to="/app/documents" replace />} />
          </Route>

          <Route path="/404" element={<NotFound />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
