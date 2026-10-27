import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { login } from '../services/api';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login: authLogin } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await authLogin(email, password);

    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  return (
    <div className="grid-backdrop min-h-screen flex flex-col items-center justify-center gap-8 bg-[var(--bg-color)] px-6">
      <Link to="/" className="flex items-center gap-2.5"><span className="flex h-6 w-6 items-center justify-center bg-[var(--primary-accent)] font-display text-base leading-none text-[#0a0a0a]">C</span><span className="font-display text-2xl leading-none tracking-wider text-[var(--text-primary)]">CASHFLOW</span></Link>
      <div className="surface-card p-8 w-full max-w-md border border-[var(--border-color)]">
        <h1 className="text-5xl text-[var(--text-primary)] text-center mb-8">Sign in to CASHFLOW</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[11px] uppercase tracking-[0.15em] text-[var(--text-secondary)] mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-[0.15em] text-[var(--text-secondary)] mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              required
            />
          </div>

          {error && (
            <div className="border border-[var(--negative-color)] bg-[rgba(248,113,113,0.08)] text-[var(--negative-color)] px-4 py-2 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3 px-6 text-sm font-medium uppercase tracking-wider disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <p className="text-center mt-6 text-sm text-[var(--text-secondary)]">
          Don't have an account?{' '}
          <Link to="/register" className="text-[var(--primary-accent)] hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Login;
