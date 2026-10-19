import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getAnalysis } from '../services/api';
import LoadingSpinner from '../components/Common/LoadingSpinner';
import {
  downloadFinancialMetricsCsv,
  downloadReportText,
  downloadRiskSummaryJson,
} from '../utils/reportExports';

const MIN_SELECTION_LENGTH = 8;

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const Report = () => {
  const { analysisId } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectionAction, setSelectionAction] = useState(null);
  const reportContentRef = useRef(null);

  useEffect(() => {
    fetchReport();
    const interval = setInterval(fetchReport, 10000);

    return () => clearInterval(interval);
  }, [analysisId]);

  const fetchReport = async () => {
    try {
      const response = await getAnalysis(analysisId);
      const data = response.data;

      setReport(data);

      if (data.status === 'completed' || data.status === 'failed') {
        setLoading(false);
      }
    } catch (err) {
      setError(err.response?.data?.error?.message || 'Failed to fetch report');
      setLoading(false);
    }
  };

  const handleSelectionAskClick = () => {
    if (!selectionAction) return;

    const params = new URLSearchParams();
    params.set('analysis_id', analysisId);
    params.set('selected_text', selectionAction.text);
    params.set('selected_section', selectionAction.section || '');

    navigate(`/chat?${params.toString()}`);

    setSelectionAction(null);
    window.getSelection()?.removeAllRanges();
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center py-32">
        <LoadingSpinner size="large" />
        <p className="mt-6 font-mono text-sm text-[var(--primary-accent)] tracking-wide uppercase">
          {report?.status === 'processing'
            ? 'Analysis in progress. This may take a few minutes.'
            : 'Loading report...'}
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="surface-card p-10 border-[var(--negative-color)]">
        <h2 className="text-xl font-bold text-[var(--negative-color)] mb-4">Error Loading Report</h2>
        <div className="font-mono text-sm text-[var(--text-secondary)] mb-6">{error}</div>
        <button
          onClick={() => navigate('/analysis')}
          className="px-4 py-2 border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--text-primary)] transition-colors font-mono text-xs uppercase tracking-widest rounded-sm"
        >
          Back to Analysis
        </button>
      </div>
    );
  }

  const reportData = report?.report;

  return (
    <div className="flex flex-col space-y-6 pb-12">
      <div className="flex justify-between items-end mb-4 border-b border-[var(--border-color)] pb-6">
        <div>
          <div className="mb-4 flex flex-wrap gap-4">
            <button
              onClick={() => navigate('/reports')}
              className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-[10px] uppercase tracking-widest"
            >
              &larr; All Reports
            </button>
            <button
              onClick={() => navigate('/analysis')}
              className="text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-[10px] uppercase tracking-widest"
            >
              Back to Analysis
            </button>
          </div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-wide">
            Financial Analysis Report
          </h1>
        </div>
        <div className="text-right space-y-3">
          <p className="font-mono text-[10px] tracking-widest text-[var(--text-muted)] uppercase mb-1">
            Status
          </p>
          <span
            className={`px-3 py-1 text-[11px] font-medium tracking-widest uppercase rounded-sm border block ${
              report?.status === 'completed'
                ? 'border-[var(--positive-color)] text-[var(--positive-color)]'
                : 'border-[var(--negative-color)] text-[var(--negative-color)]'
            }`}
          >
            {report?.status}
          </span>
          {report?.status === 'completed' && (
            <>
              <button
                onClick={() => {
                  localStorage.setItem('lastAnalysisId', analysisId);
                  navigate('/dashboard');
                }}
                className="w-full px-3 py-2 text-[11px] font-medium tracking-widest uppercase rounded-sm border border-[var(--primary-accent)] text-[var(--primary-accent)] hover:bg-[var(--primary-accent)] hover:text-[var(--bg-color)] transition-colors"
              >
                View Dashboard
              </button>
              <button
                onClick={() => {
                  const params = new URLSearchParams();
                  params.set('analysis_id', analysisId);
                  navigate(`/chat?${params.toString()}`);
                }}
                className="mt-2 w-full px-3 py-2 text-[11px] font-medium tracking-widest uppercase rounded-sm border border-[var(--primary-accent)] text-[var(--primary-accent)] hover:bg-[var(--primary-accent)] hover:text-[var(--bg-color)] transition-colors"
              >
                Ask CFO
              </button>
            </>
          )}
        </div>
      </div>

      {report?.status === 'failed' && (
        <div className="surface-card p-6 border-[var(--negative-color)] mb-6 bg-[rgba(248,113,113,0.05)]">
          <p className="font-mono text-[var(--negative-color)] text-sm tracking-wide">
            <span className="font-bold mr-2">!</span> Analysis failed. Please try again.
          </p>
        </div>
      )}

      {reportData && (
        <div
          ref={reportContentRef}
          className="relative grid grid-cols-1 lg:grid-cols-12 gap-6"
        >
          {/* Main Content Column */}
          <div className="lg:col-span-8 flex flex-col space-y-6">
            {/* Section 1: Financial Health */}
            <div
              className="surface-card p-6"
              data-report-section="Financial Health Overview"
            >
              <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">
                1. Financial Health Overview
              </h2>

              {reportData.section_1_financial_health && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[10px] tracking-wider text-[var(--text-muted)] uppercase mb-2">
                      Total Revenue
                    </p>
                    <p className="text-2xl font-bold text-[var(--text-primary)]">
                      $ {reportData.section_1_financial_health.revenue?.total?.toLocaleString() || 0}
                    </p>
                  </div>
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[10px] tracking-wider text-[var(--text-muted)] uppercase mb-2">
                      Total Expenses
                    </p>
                    <p className="text-2xl font-bold text-[var(--text-primary)]">
                      $ {reportData.section_1_financial_health.expenses?.total?.toLocaleString() || 0}
                    </p>
                  </div>
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[10px] tracking-wider text-[var(--text-muted)] uppercase mb-2">
                      Net Profit Margin
                    </p>
                    <p className="text-2xl font-bold text-[var(--primary-accent)]">
                      {reportData.section_1_financial_health.metrics?.net_profit_margin || 0}%
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Section 2: Cash Flow */}
            <div
              className="surface-card p-6"
              data-report-section="Cash Flow Forecast"
            >
              <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">
                2. Cash Flow Forecast
              </h2>

              {reportData.section_2_cash_flow_forecast && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[10px] tracking-wider text-[var(--text-muted)] uppercase mb-2">
                      Monthly Burn Rate
                    </p>
                    <p className="text-xl font-bold text-[var(--negative-color)]">
                      $ {reportData.section_2_cash_flow_forecast.monthly_burn_rate?.toLocaleString() || 0}
                    </p>
                  </div>
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[10px] tracking-wider text-[var(--text-muted)] uppercase mb-2">
                      Runway
                    </p>
                    <p className="text-xl font-bold text-[var(--secondary-accent)]">
                      {reportData.section_2_cash_flow_forecast.runway_months || 0} months
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Section 6: Recommendations */}
            <div
              className="surface-card p-6"
              data-report-section="Recommended Actions"
            >
              <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">
                6. Recommended Actions
              </h2>

              {reportData.section_6_recommended_actions?.recommended_actions && (
                <div className="space-y-3">
                  {reportData.section_6_recommended_actions.recommended_actions.map(
                    (action, idx) => (
                      <div
                        key={idx}
                        className="border border-[var(--border-color)] bg-[var(--bg-color)] p-4 rounded-sm relative overflow-hidden"
                      >
                        <div
                          className={`absolute top-0 right-0 px-2 py-1 font-mono text-[9px] tracking-widest uppercase font-bold
                          ${
                            action.priority === 'High' || action.priority === 1
                              ? 'bg-[rgba(248,113,113,0.1)] text-[var(--negative-color)]'
                              : action.priority === 'Medium' ||
                                  action.priority === 2
                                ? 'bg-[rgba(255,90,31,0.1)] text-[var(--primary-accent)]'
                                : 'bg-[rgba(74,222,128,0.1)] text-[var(--positive-color)]'
                          }`}
                        >
                          Priority {action.priority}
                        </div>

                        <h3 className="font-mono text-sm text-[var(--text-primary)] mb-2">
                          {action.action}
                        </h3>
                        <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-3">
                          {action.details}
                        </p>

                        <div className="flex flex-wrap gap-4 pt-3 border-t border-[var(--border-color)] border-opacity-50">
                          <div className="font-mono text-[10px] tracking-wider">
                            <span className="text-[var(--text-muted)] uppercase mr-1">
                              Impact:
                            </span>
                            <span className="text-[var(--text-primary)]">{action.impact}</span>
                          </div>
                          <div className="font-mono text-[10px] tracking-wider">
                            <span className="text-[var(--text-muted)] uppercase mr-1">
                              Effort:
                            </span>
                            <span className="text-[var(--text-primary)]">{action.effort}</span>
                          </div>
                          <div className="font-mono text-[10px] tracking-wider">
                            <span className="text-[var(--text-muted)] uppercase mr-1">
                              Timeline:
                            </span>
                            <span className="text-[var(--text-primary)]">{action.timeline}</span>
                          </div>
                        </div>
                      </div>
                    ),
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Right Sidebar */}
          <div className="lg:col-span-4 flex flex-col space-y-6">
            {/* Section 5: Loan Readiness Score */}
            <div
              className="surface-card p-6 text-center"
              data-report-section="Loan Readiness Score"
            >
              <h2 className="font-mono text-[10px] tracking-wider uppercase text-[var(--text-muted)] mb-4">
                5. Loan Readiness Score
              </h2>

              <p className="text-4xl font-bold text-[var(--primary-accent)]">
                {reportData.section_5_loan_readiness_score || 0}
              </p>
              <p className="font-mono text-[10px] tracking-wider text-[var(--text-secondary)] mt-1 mb-2">
                out of 100
              </p>
            </div>

            {/* Section 3: Risk Alerts */}
            <div className="surface-card p-6" data-report-section="Risk Alerts">
              <h2 className="font-mono text-[10px] tracking-wider uppercase text-[var(--text-muted)] mb-4 border-b border-[var(--border-color)] pb-2">
                3. Risk Alerts
              </h2>

              {reportData.section_3_risk_alerts && (
                <div className="text-center py-3">
                  <p className="text-2xl font-bold text-[var(--text-primary)]">
                    {reportData.section_3_risk_alerts.risk_score || 0}
                    <span className="text-lg text-[var(--text-muted)]">/100</span>
                  </p>
                  <p className="font-mono text-[10px] tracking-wider text-[var(--text-muted)] mt-1">
                    Overall Risk Score
                  </p>

                  <span
                    className={`inline-block px-4 py-1.5 border rounded-sm font-mono text-[10px] tracking-wider uppercase font-bold w-full ${
                      reportData.section_3_risk_alerts.risk_level === 'low'
                        ? 'bg-[rgba(74,222,128,0.1)] border-[var(--positive-color)] text-[var(--positive-color)]'
                        : reportData.section_3_risk_alerts.risk_level === 'medium'
                          ? 'bg-[rgba(255,90,31,0.1)] border-[var(--primary-accent)] text-[var(--primary-accent)]'
                          : 'bg-[rgba(248,113,113,0.1)] border-[var(--negative-color)] text-[var(--negative-color)]'
                    }`}
                  >
                    {reportData.section_3_risk_alerts.risk_level?.toUpperCase() || 'UNKNOWN'} RISK
                  </span>
                </div>
              )}
            </div>

            {/* Executive Summary */}
            {report?.status === 'completed' && reportData && (
              <div
                className="surface-card p-6 border-t-4 border-[var(--secondary-accent)]"
                data-report-section="Executive Summary"
              >
                <h2 className="font-mono text-[10px] tracking-wider uppercase text-[var(--text-muted)] mb-3">
                  Executive Summary
                </h2>
                {reportData.section_6_recommended_actions?.executive_summary ? (
                  <div className="text-sm text-[var(--text-secondary)] leading-relaxed border-l-2 border-[var(--border-color)] pl-4">
                    <p className="whitespace-pre-wrap">{reportData.section_6_recommended_actions.executive_summary}</p>
                  </div>
                ) : (
                  <p className="text-sm text-[var(--text-muted)]">No executive summary is available for this report.</p>
                )}
                <div className="mt-5 flex flex-wrap gap-2 border-t border-[var(--border-color)] pt-4">
                  <button
                    type="button"
                    onClick={() => downloadReportText(analysisId, reportData)}
                    className="border border-[var(--border-color)] px-2.5 py-2 font-mono text-[9px] uppercase tracking-widest text-[var(--text-primary)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)]"
                  >
                    Export TXT
                  </button>
                  <button
                    type="button"
                    onClick={() => downloadFinancialMetricsCsv(analysisId, reportData)}
                    className="border border-[var(--border-color)] px-2.5 py-2 font-mono text-[9px] uppercase tracking-widest text-[var(--text-primary)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)]"
                  >
                    Export CSV
                  </button>
                  <button
                    type="button"
                    onClick={() => downloadRiskSummaryJson(analysisId, reportData)}
                    className="border border-[var(--border-color)] px-2.5 py-2 font-mono text-[9px] uppercase tracking-widest text-[var(--text-primary)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)]"
                  >
                    Risk JSON
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Report;
