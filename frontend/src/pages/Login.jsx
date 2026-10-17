import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { login, getCsrf } from '../services/api';

export default function Login() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await getCsrf();
      const res = await login(email, password);
      setUser(res.data ? { id: res.data.user_id, email: res.data.email, organization_id: res.data.organization_id } : null);
      navigate('/app');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--color-bg)' }}>
      <form onSubmit={submit} className="card" style={{ width: 400, padding: 32 }}>
        <h1 className="font-serif mb-4" style={{ fontFamily: 'var(--font-serif)' }}>Log in</h1>
        {error && <div style={{ color: 'var(--color-danger)', marginBottom: 12 }}>{error}</div>}
        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <div style={{ height: 8 }} />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <div style={{ height: 16 }} />
        <button className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>{loading ? 'Signing in' : 'Log in'}</button>
      </form>
    </div>
  );
}
