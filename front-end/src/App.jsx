import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ModeProvider } from './context/ModeContext';
import ProtectedRoute from './components/Common/ProtectedRoute';
import ErrorBoundary from './components/Common/ErrorBoundary';
import ThemeLayout from './components/Layout/ThemeLayout';
import DashboardLayout from './components/Layout/DashboardLayout';

// Pages
import Login from './pages/Login';
import Register from './pages/Register';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import Documents from './pages/Documents';
import Analysis from './pages/Analysis';
import Report from './pages/Report';
import Chat from './pages/Chat';
import Reports from './pages/Reports';
import Billing from './pages/Billing';
import Banking from './pages/Banking';
import Security from './pages/Security';
import FXConvert from './pages/FXConvert';
import Privacy from './pages/Privacy';
import Terms from './pages/Terms';

export default function App() {
  return (
    <AuthProvider>
      <ModeProvider>
        <BrowserRouter v7_startTransition v7_relativeSplatPath>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/terms" element={<Terms />} />

            <Route element={<ThemeLayout />}>
              <Route path="/" element={<Home />} />
            </Route>

            <Route
              element={
                <ErrorBoundary fallback={<div />}>
                  <ProtectedRoute>
                    <DashboardLayout />
                  </ProtectedRoute>
                </ErrorBoundary>
              }
            >
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/analysis" element={<Analysis />} />
              <Route path="/report/:analysisId" element={<Report />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/billing" element={<Billing />} />
              <Route path="/banking" element={<Banking />} />
              <Route path="/security" element={<Security />} />
              <Route path="/fx-convert" element={<FXConvert />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ModeProvider>
    </AuthProvider>
  );
}
