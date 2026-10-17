import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div style={{ padding: 24 }}>Loading</div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}
