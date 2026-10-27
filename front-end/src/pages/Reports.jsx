import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAnalyses, getAnalysis } from '../services/api';
import LoadingSpinner from '../components/Common/LoadingSpinner';
import {
  downloadFinancialMetricsCsv,
  downloadReportText,
  downloadRiskSummaryJson,
} from '../utils/reportExports';

const PAGE_SIZE = 20;

const formatDate = (iso) => {
  if (!iso) return 'N/A';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'N/A';
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};

export default function Reports() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [exportingKey, setExportingKey] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadReports() {
      try {
        setLoading(true);
        setError(null);

        const response = await getAnalyses({
          page,
          limit: PAGE_SIZE,
          status_filter: 'completed',
        });
        if (!cancelled) {
          setAnalyses(response.data.analyses || []);
          setTotal(response.data.total || 0);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err?.response?.data?.detail || 'Failed to load reports');
          setAnalyses([]);
          setTotal(0);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadReports();
    return () => {
      cancelled = true;
    };
  }, [page]);

  const handleExport = async (analysisId, format) => {
    const exportKey = `${analysisId}:${format}`;
    setExportingKey(exportKey);
    setError(null);

    try {
      const response = await getAnalysis(analysisId);
      const reportData = response.data.report;
      if (!reportData) throw new Error('Report data is not available for this analysis.');

      if (format === 'text') downloadReportText(analysisId, reportData);
      if (format === 'csv') downloadFinancialMetricsCsv(analysisId, reportData);
      if (format === 'json') downloadRiskSummaryJson(analysisId, reportData);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to export report');
    } finally {
      setExportingKey(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (loading) return <LoadingSpinner size="medium" />;

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--border-color)] pb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-wide mb-2">Reports</h1>
          <p className="font-mono text-sm text-[var(--text-muted)] tracking-wide uppercase">Completed analyses and exports</p>
        </div>
        <span className="font-mono text-xs text-[var(--text-muted)]">{total} completed</span>
      </div>

      {error && (
        <div role="alert" className="border border-[var(--negative-color)] p-4 font-mono text-sm text-[var(--negative-color)]">
          {error}
        </div>
      )}

      {analyses.length === 0 ? (
        <div className="surface-card p-10 text-center">
          <h2 className="text-xl font-bold text-[var(--text-primary)] mb-3">No completed reports yet</h2>
          <p className="text-[var(--text-secondary)] mb-6">Completed analyses will appear here with their own report and export actions.</p>
          <button
            type="button"
            onClick={() => navigate('/analysis')}
            className="border border-[var(--primary-accent)] px-4 py-2 font-mono text-xs uppercase tracking-widest text-[var(--primary-accent)] hover:bg-[var(--primary-accent)] hover:text-[var(--bg-color)]"
          >
            Go to Analysis
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {analyses.map((analysis) => {
            const id = analysis.analysis_id;
            return (
              <article key={id} className="surface-card flex flex-col gap-5 p-5 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)]">
                      Report {id.slice(0, 8).toUpperCase()}
                    </h2>
                    <span className="border border-[var(--positive-color)] px-2 py-1 font-mono text-[9px] uppercase tracking-widest text-[var(--positive-color)]">
                      {analysis.status}
                    </span>
                  </div>
                  <p className="font-mono text-xs text-[var(--text-secondary)]">
                    Completed {formatDate(analysis.completed_at || analysis.created_at)}
                  </p>
                  <p className="font-mono text-xs text-[var(--text-muted)]">
                    {analysis.document_count} {analysis.document_count === 1 ? 'document' : 'documents'}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/report/${id}`)}
                    className="border border-[var(--primary-accent)] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[var(--primary-accent)] hover:bg-[var(--primary-accent)] hover:text-[var(--bg-color)]"
                  >
                    View report
                  </button>
                  {[
                    ['text', 'TXT'],
                    ['csv', 'CSV'],
                    ['json', 'Risk JSON'],
                  ].map(([format, label]) => {
                    const exportKey = `${id}:${format}`;
                    return (
                      <button
                        key={format}
                        type="button"
                        onClick={() => handleExport(id, format)}
                        disabled={Boolean(exportingKey)}
                        title={`Download ${label} for report ${id.slice(0, 8)}`}
                        className="border border-[var(--border-color)] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[var(--text-primary)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)] disabled:opacity-50"
                      >
                        {exportingKey === exportKey ? 'Preparing...' : label}
                      </button>
                    );
                  })}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {total > PAGE_SIZE && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-color)] pt-4">
          <p className="font-mono text-xs text-[var(--text-muted)]">
            Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, total)} of {total} reports
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page <= 1}
              className="border border-[var(--border-color)] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[var(--text-primary)] disabled:opacity-40"
            >
              Previous
            </button>
            <span className="px-2 py-2 font-mono text-[10px] text-[var(--text-muted)]">Page {page} of {totalPages}</span>
            <button
              type="button"
              onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              disabled={page >= totalPages}
              className="border border-[var(--border-color)] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[var(--text-primary)] disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
