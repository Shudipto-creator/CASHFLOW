import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart } from 'recharts';
import { getDashboardCharts, generateDashboardInsights } from '../services/api';
import LoadingSpinner from '../components/Common/LoadingSpinner';

/**
 * Financial Intelligence Dashboard
 * Uses existing CFONE color scheme and typography
 */
const FinancialIntelligence = () => {
  const navigate = useNavigate();
  const [chartData, setChartData] = useState(null);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [isDark, setIsDark] = useState(!document.documentElement.classList.contains('light'));

  // Get analysis ID from URL or session
  const analysisId = localStorage.getItem('lastAnalysisId');

  // Detect theme changes
  useEffect(() => {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          setIsDark(!document.documentElement.classList.contains('light'));
        }
      });
    });
    
    observer.observe(document.documentElement, { attributes: true });
    
    return () => observer.disconnect();
  }, []);

  // Theme-aware colors for charts
  const chartColors = {
    dark: {
      lineStroke: '#f59e0b',
      gridStroke: '#374151',
      textColor: '#e5e7eb',
      riskStroke: '#ef4444',
      loanStroke: '#10b981',
    },
    light: {
      lineStroke: '#d97706',
      gridStroke: '#d1d5db',
      textColor: '#1f2937',
      riskStroke: '#dc2626',
      loanStroke: '#059669',
    }
  };

  const colors = isDark ? chartColors.dark : chartColors.light;

  useEffect(() => {
    if (!analysisId) {
      navigate('/documents');
      return;
    }
    loadDashboard();
  }, [analysisId]);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch chart data
      const chartsResponse = await getDashboardCharts(analysisId);
      setChartData(chartsResponse.data);

      // Generate AI insights
      try {
        const insightsResponse = await generateDashboardInsights({
          analysis_id: analysisId,
          chart_data: chartsResponse.data,
        });
        // axios wraps response in .data property
        const insightsData = insightsResponse.data;
        
        // Validate the response structure
        if (insightsData && (insightsData.top_insights || insightsData.risks || insightsData.recommendations)) {
          setInsights(insightsData);
        } else {
          console.warn('Invalid insights response structure:', insightsData);
        }
      } catch (insightErr) {
        console.error('Failed to generate insights:', insightErr?.response?.data || insightErr?.message || insightErr);
        // Continue without insights
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load dashboard');
      console.error('Dashboard load error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <div className="surface-card p-10 border border-[var(--negative-color)]">
        <h2 className="font-display text-2xl text-[var(--negative-color)] mb-4">Error Loading Dashboard</h2>
        <p className="font-mono text-sm text-[var(--text-secondary)] mb-6">{error}</p>
        <button
          onClick={() => navigate('/documents')}
          className="px-4 py-2 border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--text-primary)] transition-colors font-mono text-xs uppercase tracking-widest rounded-sm"
        >
          Back to Documents
        </button>
      </div>
    );
  }

  if (!chartData) {
    return <LoadingSpinner />;
  }

  const COLORS = ['#10b981', '#f59e0b', '#3b82f6', '#8b5cf6', '#ec4899'];

  return (
    <div className="animate-fade-up pb-12">
      {/* Header */}
      <div className="mb-8 border-b border-[var(--border-color)] pb-6">
        <button
          onClick={() => navigate('/analysis')}
          className="mb-4 text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-[10px] uppercase tracking-widest flex items-center"
        >
          <span className="mr-2">←</span> Back to Analysis
        </button>
        <h1 className="font-display text-4xl text-[var(--text-primary)] tracking-wide mb-2">
          Financial Intelligence Dashboard
        </h1>
        <p className="font-mono text-[11px] tracking-widest text-[var(--text-muted)] uppercase">
          Powered by Amazon Nova Financial Intelligence Engine
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-6 mb-8 border-b border-[var(--border-color)] pb-4">
        <button
          onClick={() => setActiveTab('overview')}
          className={`font-mono text-[11px] tracking-widest uppercase transition-all ${
            activeTab === 'overview'
              ? 'text-[var(--primary-accent)] border-b-2 border-[var(--primary-accent)] pb-4'
              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('analysis')}
          className={`font-mono text-[11px] tracking-widest uppercase transition-all ${
            activeTab === 'analysis'
              ? 'text-[var(--primary-accent)] border-b-2 border-[var(--primary-accent)] pb-4'
              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
        >
          AI Insights
        </button>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Row 1: Revenue & Expenses */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Revenue Waterfall */}
            <div className="surface-card p-8">
              <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                Revenue Waterfall
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={chartData.revenue_waterfall.items}
                  margin={{ top: 20, right: 30, left: 0, bottom: 60 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} angle={-45} textAnchor="end" height={100} />
                  <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--bg-color)', border: '1px solid var(--border-color)' }}
                    formatter={(value) => `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
                  />
                  <Bar dataKey="value" fill="var(--primary-accent)">
                    {chartData.revenue_waterfall.items.map((item, index) => (
                      <Cell key={`cell-${index}`} fill={item.itemStyle?.color || 'var(--primary-accent)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="font-mono text-[11px] tracking-widest text-[var(--text-secondary)] mt-4 uppercase">
                Total Revenue: <span className="text-[var(--primary-accent)] font-bold">${chartData.revenue_waterfall.total.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span>
              </p>
            </div>

            {/* Expense Breakdown */}
            <div className="surface-card p-8">
              <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                Expense Breakdown
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={chartData.expense_breakdown}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, value }) => `${name}: $${(value / 1000).toFixed(0)}k`}
                    outerRadius={80}
                    fill="var(--primary-accent)"
                    dataKey="value"
                  >
                    {chartData.expense_breakdown.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Row 2: Variance & Burn Rate */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Variance Analysis */}
            <div className="surface-card p-8">
              <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                Budget vs Actual Variance
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={chartData.variance_chart}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 140, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <YAxis dataKey="category" type="category" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--bg-color)', border: '1px solid var(--border-color)' }}
                    formatter={(value) => `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
                  />
                  <Legend />
                  <Bar dataKey="budget" fill="var(--primary-accent)" />
                  <Bar dataKey="actual" fill="var(--secondary-accent)" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Burn Rate vs Runway */}
            <div className="surface-card p-8">
              <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                Burn Rate & Runway Projection
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={chartData.burn_rate_chart}>
                  <CartesianGrid strokeDasharray="3 3" stroke={colors.gridStroke} />
                  <XAxis dataKey="month" tick={{ fill: colors.textColor, fontSize: 10 }} angle={-45} textAnchor="end" height={100} />
                  <YAxis yAxisId="left" tick={{ fill: colors.textColor, fontSize: 11 }} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fill: colors.textColor, fontSize: 11 }} />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--bg-color)', border: '1px solid var(--border-color)' }} />
                  <Legend />
                  <Bar yAxisId="left" dataKey="burn_rate" fill="var(--secondary-accent)" name="Monthly Burn Rate" />
                  <Line yAxisId="right" type="monotone" dataKey="runway_months" stroke={colors.loanStroke} name="Runway (months)" strokeWidth={2} />
                </ComposedChart>
              </ResponsiveContainer>
              <p className="font-mono text-[11px] tracking-widest text-[var(--text-secondary)] mt-4 uppercase">
                Current Runway: <span className="text-[var(--primary-accent)] font-bold">{chartData.burn_rate_chart[chartData.burn_rate_chart.length - 1]?.runway_months.toFixed(1)} months</span>
              </p>
            </div>
          </div>

          {/* Row 3: Trends */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 12-Month Revenue Trend */}
            <div className="surface-card p-8">
              <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                12-Month Revenue Trend
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData.rolling_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke={colors.gridStroke} />
                  <XAxis dataKey="month" tick={{ fill: colors.textColor, fontSize: 10 }} angle={-45} textAnchor="end" height={100} />
                  <YAxis tick={{ fill: colors.textColor, fontSize: 11 }} />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--bg-color)', border: '1px solid var(--border-color)' }} />
                  <Line type="monotone" dataKey="value" stroke={colors.lineStroke} strokeWidth={2} dot={{ fill: colors.lineStroke }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Risk Score Trend */}
            <div className="surface-card p-8">
              <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                Risk Score Trend
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData.risk_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke={colors.gridStroke} />
                  <XAxis dataKey="month" tick={{ fill: colors.textColor, fontSize: 10 }} angle={-45} textAnchor="end" height={100} />
                  <YAxis tick={{ fill: colors.textColor, fontSize: 11 }} domain={[0, 100]} />
                  <Tooltip contentStyle={{ backgroundColor: 'var(--bg-color)', border: '1px solid var(--border-color)' }} />
                  <Line type="monotone" dataKey="risk_score" stroke={colors.riskStroke} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
              <div className="mt-6 grid grid-cols-3 gap-4">
                <div className="p-3 border border-[var(--border-color)] rounded-sm">
                  <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase">Low (0-40)</p>
                </div>
                <div className="p-3 border border-[var(--border-color)] rounded-sm">
                  <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase">Medium (40-70)</p>
                </div>
                <div className="p-3 border border-[var(--border-color)] rounded-sm">
                  <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase">Critical (70+)</p>
                </div>
              </div>
            </div>
          </div>

          {/* Loan Readiness */}
          <div className="surface-card p-8">
            <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
              Loan Readiness Score
            </h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData.loan_readiness}>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.gridStroke} />
                <XAxis dataKey="month" tick={{ fill: colors.textColor, fontSize: 10 }} angle={-45} textAnchor="end" height={100} />
                <YAxis tick={{ fill: colors.textColor, fontSize: 11 }} domain={[0, 100]} />
                <Tooltip contentStyle={{ backgroundColor: 'var(--bg-color)', border: '1px solid var(--border-color)' }} />
                <Line type="monotone" dataKey="loan_score" stroke={colors.loanStroke} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            <p className="font-mono text-[11px] tracking-widest text-[var(--text-secondary)] mt-4 uppercase">
              Current Score: <span className="text-[var(--primary-accent)] font-bold">{chartData.loan_readiness[chartData.loan_readiness.length - 1]?.loan_score.toFixed(1)}/100</span>
            </p>
          </div>
        </div>
      )}

      {/* AI Insights Tab */}
      {activeTab === 'analysis' && (
        <div className="space-y-6">
          {insights ? (
            <>
              {/* Top Insights */}
              <div className="surface-card p-8">
                <h2 className="font-display text-2xl font-semibold mb-2 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                  Key Financial Insights
                </h2>
                <p className="font-mono text-[10px] tracking-widest text-[var(--text-muted)] uppercase mb-6">Generated by {insights.generated_by || 'Amazon Nova'}</p>
                <div className="space-y-3">
                  {Array.isArray(insights.top_insights) && insights.top_insights.length > 0 ? (
                    insights.top_insights.map((insight, idx) => (
                      <div key={idx} className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                        <p className="font-mono text-[11px] text-[var(--text-primary)]">{insight}</p>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                      <p className="font-mono text-[11px] text-[var(--text-secondary)]">Unable to generate AI insights. Please review the financial data in the Overview tab.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Risks */}
              <div className="surface-card p-8">
                <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                  Financial Risks
                </h2>
                <div className="space-y-3">
                  {Array.isArray(insights.risks) && insights.risks.length > 0 ? (
                    insights.risks.map((risk, idx) => {
                      const severityColor = risk.severity === 'high' ? 'var(--negative-color)' : 
                                           risk.severity === 'medium' ? 'var(--primary-accent)' : 
                                           'var(--positive-color)';
                      return (
                        <div key={idx} className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm" style={{ borderLeft: `3px solid ${severityColor}` }}>
                          <div className="flex justify-between items-start mb-2">
                            <h3 className="font-display text-[14px] font-semibold text-[var(--text-primary)]">{risk.title}</h3>
                            <span className="font-mono text-[9px] tracking-widest uppercase px-2 py-1 border" style={{ borderColor: severityColor, color: severityColor }}>
                              {risk.severity}
                            </span>
                          </div>
                          <p className="font-mono text-[11px] text-[var(--text-secondary)]">{risk.description}</p>
                        </div>
                      );
                    })
                  ) : (
                    <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                      <p className="font-mono text-[11px] text-[var(--text-secondary)]">No risks identified in the financial analysis.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Recommendations */}
              <div className="surface-card p-8">
                <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                  Strategic Recommendations
                </h2>
                <div className="space-y-3">
                  {Array.isArray(insights.recommendations) && insights.recommendations.length > 0 ? (
                    insights.recommendations.map((rec, idx) => (
                      <div key={idx} className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                        <div className="flex gap-4">
                          <span className="font-mono text-[11px] tracking-widest font-bold text-[var(--primary-accent)] flex-shrink-0 uppercase">0{idx + 1}</span>
                          <p className="font-mono text-[11px] text-[var(--text-primary)]">{rec}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                      <p className="font-mono text-[11px] text-[var(--text-secondary)]">No recommendations available at this time.</p>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="surface-card p-8 border border-[var(--border-color)]">
              <p className="font-mono text-[11px] tracking-widest text-[var(--text-secondary)] uppercase text-center">
                AI insights could not be generated. Please review the charts above for financial analysis.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default FinancialIntelligence;