import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAnalyses, getAnalysis } from '../services/api';
import LoadingSpinner from '../components/Common/LoadingSpinner';

function formatDate(iso) {
  if (!iso) return 'N/A';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'N/A';
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function downloadJSON(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadCSV(data, filename) {
  const rows = [];
  const addRow = (key, value) => {
    const escaped = String(value).replace(/"/g, '""');
    rows.push(`"${key}","${escaped}"`);
  };

  addRow('Metric', 'Value');

  const section1 = data?.section_1_financial_health || {};
  const section2 = data?.section_2_cash_flow_forecast || {};
  const section3 = data?.section_3_risk_alerts || {};

  addRow('Total Revenue', section1?.revenue?.total || section1?.financial_health?.total_revenue || 'N/A');
  addRow('Total Expenses', section1?.expenses?.total || section1?.financial_health?.total_expenses || 'N/A');
  addRow('Net Profit Margin (%)', section1?.metrics?.net_profit_margin || section1?.financial_health?.net_profit_margin_percent || 'N/A');
  addRow('Monthly Burn Rate', section2?.monthly_burn_rate || section1?.metrics?.monthly_burn_rate || 'N/A');
  addRow('Runway (months)', section2?.runway_months || section1?.metrics?.runway_months || 'N/A');
  addRow('Risk Score', section3?.risk_score || 'N/A');
  addRow('Risk Level', section3?.risk_level || 'N/A');
  addRow('Loan Readiness Score', data?.section_5_loan_readiness_score || data?.loan_readiness_score || 'N/A');

  const csv = rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadPDF(analysisId, reportData) {
  const content = `
FINANCIAL ANALYSIS REPORT
${new Date().toLocaleDateString()}

Analysis ID: ${analysisId}

FINANCIAL HEALTH
Revenue: ${reportData?.section_1_financial_health?.revenue?.total || 'N/A'}
Expenses: ${reportData?.section_1_financial_health?.expenses?.total || 'N/A'}
Net Profit Margin: ${reportData?.section_1_financial_health?.metrics?.net_profit_margin || 'N/A'}%

CASH FLOW
Monthly Burn Rate: ${reportData?.section_2_cash_flow_forecast?.monthly_burn_rate || 'N/A'}
Runway: ${reportData?.section_2_cash_flow_forecast?.runway_months || 'N/A'} months

RISK ASSESSMENT
Risk Score: ${reportData?.section_3_risk_alerts?.risk_score || 'N/A'}
Risk Level: ${reportData?.section_3_risk_alerts?.risk_level || 'N/A'}

LOAN READINESS
Score: ${reportData?.section_5_loan_readiness_score || reportData?.loan_readiness_score || 'N/A'}/100

EXECUTIVE SUMMARY
${reportData?.section_6_recommended_actions?.executive_summary || 'No summary available'}

For full interactive report, open the Full Report view.
`;

  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `financial-report-${analysisId.slice(0, 8)}.txt`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function Reports() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [latestAnalysis, setLatestAnalysis] = useState(null);
  const [reportData, setReportData] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadLatestReport() {
      try {
        setLoading(true);
        setError(null);

        const analysesResp = await getAnalyses({ page: 1, limit: 50, status_filter: 'completed' });
        const analyses = analysesResp?.data?.analyses || [];

        if (!analyses.length) {
          if (!cancelled) {
            setLatestAnalysis(null);
            setReportData(null);
          }
          return;
        }

        const latest = analyses[0];
        if (!cancelled) setLatestAnalysis(latest);

        try {
          const reportResp = await getAnalysis(latest.analysis_id);
          const report = reportResp?.data?.report || null;
          if (!cancelled) setReportData(report);
        } catch (e) {
          if (!cancelled) setReportData(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err?.response?.data?.detail || 'Failed to load reports');
          setLatestAnalysis(null);
          setReportData(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadLatestReport();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <div className="surface-card p-10 border border-[var(--negative-color)] animate-fade-up">
        <h1 className="font-display text-3xl mb-4 text-[var(--negative-color)]">Error</h1>
        <p className="text-[var(--text-secondary)] font-mono text-sm">{error}</p>
      </div>
    );
  }

  if (!latestAnalysis) {
    return (
      <div className="surface-card p-10 animate-fade-up">
        <h1 className="font-display text-3xl mb-4 text-[var(--text-primary)]">Reports</h1>
        <p className="text-[var(--text-secondary)]">No financial reports available yet. Run an analysis to generate your first report.</p>
      </div>
    );
  }

  return (
    <div className="animate-fade-up pb-12 space-y-6">
      {/* Header */}
      <div className="border-b border-[var(--border-color)] pb-6">
        <h1 className="font-display text-4xl text-[var(--text-primary)] tracking-wide mb-2">Executive Report Export</h1>
        <p className="font-mono text-[11px] tracking-widest text-[var(--text-muted)] uppercase">Download and share your latest financial analysis</p>
      </div>

      {/* Latest Analysis Summary */}
      <div className="surface-card p-8" data-section="Latest Analysis Summary">
        <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
          Latest Analysis
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
          <div>
            <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase mb-2">Analysis ID</p>
            <p className="font-mono text-sm text-[var(--text-primary)] break-all">{latestAnalysis.analysis_id}</p>
          </div>
          <div>
            <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase mb-2">Date Completed</p>
            <p className="font-mono text-sm text-[var(--text-primary)]">{formatDate(latestAnalysis.completed_at)}</p>
          </div>
          <div>
            <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase mb-2">Status</p>
            <p className="font-mono text-sm">
              <span className="inline-block px-3 py-1 border border-[var(--positive-color)] bg-[rgba(0,230,118,0.05)] text-[var(--positive-color)] rounded-sm uppercase text-[10px] tracking-wider font-bold">
                {latestAnalysis.status}
              </span>
            </p>
          </div>
          <div>
            <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase mb-2">Documents Analyzed</p>
            <p className="font-mono text-sm text-[var(--text-primary)]">{latestAnalysis.document_count}</p>
          </div>
        </div>

        <div className="border-t border-[var(--border-color)] pt-6">
          <button
            onClick={() => navigate(`/report/${latestAnalysis.analysis_id}`)}
            className="px-6 py-3 border border-[var(--primary-accent)] text-[var(--primary-accent)] hover:bg-[var(--primary-accent)] hover:text-[var(--bg-color)] transition-colors font-mono text-xs uppercase tracking-widest rounded-sm font-bold"
          >
            Open Full Report
          </button>
        </div>
      </div>

      {/* Export Options */}
      <div className="surface-card p-8" data-section="Export Options">
        <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
          Export Options
        </h2>

        <div className="space-y-4">
          {/* Download Full Report */}
          <div className="p-4 border border-[var(--border-color)] rounded-sm">
            <h3 className="font-display text-lg text-[var(--text-primary)] mb-2">Download Full Report</h3>
            <p className="font-mono text-[11px] text-[var(--text-secondary)] mb-4">Plain text summary of your financial analysis including all key metrics and executive summary.</p>
            <button
              onClick={() => downloadPDF(latestAnalysis.analysis_id, reportData)}
              className="px-4 py-2 border border-[var(--border-color)] text-[var(--text-primary)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)] transition-colors font-mono text-[11px] uppercase tracking-widest rounded-sm"
            >
              Download as Text
            </button>
          </div>

          {/* Download Financial Metrics */}
          <div className="p-4 border border-[var(--border-color)] rounded-sm">
            <h3 className="font-display text-lg text-[var(--text-primary)] mb-2">Download Financial Metrics</h3>
            <p className="font-mono text-[11px] text-[var(--text-secondary)] mb-4">Spreadsheet-compatible CSV with all key financial metrics for integration with Excel or other tools.</p>
            <button
              onClick={() => downloadCSV(reportData, `financial-metrics-${latestAnalysis.analysis_id.slice(0, 8)}.csv`)}
              className="px-4 py-2 border border-[var(--border-color)] text-[var(--text-primary)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)] transition-colors font-mono text-[11px] uppercase tracking-widest rounded-sm"
            >
              Download as CSV
            </button>
          </div>

          {/* Download Risk Summary */}
          <div className="p-4 border border-[var(--border-color)] rounded-sm">
            <h3 className="font-display text-lg text-[var(--text-primary)] mb-2">Download Risk Summary</h3>
            <p className="font-mono text-[11px] text-[var(--text-secondary)] mb-4">Complete risk assessment data in JSON format for system integration and further analysis.</p>
            <button
              onClick={() => downloadJSON(reportData?.section_3_risk_alerts || {}, `risk-summary-${latestAnalysis.analysis_id.slice(0, 8)}.json`)}
              className="px-4 py-2 border border-[var(--border-color)] text-[var(--text-primary)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)] transition-colors font-mono text-[11px] uppercase tracking-widest rounded-sm"
            >
              Download as JSON
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
