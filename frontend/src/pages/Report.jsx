import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getAnalysis } from "../services/api";
import LoadingSpinner from "../components/Common/LoadingSpinner";
import AskCFOChat from "../components/AskCFO/AskCFOChat";

const MIN_SELECTION_LENGTH = 8;

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const Report = () => {
  const { analysisId } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectionAction, setSelectionAction] = useState(null);
  const [selectedContextForChat, setSelectedContextForChat] = useState(null);
  const reportContentRef = useRef(null);
  const chatSectionRef = useRef(null);

  useEffect(() => {
    fetchReport();
    const interval = setInterval(fetchReport, 10000); // Poll every 10 seconds

    return () => clearInterval(interval);
  }, [analysisId]);

  useEffect(() => {
    const handleSelectionChange = () => {
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
        setSelectionAction(null);
        return;
      }

      const selectedText = selection.toString().trim();
      if (
        selectedText.length < MIN_SELECTION_LENGTH ||
        !reportContentRef.current
      ) {
        setSelectionAction(null);
        return;
      }

      const range = selection.getRangeAt(0);
      const commonAncestor = range.commonAncestorContainer;
      const targetNode =
        commonAncestor.nodeType === Node.TEXT_NODE
          ? commonAncestor.parentElement
          : commonAncestor;

      if (!targetNode || !reportContentRef.current.contains(targetNode)) {
        setSelectionAction(null);
        return;
      }

      const rect = range.getBoundingClientRect();
      if (!rect.width && !rect.height) {
        setSelectionAction(null);
        return;
      }

      // Use the last visible highlight segment so the button sits beside selected words.
      const selectionRects = Array.from(range.getClientRects()).filter(
        (item) => item.width > 0 && item.height > 0,
      );
      const anchorRect =
        selectionRects.length > 0
          ? selectionRects.reduce((best, current) => {
              if (!best) return current;
              if (current.bottom > best.bottom) return current;
              if (current.bottom === best.bottom && current.right > best.right)
                return current;
              return best;
            }, null)
          : rect;

      const sectionElement = targetNode.closest("[data-report-section]");
      const section =
        sectionElement?.getAttribute("data-report-section") ||
        "Financial Analysis Report";

      const containerRect = reportContentRef.current.getBoundingClientRect();
      const buttonWidth = 160;
      const buttonHeight = 36;

      const relativeTop =
        anchorRect.top -
        containerRect.top +
        anchorRect.height / 2 -
        buttonHeight / 2;
      const relativeLeft = anchorRect.right - containerRect.left + 4;

      setSelectionAction({
        text: selectedText,
        section,
        top: clamp(
          relativeTop,
          0,
          reportContentRef.current.offsetHeight - buttonHeight,
        ),
        left: clamp(
          relativeLeft,
          0,
          reportContentRef.current.offsetWidth - buttonWidth,
        ),
      });
    };

    document.addEventListener("selectionchange", handleSelectionChange);

    return () => {
      document.removeEventListener("selectionchange", handleSelectionChange);
    };
  }, []);

  const fetchReport = async () => {
    try {
      const response = await getAnalysis(analysisId);
      const data = response.data;

      setReport(data);

      if (data.status === "completed" || data.status === "failed") {
        setLoading(false);
      }
    } catch (err) {
      setError(err.response?.data?.error?.message || "Failed to fetch report");
      setLoading(false);
    }
  };

  const handleSelectionAskClick = () => {
    if (!selectionAction) return;

    setSelectedContextForChat({
      id: Date.now(),
      text: selectionAction.text,
      section: selectionAction.section,
    });

    setSelectionAction(null);
    window.getSelection()?.removeAllRanges();

    setTimeout(() => {
      chatSectionRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 80);
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center py-32 animate-fade-up">
        <LoadingSpinner size="large" />
        <p className="mt-8 font-mono text-[11px] tracking-widest text-[var(--primary-accent)] uppercase animate-pulse">
          {report?.status === "processing"
            ? "Analysis in progress... This may take a few minutes."
            : "Loading report..."}
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="surface-card p-10 animate-fade-up border-[var(--negative-color)]">
        <h2 className="font-display text-2xl text-[var(--negative-color)] mb-4">
          Error Loading Report
        </h2>
        <div className="font-mono text-sm text-[var(--text-secondary)]">
          {error}
        </div>
        <button
          onClick={() => navigate("/analysis")}
          className="mt-6 px-4 py-2 border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--text-primary)] transition-colors font-mono text-xs uppercase tracking-widest rounded-sm"
        >
          ← Back to Analysis
        </button>
      </div>
    );
  }

  const reportData = report?.report;

  return (
    <div className="flex flex-col space-y-6 animate-fade-up pb-12">
      <div className="flex justify-between items-end mb-4 border-b border-[var(--border-color)] pb-6">
        <div>
          <button
            onClick={() => navigate("/analysis")}
            className="mb-4 text-[var(--text-muted)] hover:text-[var(--primary-accent)] transition-colors font-mono text-[10px] uppercase tracking-widest flex items-center"
          >
            <span className="mr-2">←</span> BACK TO ANALYSIS
          </button>
          <h1 className="font-display text-4xl text-[var(--text-primary)] tracking-wide">
            Financial Analysis Report
          </h1>
        </div>
        <div className="text-right space-y-3">
          <p className="font-mono text-[10px] tracking-widest text-[var(--text-muted)] uppercase mb-1">
            Status
          </p>
          <span
            className={`px-3 py-1 text-[11px] font-mono tracking-widest uppercase rounded-sm border block ${
              report?.status === "completed"
                ? "border-[var(--positive-color)] text-[var(--positive-color)]"
                : "border-[var(--negative-color)] text-[var(--negative-color)]"
            }`}
          >
            {report?.status}
          </span>
          {report?.status === "completed" && (
            <button
              onClick={() => {
                localStorage.setItem('lastAnalysisId', analysisId);
                navigate('/financial-intelligence');
              }}
              className="w-full px-3 py-2 text-[11px] font-mono tracking-widest uppercase rounded-sm border border-[var(--primary-accent)] text-[var(--primary-accent)] hover:bg-[var(--primary-accent)] hover:text-[var(--bg-color)] transition-all"
            >
              📊 Dashboard
            </button>
          )}
        </div>
      </div>

      {report?.status === "failed" && (
        <div className="surface-card p-6 border-[var(--negative-color)] mb-6 bg-[rgba(255,59,59,0.05)]">
          <p className="font-mono text-[var(--negative-color)] text-sm tracking-wide">
            <span className="font-bold mr-2">!</span> Analysis failed. Please
            try again.
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
            {/* Agent Warnings */}
            {(reportData.section_1_financial_health?.error ||
              reportData.section_2_cash_flow_forecast?.error ||
              reportData.section_3_risk_alerts?.error) && (
              <div
                className="surface-card p-6 border-[var(--primary-accent)] bg-[rgba(205,127,50,0.05)]"
                data-report-section="Partial Analysis Warnings"
              >
                <p className="font-mono text-[var(--primary-accent)] text-sm font-semibold tracking-wide mb-3 uppercase">
                  ⚠️ Partial Analysis Warnings:
                </p>
                <div className="space-y-2 font-mono text-[11px] text-[var(--text-secondary)]">
                  {reportData.section_1_financial_health?.error && (
                    <p>
                      › Financial Health:{" "}
                      {reportData.section_1_financial_health.error}
                    </p>
                  )}
                  {reportData.section_2_cash_flow_forecast?.error && (
                    <p>
                      › Cash Flow:{" "}
                      {reportData.section_2_cash_flow_forecast.error}
                    </p>
                  )}
                  {reportData.section_3_risk_alerts?.error && (
                    <p>› Risk: {reportData.section_3_risk_alerts.error}</p>
                  )}
                </div>
              </div>
            )}

            {/* Section 1: Financial Health */}
            <div
              className="surface-card p-8"
              data-report-section="Financial Health Overview"
            >
              <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                1. Financial Health Overview
              </h2>

              {reportData.section_1_financial_health && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase mb-2">
                      Total Revenue
                    </p>
                    <p className="font-mono text-2xl font-bold text-[var(--text-primary)]">
                      $
                      {reportData.section_1_financial_health.revenue?.total?.toLocaleString() ||
                        0}
                    </p>
                  </div>
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase mb-2">
                      Total Expenses
                    </p>
                    <p className="font-mono text-2xl font-bold text-[var(--text-primary)]">
                      $
                      {reportData.section_1_financial_health.expenses?.total?.toLocaleString() ||
                        0}
                    </p>
                  </div>
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase mb-2">
                      Net Profit Margin
                    </p>
                    <p className="font-mono text-2xl font-bold text-[var(--primary-accent)]">
                      {reportData.section_1_financial_health.metrics
                        ?.net_profit_margin || 0}
                      %
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Section 2: Cash Flow */}
            <div
              className="surface-card p-8"
              data-report-section="Cash Flow Forecast"
            >
              <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                2. Cash Flow Forecast
              </h2>

              {reportData.section_2_cash_flow_forecast && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase mb-2">
                      Monthly Burn Rate
                    </p>
                    <p className="font-mono text-xl font-bold text-[var(--negative-color)]">
                      $
                      {reportData.section_2_cash_flow_forecast.monthly_burn_rate?.toLocaleString() ||
                        0}
                    </p>
                  </div>
                  <div className="p-4 border border-[var(--border-color)] bg-[var(--bg-color)] rounded-sm">
                    <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] uppercase mb-2">
                      Runway
                    </p>
                    <p className="font-mono text-xl font-bold text-[var(--secondary-accent)]">
                      {reportData.section_2_cash_flow_forecast.runway_months ||
                        0}{" "}
                      months
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Section 6: Recommendations */}
            <div
              className="surface-card p-8"
              data-report-section="Recommended Actions"
            >
              <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)] border-b border-[var(--border-color)] pb-4">
                6. Recommended Actions
              </h2>

              {reportData.section_6_recommended_actions
                ?.recommended_actions && (
                <div className="space-y-4">
                  {reportData.section_6_recommended_actions.recommended_actions.map(
                    (action, idx) => (
                      <div
                        key={idx}
                        className="border border-[var(--border-color)] bg-[var(--bg-color)] p-5 rounded-sm relative overflow-hidden"
                      >
                        {/* Priority Tag */}
                        <div
                          className={`absolute top-0 right-0 px-3 py-1 font-mono text-[9px] tracking-widest uppercase font-bold
                          ${
                            action.priority === "High" || action.priority === 1
                              ? "bg-[rgba(255,59,59,0.1)] text-[var(--negative-color)]"
                              : action.priority === "Medium" ||
                                  action.priority === 2
                                ? "bg-[rgba(205,127,50,0.1)] text-[var(--primary-accent)]"
                                : "bg-[rgba(170,255,0,0.1)] text-[var(--secondary-accent)]"
                          }
                        `}
                        >
                          Priority {action.priority}
                        </div>

                        <h3 className="font-display text-lg text-[var(--text-primary)] mb-2 pr-24">
                          {action.action}
                        </h3>
                        <p className="text-[13px] text-[var(--text-secondary)] leading-relaxed mb-4">
                          {action.details}
                        </p>

                        <div className="flex flex-wrap gap-4 pt-4 border-t border-[var(--border-color)] border-opacity-50">
                          <div className="font-mono text-[10px] tracking-wider">
                            <span className="text-[var(--text-muted)] uppercase mr-2">
                              Impact:
                            </span>
                            <span className="text-[var(--text-primary)]">
                              {action.impact}
                            </span>
                          </div>
                          <div className="font-mono text-[10px] tracking-wider">
                            <span className="text-[var(--text-muted)] uppercase mr-2">
                              Effort:
                            </span>
                            <span className="text-[var(--text-primary)]">
                              {action.effort}
                            </span>
                          </div>
                          <div className="font-mono text-[10px] tracking-wider">
                            <span className="text-[var(--text-muted)] uppercase mr-2">
                              Timeline:
                            </span>
                            <span className="text-[var(--text-primary)]">
                              {action.timeline}
                            </span>
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
            {/* Section 5: Loan Readiness */}
            <div
              className="surface-card p-8 text-center relative overflow-hidden"
              data-report-section="Loan Readiness Score"
            >
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[var(--primary-accent)] to-[var(--secondary-accent)]"></div>
              <h2 className="font-mono text-[10px] tracking-widest uppercase text-[var(--text-muted)] mb-8">
                5. Loan Readiness Score
              </h2>

              <div className="inline-block relative">
                {/* Decorative circle */}
                <div className="absolute inset-[-20px] rounded-full border border-[var(--border-color)] animate-[spin_10s_linear_infinite] opacity-30"></div>

                <p className="font-mono text-7xl font-bold text-[var(--primary-accent)] relative z-10">
                  {reportData.section_5_loan_readiness_score || 0}
                </p>
                <p className="font-mono text-[10px] tracking-widest uppercase text-[var(--text-secondary)] mt-4 mb-2">
                  out of 100
                </p>
              </div>
            </div>

            {/* Section 3: Risk Alerts */}
            <div className="surface-card p-6" data-report-section="Risk Alerts">
              <h2 className="font-mono text-[10px] tracking-widest uppercase text-[var(--text-muted)] mb-6 border-b border-[var(--border-color)] pb-4">
                3. Risk Alerts
              </h2>

              {reportData.section_3_risk_alerts && (
                <div className="text-center py-4">
                  <div className="mb-6">
                    <p className="font-display text-4xl font-bold text-[var(--text-primary)]">
                      {reportData.section_3_risk_alerts.risk_score || 0}
                      <span className="text-xl text-[var(--text-muted)]">
                        /100
                      </span>
                    </p>
                    <p className="font-mono text-[9px] tracking-widest uppercase text-[var(--text-muted)] mt-2">
                      Overall Risk Score
                    </p>
                  </div>

                  <span
                    className={`inline-block px-6 py-2 border rounded-sm font-mono text-xs tracking-widest uppercase font-bold w-full ${
                      reportData.section_3_risk_alerts.risk_level === "low"
                        ? "bg-[rgba(0,230,118,0.05)] border-[var(--positive-color)] text-[var(--positive-color)]"
                        : reportData.section_3_risk_alerts.risk_level ===
                            "medium"
                          ? "bg-[rgba(205,127,50,0.05)] border-[var(--primary-accent)] text-[var(--primary-accent)]"
                          : "bg-[rgba(255,59,59,0.05)] border-[var(--negative-color)] text-[var(--negative-color)]"
                    }`}
                  >
                    {reportData.section_3_risk_alerts.risk_level?.toUpperCase() ||
                      "UNKNOWN"}{" "}
                    RISK
                  </span>
                </div>
              )}
            </div>

            {/* Executive Summary */}
            {reportData.section_6_recommended_actions?.executive_summary && (
              <div
                className="surface-card p-6 border-t-4 border-[var(--secondary-accent)]"
                data-report-section="Executive Summary"
              >
                <h2 className="font-mono text-[10px] tracking-widest uppercase text-[var(--text-muted)] mb-4">
                  Executive Summary
                </h2>
                <div className="font-body text-[13px] text-[var(--text-secondary)] leading-relaxed italic border-l-2 border-[var(--border-color)] pl-4">
                  <p className="whitespace-pre-wrap">
                    "
                    {reportData.section_6_recommended_actions.executive_summary}
                    "
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Ask AgentCFO Chat – only show when analysis is completed */}
      {report?.status === "completed" && reportData && (
        <div ref={chatSectionRef} className="mt-8">
          <div className="mb-6 border-b border-[var(--border-color)] pb-4">
            <h2 className="font-display text-2xl text-[var(--text-primary)] tracking-wide mb-2">
              Ask AgentCFO
            </h2>
            <p className="font-mono text-[10px] tracking-widest text-[var(--text-muted)] uppercase">
              Get strategic CFO-level financial guidance on your report
            </p>
            <p className="mt-3 font-mono text-[10px] tracking-widest text-[var(--secondary-accent)] uppercase">
              Select any report text above to ask a focused follow-up
            </p>
          </div>
          <AskCFOChat
            analysisId={analysisId}
            reportData={reportData}
            selectedContext={selectedContextForChat}
          />
        </div>
      )}

      {selectionAction && reportData && (
        <button
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={handleSelectionAskClick}
          className="absolute z-40 px-4 py-2 bg-[var(--text-primary)] text-[var(--bg-color)] rounded-sm shadow-lg font-mono text-[10px] tracking-widest uppercase hover:opacity-90 transition-opacity"
          style={{
            top: `${selectionAction.top}px`,
            left: `${selectionAction.left}px`,
          }}
        >
          Ask AgentCFO
        </button>
      )}
    </div>
  );
};

export default Report;
