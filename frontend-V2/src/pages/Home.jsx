import React, { useRef } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, FileUp, LineChart, ShieldAlert, Landmark, TrendingDown, MessageSquare } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import SplitFlap from '../components/Common/SplitFlap';

const features = [
  { icon: LineChart, title: 'Financial Analysis', description: 'Upload documents and run full financial health analysis covering revenue, expenses, margins, and cash flow.' },
  { icon: TrendingDown, title: 'Cash Flow Forecast', description: 'Project monthly burn rate and runway months to plan ahead with confidence.' },
  { icon: ShieldAlert, title: 'Risk Alerts', description: 'Detect financial risks automatically with risk scores and severity levels.' },
  { icon: Landmark, title: 'Loan Readiness', description: 'Get a loan readiness score out of 100 to assess financing eligibility.' },
  { icon: FileUp, title: 'Document Upload', description: 'Upload financial statements and source documents for secure processing.' },
  { icon: MessageSquare, title: 'AI CFO Chat', description: 'Ask follow-up questions about your reports with AgentCFO financial advisory chat.' },
];

const steps = [
  { number: '01', title: 'Upload Documents', description: 'Upload your financial statements and source documents.' },
  { number: '02', title: 'Run Analysis', description: 'Select processing mode and run a full financial analysis.' },
  { number: '03', title: 'Review Report', description: 'View your report with charts, scores, and recommendations.' },
];

const ticker = ['Revenue', 'Expenses', 'Gross margin', 'Burn rate', 'Runway', 'Risk score', 'Loan readiness', 'Cash position'];

function SectionLabel({ index, children }) {
  return (
    <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
      <span className="text-[var(--primary-accent)]">{index}</span>
      <span className="h-px w-8 bg-[var(--border-color)]" />
      <span>{children}</span>
    </div>
  );
}

function PrimaryCta({ to, children }) {
  return (
    <Link
      to={to}
      className="btn-primary inline-flex items-center justify-center gap-2 px-6 py-3 text-xs font-medium uppercase tracking-[0.15em]"
    >
      {children}
      <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
    </Link>
  );
}

function SecondaryCta({ to, children }) {
  return (
    <Link
      to={to}
      className="btn-outline inline-flex items-center justify-center px-6 py-3 text-xs font-medium uppercase tracking-[0.15em]"
    >
      {children}
    </Link>
  );
}

function FeatureGrid() {
  const gridRef = useRef(null);

  const handleMove = (e) => {
    const card = e.currentTarget;
    const rect = card.getBoundingClientRect();
    card.style.setProperty('--mx', `${e.clientX - rect.left}px`);
    card.style.setProperty('--my', `${e.clientY - rect.top}px`);
  };

  return (
    <div
      ref={gridRef}
      className="grid grid-cols-1 border-l border-t border-[var(--border-color)] md:grid-cols-2 lg:grid-cols-3"
    >
      {features.map(({ icon: Icon, title, description }, idx) => (
        <article
          key={title}
          onMouseMove={handleMove}
          className="group relative overflow-hidden border-b border-r border-[var(--border-color)] p-8"
        >
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
            style={{
              background:
                'radial-gradient(240px circle at var(--mx, 50%) var(--my, 50%), rgba(255,90,31,0.14), transparent 70%)',
            }}
          />
          <div className="relative flex h-full flex-col gap-10">
            <div className="flex items-start justify-between">
              <Icon className="h-5 w-5 text-[var(--primary-accent)]" aria-hidden="true" />
              <span className="text-[11px] tracking-[0.2em] text-[var(--text-muted)]">
                {String(idx + 1).padStart(2, '0')}
              </span>
            </div>
            <div>
              <h3 className="mb-3 text-3xl text-[var(--text-primary)]">{title}</h3>
              <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">{description}</p>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

const Home = () => {
  const { isAuthenticated } = useAuth();

  return (
    <div className="-mx-6 flex flex-col bg-[var(--bg-color)] text-[var(--text-primary)]">
      {/* Hero */}
      <section className="grid-backdrop relative border-b border-[var(--border-color)]">
        <div className="mx-auto flex max-w-[1280px] flex-col gap-12 px-6 pb-20 pt-16 md:pb-28 md:pt-24">
          <div className="flex flex-wrap items-center justify-between gap-4 text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
            <span className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 bg-[var(--primary-accent)]" aria-hidden="true" />
              Financial intelligence platform
            </span>
            <span>For modern SMEs</span>
          </div>

          <h1 className="flex flex-col gap-4 leading-none">
            <span className="text-[13vw] text-[var(--text-primary)] md:text-[8.5rem]">Know your</span>
            <SplitFlap
              words={['Cashflow', 'Runway', 'Risk', 'Margins', 'Burn']}
              tileClassName="h-[14vw] w-[10vw] text-[11vw] md:h-[8.5rem] md:w-[6rem] md:text-[7rem]"
            />
          </h1>

          <div className="flex flex-col gap-10 border-t border-[var(--border-color)] pt-10 md:flex-row md:items-end md:justify-between">
            <p className="max-w-xl text-pretty text-base leading-relaxed text-[var(--text-secondary)]">
              Turn financial documents into clear insights. Analyze cash flow, detect risks, and get CFO-level
              guidance for your business<span className="blink text-[var(--primary-accent)]">_</span>
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              {isAuthenticated ? (
                <PrimaryCta to="/dashboard">Go to Dashboard</PrimaryCta>
              ) : (
                <>
                  <PrimaryCta to="/register">Get Started</PrimaryCta>
                  <SecondaryCta to="/login">Login</SecondaryCta>
                </>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Ticker */}
      <div className="overflow-hidden border-b border-[var(--border-color)] py-4" aria-hidden="true">
        <div className="marquee-track">
          {[...ticker, ...ticker].map((item, i) => (
            <span key={i} className="flex items-center gap-6 px-6 text-[11px] uppercase tracking-[0.25em] text-[var(--text-muted)]">
              {item}
              <span className="text-[var(--primary-accent)]">/</span>
            </span>
          ))}
        </div>
      </div>

      {/* Capabilities */}
      <section className="mx-auto w-full max-w-[1280px] px-6 py-24">
        <div className="mb-14 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-col gap-5">
            <SectionLabel index="01">Capabilities</SectionLabel>
            <h2 className="text-balance text-5xl md:text-7xl">Everything you need to run financial intelligence</h2>
          </div>
          <p className="max-w-sm text-[13px] leading-relaxed text-[var(--text-secondary)]">
            Six instruments, one control panel. Hover a module to inspect it.
          </p>
        </div>
        <FeatureGrid />
      </section>

      {/* How it works */}
      <section className="border-y border-[var(--border-color)]">
        <div className="mx-auto w-full max-w-[1280px] px-6 py-24">
          <div className="mb-14 flex flex-col gap-5">
            <SectionLabel index="02">How it works</SectionLabel>
            <svg viewBox="0 0 1200 140" className="stroke-draw h-auto w-full" role="img" aria-label="Documents to decisions">
              <text x="0" y="118" fontFamily="Bebas Neue, sans-serif" fontSize="150" letterSpacing="2">
                DOCUMENTS TO DECISIONS
              </text>
            </svg>
          </div>
          <ol className="grid grid-cols-1 gap-px bg-[var(--border-color)] md:grid-cols-3">
            {steps.map((step) => (
              <li key={step.number} className="flex flex-col gap-8 bg-[var(--bg-color)] p-8">
                <span className="font-display text-6xl text-[var(--primary-accent)]">{step.number}</span>
                <div>
                  <h3 className="mb-3 text-3xl">{step.title}</h3>
                  <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Processing modes */}
      <section className="mx-auto w-full max-w-[1280px] px-6 py-24">
        <div className="mb-14 flex flex-col gap-5">
          <SectionLabel index="03">Processing modes</SectionLabel>
          <h2 className="text-5xl md:text-7xl">Cloud or local. Your call.</h2>
        </div>
        <div className="grid grid-cols-1 gap-px bg-[var(--border-color)] md:grid-cols-2">
          {[
            { label: 'AWS Mode', detail: 'Amazon Bedrock Nova agents, Titan embeddings, Sonic TTS' },
            { label: 'Local Mode', detail: 'Local sklearn classifier/analyzer + Ollama chat' },
          ].map((m) => (
            <div key={m.label} className="flex flex-col gap-4 bg-[var(--bg-color)] p-8">
              <span className="text-[11px] uppercase tracking-[0.2em] text-[var(--primary-accent)]">{m.label}</span>
              <p className="text-lg leading-relaxed text-[var(--text-primary)]">{m.detail}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-[var(--border-color)] bg-[var(--primary-accent)] text-[#0a0a0a]">
        <div className="mx-auto flex max-w-[1280px] flex-col gap-10 px-6 py-20 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-col gap-4">
            <span className="text-[11px] uppercase tracking-[0.2em]">Join teams using CASHFLOW</span>
            <h2 className="text-6xl leading-none md:text-8xl">Ready to get started?</h2>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            {isAuthenticated ? (
              <Link to="/dashboard" className="inline-flex items-center justify-center gap-2 bg-[#0a0a0a] px-6 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[var(--text-primary)] transition-opacity hover:opacity-85">
                Open Dashboard <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            ) : (
              <>
                <Link to="/register" className="inline-flex items-center justify-center gap-2 bg-[#0a0a0a] px-6 py-3 text-xs font-medium uppercase tracking-[0.15em] text-[var(--text-primary)] transition-opacity hover:opacity-85">
                  Create Account <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
                </Link>
                <Link to="/login" className="inline-flex items-center justify-center border border-[#0a0a0a] px-6 py-3 text-xs font-medium uppercase tracking-[0.15em] transition-colors hover:bg-[#0a0a0a] hover:text-[var(--text-primary)]">
                  Sign In
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--border-color)]">
        <div className="mx-auto max-w-[1280px] px-6 pt-16">
          <div className="grid grid-cols-1 gap-10 pb-12 md:grid-cols-4">
            <div className="md:col-span-2">
              <p className="max-w-xs text-[13px] leading-relaxed text-[var(--text-muted)]">
                Financial intelligence platform for SMEs. Turn documents into decisions.
              </p>
            </div>
            <nav aria-label="Product">
              <h4 className="mb-4 text-[11px] uppercase tracking-[0.2em] text-[var(--text-primary)]">Product</h4>
              <ul className="flex flex-col gap-2 text-[13px]">
                {[['/dashboard', 'Dashboard'], ['/documents', 'Documents'], ['/analysis', 'Analysis'], ['/chat', 'AI CFO'], ['/reports', 'Reports']].map(([to, label]) => (
                  <li key={to}><Link to={to} className="text-[var(--text-muted)] transition-colors hover:text-[var(--primary-accent)]">{label}</Link></li>
                ))}
              </ul>
            </nav>
            <nav aria-label="Legal">
              <h4 className="mb-4 text-[11px] uppercase tracking-[0.2em] text-[var(--text-primary)]">Legal</h4>
              <ul className="flex flex-col gap-2 text-[13px]">
                {[['/privacy', 'Privacy Policy'], ['/terms', 'Terms & Conditions'], ['/login', 'Login']].map(([to, label]) => (
                  <li key={to}><Link to={to} className="text-[var(--text-muted)] transition-colors hover:text-[var(--primary-accent)]">{label}</Link></li>
                ))}
              </ul>
            </nav>
          </div>
          <div aria-hidden="true" className="font-display select-none text-center text-[22vw] leading-[0.8] text-[var(--surface-raised)] md:text-[17rem]">
            CASHFLOW
          </div>
          <div className="flex flex-col items-center justify-between gap-4 border-t border-[var(--border-color)] py-6 text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)] md:flex-row">
            <p>CASHFLOW. All rights reserved.</p>
            <div className="flex items-center gap-6">
              <Link to="/privacy" className="transition-colors hover:text-[var(--primary-accent)]">Privacy</Link>
              <Link to="/terms" className="transition-colors hover:text-[var(--primary-accent)]">Terms</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Home;
