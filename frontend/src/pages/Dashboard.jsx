import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function Dashboard() {
  const { user } = useAuth();
  const [org, setOrg] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/organizations/me', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then(setOrg)
      .catch(() => setError('Could not load organization'));
  }, []);

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontFamily: 'var(--font-serif)' }}>Welcome back, {user?.first_name || user?.email}</h1>
      <p style={{ color: 'var(--color-muted)' }}>
        {org ? `Organization: ${org.name} (${org.base_currency})` : 'Loading organization'}
      </p>
      {error && <div style={{ color: 'var(--color-danger)' }}>{error}</div>}
      <div className="card" style={{ marginTop: 16 }}>No data yet. Import your first document to get started.</div>
    </div>
  );
}
