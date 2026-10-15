import React, { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { getDocuments, getAnalyses } from "../services/api";
import { useNavigate } from "react-router-dom";

const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    documents: 2, // Default visual placeholders
    analyses: 3,
    latest: null,
  });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [docsRes, analysesRes] = await Promise.all([
          getDocuments({ limit: 1 }),
          getAnalyses({ limit: 1 }),
        ]);

        setStats({
          documents: docsRes.data.total,
          analyses: analysesRes.data.total,
          latest: analysesRes.data.analyses[0] || null,
        });
      } catch (error) {
        console.error("Failed to fetch stats:", error);
      }
    };

    fetchStats();
  }, []);

  const formatSnapshotTime = (timestamp) => {
    if (!timestamp) return "No runs yet";
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 xl:gap-5">
      {/* Left Column (Wide) */}
      <div className="lg:col-span-8 flex flex-col space-y-4">
        {/* Welcome Panel */}
        <div className="surface-card p-7 animate-fade-up fade-delay-1 relative overflow-hidden">
          <div className="flex justify-between items-start mb-7">
            <div>
              <h1 className="font-display text-4xl mb-3 text-[var(--text-primary)] tracking-wide leading-tight">
                Welcome back,{" "}
                <span className="italic text-[var(--primary-accent)] font-serif">
                  {user?.company_name || "KJSCE"}
                </span>
              </h1>
              <p className="font-mono text-[10px] tracking-widest text-[var(--text-secondary)] uppercase">
                FINANCIAL OVERVIEW — 28 FEB 2026, 14:32 IST
              </p>
            </div>
            <div className="px-4 py-1.5 font-mono text-[9px] tracking-widest flex items-center gap-3 border border-opacity-30 border-[var(--positive-color)] rounded-full text-[var(--positive-color)] bg-[var(--bg-color)]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--positive-color)] animate-pulse"></span>
              ALL SYSTEMS OPERATIONAL
            </div>
          </div>

          <div className="font-mono text-xs text-[var(--text-muted)]">
            <span className="text-[var(--cmd-line-color)]">
              cfone $ running financial health check — {stats.analyses} reports
              ready for review
            </span>
            <span className="inline-block w-2 h-3 bg-[var(--cmd-line-color)] ml-1 animate-blink align-middle"></span>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-0 surface-card py-6 animate-fade-up fade-delay-2 divide-x divide-[var(--border-color)]">
          <div className="px-6 flex flex-col">
            <span className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] mb-3 uppercase">
              · TOTAL DOCUMENTS
            </span>
            <span className="font-mono text-4xl font-bold text-[var(--primary-accent)] mb-2">
              {stats.documents.toString().padStart(2, "0")}
            </span>
            <span className="text-xs text-[var(--text-secondary)]">
              Bank statements & GST reports
            </span>
          </div>
          <div className="px-6 flex flex-col">
            <span className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] mb-3 uppercase">
              · TOTAL ANALYSES
            </span>
            <span
              className="font-mono text-4xl font-bold mb-2"
              style={{ color: "var(--ticker-up)" }}
            >
              {stats.analyses.toString().padStart(2, "0")}
            </span>
            <span className="text-xs text-[var(--text-secondary)]">
              Comprehensive reports
            </span>
          </div>
          <div className="px-6 flex flex-col">
            <span className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] mb-3 uppercase">
              · LATEST STATUS
            </span>
            <span className="font-mono text-2xl font-bold text-[var(--positive-color)] mb-2 mt-1 tracking-widest uppercase">
              {stats.latest ? stats.latest.status : "COMPLETED"}
            </span>
            <span className="text-xs text-[var(--text-muted)] mt-auto">
              Last run: 2 hrs ago
            </span>
          </div>
        </div>

        {/* Actions Row */}
        <div className="grid grid-cols-2 gap-0 surface-card animate-fade-up fade-delay-3 divide-x divide-[var(--border-color)]">
          <div className="p-6 pb-7 flex flex-col">
            <span className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] mb-4">
              01 / INGEST
            </span>
            <h3 className="font-display text-[28px] font-semibold mb-3 text-[var(--text-primary)] leading-tight">
              Upload Documents
            </h3>
            <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed mb-5 flex-1 pr-2">
              Import bank statements, GST reports, or Excel sales sheets. All
              formats processed and indexed for multi-agent analysis.
            </p>
            <button
              onClick={() => navigate("/documents")}
              className="btn-select py-3 px-5 font-mono text-[10px] tracking-wider flex justify-between items-center w-full"
            >
              <span className="mr-6 uppercase font-bold">SELECT FILES</span>{" "}
              <span>→</span>
            </button>
          </div>
          <div className="p-6 pb-7 flex flex-col">
            <span className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] mb-4">
              02 / PROCESS
            </span>
            <h3 className="font-display text-[28px] font-semibold mb-3 text-[var(--text-primary)] leading-tight">
              Run Analysis
            </h3>
            <p className="text-[12px] text-[var(--text-secondary)] leading-relaxed mb-5 flex-1 pr-2">
              Deploy all 5 AI agents across your documents. Generates a full
              financial health report with risk flags and forecasts.
            </p>
            <button
              onClick={() => navigate("/analysis")}
              className="btn-generate py-3 px-5 font-mono text-[10px] tracking-wider flex justify-between items-center w-full"
            >
              <span className="mr-6 uppercase font-bold">GENERATE REPORT</span>{" "}
              <span>→</span>
            </button>
          </div>
        </div>
      </div>

      {/* Right Sidebar (320px logic) */}
      <div className="lg:col-span-4 w-full flex flex-col space-y-4">
        {/* AI AGENTS Panel */}
        <div className="surface-card p-5 animate-fade-up fade-delay-4">
          <div className="flex justify-between items-center border-b border-[var(--border-color)] pb-4 mb-5 font-mono text-[9px] tracking-widest text-[var(--primary-accent)] uppercase">
            <span>AI AGENTS</span>
            <span className="text-[var(--text-muted)]">5/5 ONLINE</span>
          </div>
          <div className="space-y-3 font-mono text-[10px]">
            {[
              "Financial Analyzer",
              "Cash Flow Forecaster",
              "Risk Detector",
              "Compliance Agent",
              "Explainability Agent",
            ].map((agent, i) => (
              <div key={i} className="flex justify-between items-center group">
                <div className="flex items-center space-x-3 text-[var(--text-primary)]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--electric-green)] shadow-[0_0_6px_var(--electric-green)] group-hover:scale-150 transition-transform"></span>
                  <span className="group-hover:text-[var(--electric-green)] transition-colors font-semibold tracking-wide">
                    {agent}
                  </span>
                </div>
                <span className="text-[var(--electric-green)] text-[9px] tracking-widest">
                  READY
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* LAST ANALYSIS SNAPSHOT Panel */}
        <div className="surface-card p-5 pb-6 animate-fade-up fade-delay-5">
          <div className="flex justify-between items-center border-b border-[var(--border-color)] pb-4 mb-5 font-mono text-[9px] tracking-widest text-[var(--primary-accent)] uppercase">
            <span>LAST ANALYSIS SNAPSHOT</span>
            <span className="text-[var(--text-muted)]">METADATA</span>
          </div>
          <div className="font-mono text-[10px] text-[var(--text-muted)] space-y-3 pl-1">
            <div className="flex tracking-wide">
              <span className="text-[var(--primary-accent)] mr-3 opacity-60">
                ›
              </span>{" "}
              run time:{" "}
              <span className="text-[var(--text-primary)] ml-2">
                {formatSnapshotTime(
                  stats.latest?.completed_at || stats.latest?.created_at,
                )}
              </span>
            </div>
            <div className="flex tracking-wide">
              <span className="text-[var(--primary-accent)] mr-3 opacity-60">
                ›
              </span>{" "}
              input docs used:{" "}
              <span className="text-[var(--text-primary)] ml-2">
                {stats.latest?.document_count ?? 0}
              </span>
            </div>
            <div className="flex tracking-wide">
              <span className="text-[var(--primary-accent)] mr-3 opacity-60">
                ›
              </span>{" "}
              report version:{" "}
              <span className="text-[var(--text-primary)] ml-2">
                {stats.latest?.analysis_id
                  ? `RPT-${stats.latest.analysis_id.slice(0, 8).toUpperCase()}`
                  : "N/A"}
              </span>
            </div>
            <div className="flex tracking-wide">
              <span className="text-[var(--primary-accent)] mr-3 opacity-60">
                ›
              </span>{" "}
              status:{" "}
              <span className="text-[var(--secondary-accent)] ml-2 uppercase">
                {stats.latest?.status || "NOT GENERATED"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
