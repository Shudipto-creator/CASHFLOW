import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ModeProvider } from './context/ModeContext';
import ProtectedRoute from './components/Common/ProtectedRoute';
import ThemeLayout from './components/Layout/ThemeLayout';

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
import Privacy from './pages/Privacy';
import Terms from './pages/Terms';

export default function App() {
  return (
    <AuthProvider>
      <ModeProvider>
        <BrowserRouter>
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
                <ProtectedRoute>
                  <ThemeLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/analysis" element={<Analysis />} />
              <Route path="/report/:analysisId" element={<Report />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/reports" element={<Reports />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ModeProvider>
    </AuthProvider>
  );
}
