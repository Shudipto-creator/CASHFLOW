import React from 'react';
import { Link } from 'react-router-dom';

export default function Landing() {
  return (
    <div style={{ background: 'var(--color-bg)', color: 'var(--color-text)', minHeight: '100vh' }}>
      <header className="flex items-center justify-between p-6" style={{ maxWidth: 1280, margin: '0 auto' }}>
        <div style={{ fontFamily: 'var(--font-serif)', letterSpacing: '0.08em', fontWeight: 600 }}>CASHFLOW</div>
        <div className="flex gap-4">
          <Link to="/security">Security</Link>
          <Link to="/login">Log in</Link>
          <Link to="/signup" className="btn btn-primary">Create account</Link>
        </div>
      </header>
      <section style={{ padding: '64px 24px', textAlign: 'center' }}>
        <h1 style={{ fontFamily: 'var(--font-serif)', fontSize: 40, margin: 0 }}>Know your cash position 13 weeks ahead.</h1>
        <p style={{ maxWidth: 640, margin: '16px auto', fontSize: 16, color: 'var(--color-muted)' }}>
          Import your invoices and bank statements. CASHFLOW forecasts your cash, flags a shortfall early, and compares financing options by what they really cost. Nothing moves without your approval.
        </p>
        <div className="flex gap-4 justify-center mt-6">
          <Link to="/signup" className="btn btn-primary">Create account</Link>
          <Link to="#how" className="btn btn-secondary">See how it works</Link>
        </div>
        <p style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 16 }}>Demo data</p>
      </section>
      <section id="how" style={{ padding: 48, textAlign: 'center' }}>
        <h2 style={{ fontFamily: 'var(--font-serif)' }}>How it works</h2>
        <div className="flex gap-6 justify-center flex-wrap" style={{ marginTop: 24 }}>
          <div className="card" style={{ width: 240 }}>1. Import bank statements and invoices.</div>
          <div className="card" style={{ width: 240 }}>2. Review extracted data before saving.</div>
          <div className="card" style={{ width: 240 }}>3. Approve any drafted action.</div>
        </div>
      </section>
      <footer style={{ textAlign: 'center', padding: 24, color: 'var(--color-muted)', fontSize: 12 }}>
        <p>(c) 2026 CASHFLOW</p>
      </footer>
    </div>
  );
}
