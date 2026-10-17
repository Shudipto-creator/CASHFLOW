import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { getDocuments, getAnalyses, getDashboardCharts } from '../services/api';
import { useNavigate } from 'react-router-dom';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart,
} from 'recharts';
import LoadingSpinner from '../components/Common/LoadingSpinner';

const COLORS = ['#1e3a8a', '#475569', '#64748b', '#94a3b8', '#cbd5e1'];

const formatDate = (iso) => {
  if (!iso) return 'N/A';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'N/A';
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
};

const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    documents: 0,
    analyses: 0,
    latest: null,
  });
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
        if (error.response?.status === 401) {
          setLoadingStats(false);
          return;
        }
        console.error('Failed to fetch stats:', error);
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
        if (err.response?.status === 401) {
          // Don't auto-logout; just clear chart data
          setChartData(null);
          return;
        }
        console.error('Failed to load charts:', err);
      } finally {
        setLoadingCharts(false);
      }
    };

    loadCharts();
  }, [analysisId]);

  const formatSnapshotTime = (timestamp) => {
    if (!timestamp) return 'No runs yet';
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-[var(--border-color)] pb-4 mb-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-wide">CASHFLOW Dashboard</h1>
            <p className="font-mono text-sm text-[var(--text-muted)] tracking-wide uppercase">
              Financial overview for {user?.company_name || 'your company'}
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={() => navigate('/documents')}
              className="btn-secondary px-4 py-2 text-sm font-medium"
            >
              Upload Documents
            </button>
            <button
              onClick={() => navigate('/analysis')}
              className="btn-primary px-4 py-2 text-sm font-medium"
            >
              Run Analysis
            </button>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="surface-card p-6">
          <p className="font-mono text-xs text-[var(--text-muted)] uppercase tracking-wider mb-2">Total Documents</p>
          <p className="text-3xl font-bold text-[var(--text-primary)]">{stats.documents}</p>
          <p className="font-mono text-xs text-[var(--text-secondary)] mt-2">Bank statements and GST reports</p>
        </div>
        <div className="surface-card p-6">
          <p className="font-mono text-xs text-[var(--text-muted)] uppercase tracking-wider mb-2">Total Analyses</p>
          <p className="text-3xl font-bold text-[var(--text-primary)]">{stats.analyses}</p>
          <p className="font-mono text-xs text-[var(--text-secondary)] mt-2">Comprehensive financial reports</p>
        </div>
        <div className="surface-card p-6">
          <p className="font-mono text-xs text-[var(--text-muted)] uppercase tracking-wider mb-2">Latest Status</p>
          <p className="text-3xl font-bold text-[var(--positive-color)]">{stats.latest ? stats.latest.status : 'N/A'}</p>
          <p className="font-mono text-xs text-[var(--text-muted)] mt-2">Last run: {formatSnapshotTime(stats.latest?.completed_at || stats.latest?.created_at)}</p>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Waterfall */}
        <div className="surface-card p-6">
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">Revenue Waterfall</h2>
          {loadingCharts ? (
            <LoadingSpinner size="small" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={chartData?.revenue_waterfall?.items || []}
                  margin={{ top: 20, right: 30, left: 0, bottom: 60 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} angle={-45} textAnchor="end" />
                  <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--bg-color)', border: '1px solid var(--border-color)' }}
                    formatter={(value) => `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
                  />
                  <Bar dataKey="value" fill="var(--primary-accent)">
                    {(chartData?.revenue_waterfall?.items || []).map((item, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="font-mono text-xs text-[var(--text-secondary)] mt-3 uppercase tracking-wider">
                Total Revenue: <span className="text-[var(--primary-accent)] font-bold">${(chartData?.revenue_waterfall?.total || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
              </p>
            </>
          )}
        </div>

        {/* Expense Breakdown */}
        <div className="surface-card p-6">
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">Expense Breakdown</h2>
          {loadingCharts ? (
            <LoadingSpinner size="small" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={chartData?.expense_breakdown || []}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, value }) => `${name}: $${(value / 1000).toFixed(0)}k`}
                    outerRadius={80}
                    fill="var(--primary-accent)"
                    dataKey="value"
                  >
                    {(chartData?.expense_breakdown || []).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`} />
                </PieChart>
              </ResponsiveContainer>
              <p className="font-mono text-xs text-[var(--text-secondary)] mt-3 uppercase tracking-wider">
                Select an analysis to view expense breakdown.
              </p>
            </>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="surface-card p-6">
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">Ingest Documents</h2>
          <p className="font-mono text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
            Import bank statements, GST reports, or Excel sales sheets. All formats processed and indexed for analysis.
          </p>
          <button
            onClick={() => navigate('/documents')}
            className="btn-outline px-4 py-2 text-sm font-medium"
          >
            Select Files
          </button>
        </div>
        <div className="surface-card p-6">
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">Run Analysis</h2>
          <p className="font-mono text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
            Deploy all five AI agents across your documents. Generates a full financial health report with risk flags and forecasts.
          </p>
          <button
            onClick={() => navigate('/analysis')}
            className="btn-primary px-4 py-2 text-sm font-medium"
          >
            Generate Report
          </button>
        </div>
      </div>

      {/* Last Analysis Snapshot */}
      {stats.latest && (
        <div className="surface-card p-6">
          <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">Last Analysis Snapshot</h2>
          <div className="font-mono text-xs text-[var(--text-muted)] space-y-3">
            <div className="flex justify-between">
              <span>Run time</span>
              <span className="text-[var(--text-primary)]">{formatSnapshotTime(stats.latest.completed_at || stats.latest.created_at)}</span>
            </div>
            <div className="flex justify-between">
              <span>Documents used</span>
              <span className="text-[var(--text-primary)]">{stats.latest.document_count ?? 0}</span>
            </div>
            <div className="flex justify-between">
              <span>Report version</span>
              <span className="text-[var(--text-primary)]">
                {stats.latest.analysis_id ? `RPT-${stats.latest.analysis_id.slice(0, 8).toUpperCase()}` : 'N/A'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Status</span>
              <span className="text-[var(--text-primary)] uppercase">{stats.latest.status || 'NOT GENERATED'}</span>
            </div>
          </div>
        </div>
      )}

      {/* Charts notice if no analysis selected */}
      {!analysisId && !loadingCharts && (
        <div className="surface-card p-6 text-center">
          <p className="font-mono text-xs text-[var(--text-muted)]">
            Run an analysis to view detailed charts including revenue, expense breakdown, variance, burn rate, risk score, and loan readiness.
          </p>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
