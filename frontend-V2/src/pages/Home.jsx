import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Home = () => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const features = [
    {
      title: 'Financial Analysis',
      description: 'Upload documents and run full financial health analysis covering revenue, expenses, margins, and cash flow.',
    },
    {
      title: 'Cash Flow Forecast',
      description: 'Project monthly burn rate and runway months to plan ahead with confidence.',
    },
    {
      title: 'Risk Alerts',
      description: 'Detect financial risks automatically with risk scores and severity levels.',
    },
    {
      title: 'Loan Readiness',
      description: 'Get a loan readiness score out of 100 to assess financing eligibility.',
    },
    {
      title: 'Document Upload',
      description: 'Upload financial statements and source documents for secure processing.',
    },
    {
      title: 'AI CFO Chat',
      description: 'Ask follow-up questions about your reports with AgentCFO financial advisory chat.',
    },
  ];

  const steps = [
    { number: '01', title: 'Upload Documents', description: 'Upload your financial statements and source documents.' },
    { number: '02', title: 'Run Analysis', description: 'Select processing mode and run a full financial analysis.' },
    { number: '03', title: 'Review Report', description: 'View your report with charts, scores, and recommendations.' },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg-color)] text-[var(--text-primary)]">
      <section className="max-w-[1280px] mx-auto px-6 py-20 text-center">
        <div className="inline-flex items-center space-x-2 px-3 py-1 border border-[var(--border-color)] rounded-sm mb-6">
          <span className="font-mono text-[10px] text-[var(--text-muted)] uppercase tracking-widest">Platform</span>
          <span className="w-px h-2 bg-[var(--border-color)]"></span>
          <span className="font-mono text-[10px] text-[var(--text-muted)] uppercase tracking-widest">SaaS</span>
        </div>
        <h1 className="text-4xl md:text-5xl font-bold tracking-wider mb-6">
          Financial intelligence for modern SMEs
        </h1>
        <p className="text-lg md:text-xl text-[var(--text-secondary)] max-w-2xl mx-auto mb-10 leading-relaxed font-mono">
          Turn financial documents into clear insights. Analyze cash flow, detect risks, and get CFO-level guidance for your business.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          {isAuthenticated ? (
            <Link
              to="/dashboard"
              className="px-6 py-3 bg-[var(--primary-accent)] text-white rounded-sm text-sm font-medium uppercase tracking-wider hover:bg-[#153575] transition-colors"
            >
              Go to Dashboard
            </Link>
          ) : (
            <>
              <Link
                to="/register"
                className="px-6 py-3 bg-[var(--primary-accent)] text-white rounded-sm text-sm font-medium uppercase tracking-wider hover:bg-[#153575] transition-colors"
              >
                Get Started
              </Link>
              <Link
                to="/login"
                className="px-6 py-3 border border-[var(--border-color)] rounded-sm text-sm font-medium uppercase tracking-wider text-[var(--text-primary)] hover:bg-[var(--surface-card)] transition-colors"
              >
                Login
              </Link>
            </>
          )}
        </div>
      </section>

      <section className="border-t border-[var(--border-color)] border-b border-[var(--border-color)] py-20">
        <div className="max-w-[1280px] mx-auto px-6">
          <div className="text-center mb-14">
            <h2 className="text-2xl font-bold tracking-wider mb-4">Capabilities</h2>
            <p className="text-[var(--text-muted)] font-mono text-sm uppercase tracking-widest">
              Everything you need to run financial intelligence
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {features.map((feature, idx) => (
              <div key={idx} className="surface-card p-6">
                <div className="w-10 h-10 flex items-center justify-center border border-[var(--border-color)] rounded-sm mb-4 text-[var(--primary-accent)] font-bold text-lg">
                  {idx + 1}
                </div>
                <h3 className="font-bold text-[var(--text-primary)] mb-3 tracking-wide">{feature.title}</h3>
                <p className="text-[var(--text-secondary)] font-mono text-xs leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="max-w-[1280px] mx-auto px-6 py-20">
        <div className="text-center mb-14">
          <h2 className="text-2xl font-bold tracking-wider mb-4">How it works</h2>
          <p className="text-[var(--text-muted)] font-mono text-sm uppercase tracking-widest">
            From documents to decisions in three steps
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-8">
          {steps.map((step) => (
            <div key={step.number} className="text-center">
              <div className="flex items-center justify-center w-10 h-10 border border-[var(--primary-accent)] rounded-sm text-[var(--primary-accent)] font-bold mb-4">
                {step.number}
              </div>
              <h3 className="font-bold text-[var(--text-primary)] mb-3 tracking-wide">{step.title}</h3>
              <p className="text-[var(--text-secondary)] font-mono text-xs leading-relaxed">{step.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="py-20 border-t border-[var(--border-color)]">
        <div className="max-w-[1280px] mx-auto px-6">
          <div className="surface-card p-10 text-center border border-[var(--border-color)]">
            <h2 className="text-2xl font-bold text-[var(--text-primary)] tracking-wider mb-4">Ready to get started?</h2>
            <p className="text-[var(--text-secondary)] font-mono text-sm mb-8 uppercase tracking-widest">
              Join teams using CASHFLOW for financial intelligence
            </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="px-6 py-3 bg-[var(--primary-accent)] text-white rounded-sm text-sm font-medium uppercase tracking-wider hover:bg-[#153575] transition-colors"
              >
                Open Dashboard
              </Link>
            ) : (
              <>
                <Link
                  to="/register"
                  className="px-6 py-3 bg-[var(--primary-accent)] text-white rounded-sm text-sm font-medium uppercase tracking-wider hover:bg-[#153575] transition-colors"
                >
                  Create Account
                </Link>
                <Link
                  to="/login"
                  className="px-6 py-3 border border-[var(--border-color)] rounded-sm text-sm font-medium uppercase tracking-wider text-[var(--text-primary)] hover:bg-[var(--surface-card)] transition-colors"
                >
                  Sign In
                </Link>
              </>
            )}
          </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-[var(--border-color)] bg-[var(--surface-card)] py-12">
        <div className="max-w-[1280px] mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center space-x-3 mb-4">
                <div
                  className="w-6 h-6 flex items-center justify-center font-bold text-xs"
                  style={{
                    border: "1px solid var(--primary-accent)",
                    color: "var(--primary-accent)",
                    backgroundColor: "var(--bg-color)",
                  }}
                >
                  C
                </div>
                <span className="font-bold tracking-widest text-sm">CASHFLOW</span>
              </div>
              <p className="text-[var(--text-muted)] font-mono text-xs leading-relaxed mb-4">
                Financial intelligence platform for SMEs. Turn documents into decisions.
              </p>
            </div>
            <div>
              <h4 className="font-bold text-[var(--text-primary)] mb-4 tracking-wider uppercase text-[10px] font-mono">Product</h4>
              <ul className="space-y-2">
                <li><Link to="/dashboard" className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-xs">Dashboard</Link></li>
                <li><Link to="/documents" className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-xs">Documents</Link></li>
                <li><Link to="/analysis" className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-xs">Analysis</Link></li>
                <li><Link to="/chat" className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-xs">AI CFO</Link></li>
                <li><Link to="/reports" className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-xs">Reports</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold text-[var(--text-primary)] mb-4 tracking-wider uppercase text-[10px] font-mono">Legal</h4>
              <ul className="space-y-2">
                <li><Link to="/privacy" className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-xs">Privacy Policy</Link></li>
                <li><Link to="/terms" className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-xs">Terms &amp; Conditions</Link></li>
                <li><Link to="/login" className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-xs">Login</Link></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-[var(--border-color)] pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-[var(--text-muted)] font-mono text-[10px] uppercase tracking-widest">
              CASHFLOW. All rights reserved.
            </p>
            <div className="flex items-center space-x-6 font-mono text-[10px] uppercase tracking-widest text-[var(--text-muted)]">
              <Link to="/privacy" className="hover:text-[var(--primary-accent)] transition-colors">Privacy</Link>
              <Link to="/terms" className="hover:text-[var(--primary-accent)] transition-colors">Terms</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Home;
