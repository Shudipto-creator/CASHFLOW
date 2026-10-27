import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useMode } from '../context/ModeContext';
import { getDocuments, getAnalyses, getDashboardCharts } from '../services/api';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { FileText, Activity, CheckCircle2, Upload, Play, MessageSquare, ArrowUpRight } from 'lucide-react';
import LoadingSpinner from '../components/Common/LoadingSpinner';
import PageHeader from '../components/Common/PageHeader';

const COLORS = ['#ff5a1f', '#ededea', '#a3a3a0', '#6b6b68', '#3a3a3a'];

const tooltipStyle = {
  backgroundColor: '#111111',
  border: '1px solid #262626',
  borderRadius: 6,
  fontFamily: 'IBM Plex Mono, monospace',
  fontSize: 12,
};

const formatMoney = (value) =>
  `$${Number(value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;

const formatSnapshotTime = (timestamp) => {
  if (!timestamp) return 'No runs yet';
  const d = new Date(timestamp);
  return Number.isNaN(d.getTime()) ? 'No runs yet' : d.toLocaleString();
};

function StatTile({ label, value, hint, icon: Icon, tone = 'default' }) {
  const valueColor =
    tone === 'accent'
      ? 'text-[var(--primary-accent)]'
      : tone === 'positive'
        ? 'text-[var(--positive-color)]'
        : tone === 'negative'
          ? 'text-[var(--negative-color)]'
          : 'text-[var(--text-primary)]';
  return (
    <div className="surface-card stripes flex flex-col justify-between gap-6 p-5">
      <div className="flex items-start justify-between">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">{label}</p>
        <span className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--border-color)] text-[var(--text-secondary)]">
          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
      </div>
      <div>
        <p className={`font-display text-6xl leading-none uppercase ${valueColor}`}>{value}</p>
        <p className="mt-2 text-[11px] text-[var(--text-muted)]">{hint}</p>
      </div>
    </div>
  );
}

function EmptyChart({ message }) {
  return (
    <div className="flex h-[240px] items-center justify-center rounded-md border border-dashed border-[var(--border-color)] px-6 text-center">
      <p className="text-[11px] uppercase tracking-[0.15em] text-[var(--text-muted)]">{message}</p>
    </div>
  );
}

const Dashboard = () => {
  const { user } = useAuth();
  const { mode } = useMode();
  const navigate = useNavigate();
  const [stats, setStats] = useState({ documents: 0, analyses: 0, latest: null });
  const [chartData, setChartData] = useState(null);
  const [loadingCharts, setLoadingCharts] = useState(false);
  const [loadingStats, setLoadingStats] = useState(true);

  const analysisId = localStorage.getItem('lastAnalysisId');

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [docsRes, analysesRes] = await Promise.all([
          getDocuments({ limit: 1 }),
          getAnalyses({ limit: 1 }),
        ]);
        setStats({
          documents: docsRes.data.total || 0,
          analyses: analysesRes.data.total || 0,
          latest: analysesRes.data.analyses?.[0] || null,
        });
      } catch (error) {
        if (error.response?.status !== 401) console.error('Failed to fetch stats:', error);
      } finally {
        setLoadingStats(false);
      }
    };
    fetchStats();
  }, []);

  useEffect(() => {
    if (!analysisId) return;
    const loadCharts = async () => {
      setLoadingCharts(true);
      try {
        const res = await getDashboardCharts(analysisId);
        setChartData(res.data);
      } catch (err) {
        setChartData(null);
        if (err.response?.status !== 401) console.error('Failed to load charts:', err);
      } finally {
        setLoadingCharts(false);
      }
    };
    loadCharts();
  }, [analysisId]);

  const waterfall = chartData?.revenue_waterfall?.items || [];
  const expenses = chartData?.expense_breakdown || [];
  const expenseTotal = expenses.reduce((sum, e) => sum + (Number(e.value) || 0), 0);
  const latest = stats.latest;
  const latestStatus = latest?.status || 'N/A';
  const statusTone =
    latestStatus === 'completed' ? 'positive' : latestStatus === 'failed' ? 'negative' : 'default';
  const openReportId = analysisId || latest?.analysis_id;

  return (
    <div>
      <PageHeader
        eyebrow={`Live · ${mode === 'local' ? 'Local' : 'AWS'} mode`}
        title="Overview"
        description={`Financial command center for ${user?.company_name || 'your company'}`}
        actions={
          <>
            <button onClick={() => navigate('/documents')} className="btn-outline flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-[0.15em]">
              <Upload className="h-3.5 w-3.5" aria-hidden="true" />
              Upload
            </button>
            <button onClick={() => navigate('/analysis')} className="btn-primary flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-[0.15em]">
              <Play className="h-3.5 w-3.5" aria-hidden="true" />
              Run Analysis
            </button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_320px]">
        <div className="flex min-w-0 flex-col gap-6">
          <section aria-label="Key metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatTile
              label="Documents"
              value={loadingStats ? '--' : stats.documents}
              hint="Bank statements, GST and sales sheets"
              icon={FileText}
            />
            <StatTile
              label="Analyses"
              value={loadingStats ? '--' : stats.analyses}
              hint="Five-agent financial health reports"
              icon={Activity}
              tone="accent"
            />
            <StatTile
              label="Latest status"
              value={loadingStats ? '--' : latestStatus}
              hint={`Last run: ${formatSnapshotTime(latest?.completed_at || latest?.created_at)}`}
              icon={CheckCircle2}
              tone={statusTone}
            />
          </section>

          <section aria-label="Charts" className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="surface-card p-5">
              <h2 className="panel-title">Revenue Waterfall</h2>
              {loadingCharts ? (
                <div className="flex h-[240px] items-center justify-center"><LoadingSpinner size="medium" /></div>
              ) : waterfall.length === 0 ? (
                <EmptyChart message={analysisId ? 'No revenue data in this analysis' : 'Run an analysis to see revenue'} />
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={waterfall} margin={{ top: 10, right: 10, left: 0, bottom: 50 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
                    <XAxis dataKey="name" tick={{ fill: '#a3a3a0', fontSize: 10 }} angle={-35} textAnchor="end" interval={0} stroke="#262626" />
                    <YAxis tick={{ fill: '#a3a3a0', fontSize: 10 }} stroke="#262626" tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                    <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,90,31,0.08)' }} formatter={(value) => formatMoney(value)} />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {waterfall.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
              <div className="mt-4 flex items-baseline justify-between border-t border-[var(--border-color)] pt-3">
                <span className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Total revenue</span>
                <span className="font-display text-3xl leading-none text-[var(--primary-accent)]">
                  {formatMoney(chartData?.revenue_waterfall?.total)}
                </span>
              </div>
            </div>

            <div className="surface-card p-5">
              <h2 className="panel-title">Expense Breakdown</h2>
              {loadingCharts ? (
                <div className="flex h-[240px] items-center justify-center"><LoadingSpinner size="medium" /></div>
              ) : expenses.length === 0 ? (
                <EmptyChart message={analysisId ? 'No expense data in this analysis' : 'Run an analysis to see expenses'} />
              ) : (
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                  <div className="h-[200px] w-full sm:w-1/2">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={expenses} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2} stroke="none">
                          {expenses.map((_, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={tooltipStyle} formatter={(value) => formatMoney(value)} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <ul className="flex flex-1 flex-col gap-2">
                    {expenses.slice(0, 6).map((e, index) => (
                      <li key={e.name ?? index} className="flex items-center justify-between gap-3 text-[11px]">
                        <span className="flex min-w-0 items-center gap-2">
                          <span aria-hidden="true" className="h-2 w-2 shrink-0" style={{ background: COLORS[index % COLORS.length] }} />
                          <span className="truncate text-[var(--text-secondary)]">{e.name}</span>
                        </span>
                        <span className="tabular-nums text-[var(--text-primary)]">
                          {expenseTotal ? `${Math.round((Number(e.value) / expenseTotal) * 100)}%` : formatMoney(e.value)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mt-4 flex items-baseline justify-between border-t border-[var(--border-color)] pt-3">
                <span className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Total expenses</span>
                <span className="font-display text-3xl leading-none text-[var(--text-primary)]">{formatMoney(expenseTotal)}</span>
              </div>
            </div>
          </section>

          <section aria-label="Quick actions" className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {[
              { title: 'Ingest Documents', body: 'Import bank statements, GST reports or Excel sales sheets.', to: '/documents', icon: Upload },
              { title: 'Run Analysis', body: 'Deploy all five AI agents for a full health report.', to: '/analysis', icon: Play },
              { title: 'Ask AI CFO', body: 'Question your latest report in plain language.', to: openReportId ? `/chat?analysis_id=${encodeURIComponent(openReportId)}` : '/chat', icon: MessageSquare },
            ].map(({ title, body, to, icon: Icon }) => (
              <button
                key={title}
                onClick={() => navigate(to)}
                className="surface-card group flex flex-col gap-4 p-5 text-left transition-colors hover:border-[var(--primary-accent)]"
              >
                <span className="flex items-center justify-between">
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-[var(--surface-raised)] text-[var(--primary-accent)]">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <ArrowUpRight className="h-4 w-4 text-[var(--text-muted)] transition-colors group-hover:text-[var(--primary-accent)]" aria-hidden="true" />
                </span>
                <span>
                  <span className="block text-xs uppercase tracking-[0.15em] text-[var(--text-primary)]">{title}</span>
                  <span className="mt-1.5 block text-[11px] leading-relaxed text-[var(--text-muted)]">{body}</span>
                </span>
              </button>
            ))}
          </section>
        </div>

        <aside aria-label="Last analysis" className="flex flex-col gap-6">
          <div className="surface-card p-5">
            <h2 className="panel-title">Last Analysis</h2>
            {latest ? (
              <>
                <dl className="flex flex-col gap-3 text-[11px]">
                  {[
                    ['Report', latest.analysis_id ? `RPT-${latest.analysis_id.slice(0, 8).toUpperCase()}` : 'N/A'],
                    ['Run time', formatSnapshotTime(latest.completed_at || latest.created_at)],
                    ['Documents', latest.document_count ?? 0],
                    ['Status', (latest.status || 'Not generated').toUpperCase()],
                  ].map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between gap-3">
                      <dt className="uppercase tracking-[0.15em] text-[var(--text-muted)]">{k}</dt>
                      <dd className="truncate text-right text-[var(--text-primary)]">{v}</dd>
                    </div>
                  ))}
                </dl>
                {latest.analysis_id && (
                  <button
                    onClick={() => navigate(`/report/${latest.analysis_id}`)}
                    className="btn-outline mt-5 w-full px-4 py-2 text-xs uppercase tracking-[0.15em]"
                  >
                    Open Report
                  </button>
                )}
              </>
            ) : (
              <p className="text-[11px] leading-relaxed text-[var(--text-muted)]">
                {loadingStats ? 'Loading…' : 'No analysis yet. Upload documents and run your first analysis.'}
              </p>
            )}
          </div>

          <div className="surface-card p-5">
            <h2 className="panel-title">Agent Pipeline</h2>
            <ol className="flex flex-col gap-3">
              {['Document classifier', 'Cashflow analyzer', 'Risk detector', 'Forecaster', 'CFO reporter'].map((agent, i) => (
                <li key={agent} className="flex items-center gap-3 text-[11px]">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-[var(--border-color)] tabular-nums text-[var(--text-muted)]">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="flex-1 text-[var(--text-secondary)]">{agent}</span>
                  <span
                    aria-label={latestStatus === 'completed' ? 'Done' : 'Idle'}
                    className={`h-1.5 w-1.5 rounded-full ${latestStatus === 'completed' ? 'bg-[var(--positive-color)]' : 'bg-[var(--text-muted)]'}`}
                  />
                </li>
              ))}
            </ol>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default Dashboard;
