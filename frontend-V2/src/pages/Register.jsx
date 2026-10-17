import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { register } from '../services/api';

const Register = () => {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    company_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      await register({
        email: formData.email,
        password: formData.password,
        company_name: formData.company_name,
      });

      navigate('/login', { state: { message: 'Registration successful. Please sign in.' } });
    } catch (err) {
      console.error('Registration error:', err.response?.data);

      let errorMessage = 'Registration failed';

      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          errorMessage = err.response.data.detail
            .map(e => `${e.loc.join('.')}: ${e.msg}`)
            .join(', ');
        } else if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
        }
      } else if (err.response?.data?.message) {
        errorMessage = err.response.data.message;
      } else if (err.message) {
        errorMessage = err.message;
      }

      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid-backdrop min-h-screen flex flex-col items-center justify-center gap-8 bg-[var(--bg-color)] px-6">
      <Link to="/" className="flex items-center gap-2.5"><span className="flex h-6 w-6 items-center justify-center bg-[var(--primary-accent)] font-display text-base leading-none text-[#0a0a0a]">C</span><span className="font-display text-2xl leading-none tracking-wider text-[var(--text-primary)]">CASHFLOW</span></Link>
      <div className="surface-card p-8 w-full max-w-md border border-[var(--border-color)]">
        <h1 className="text-5xl text-[var(--text-primary)] text-center mb-8">Create a CASHFLOW account</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[11px] uppercase tracking-[0.15em] text-[var(--text-secondary)] mb-2">Email</label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className="input-field"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-[0.15em] text-[var(--text-secondary)] mb-2">Company Name</label>
            <input
              type="text"
              name="company_name"
              value={formData.company_name}
              onChange={handleChange}
              className="input-field"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-[0.15em] text-[var(--text-secondary)] mb-2">Password</label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className="input-field"
              required
            />
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Must be at least 8 characters with uppercase, lowercase, and number.
            </p>
          </div>

          <div>
            <label className="block text-[11px] uppercase tracking-[0.15em] text-[var(--text-secondary)] mb-2">Confirm Password</label>
            <input
              type="password"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
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
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <p className="text-center mt-6 text-sm text-[var(--text-secondary)]">
          Already have an account?{' '}
          <Link to="/login" className="text-[var(--primary-accent)] hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Register;
