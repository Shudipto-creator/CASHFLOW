import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getDocuments, getAnalyses, runAnalysis } from "../services/api";
import LoadingSpinner from "../components/Common/LoadingSpinner";
import { useMode } from "../context/ModeContext";

const Analysis = () => {
  const [documents, setDocuments] = useState([]);
  const [analyses, setAnalyses] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const navigate = useNavigate();
  const { mode, modes, setMode, loading: modeLoading } = useMode();
  const confirmedDocuments = documents.filter(
    (doc) => doc.classification_status === 'confirmed' && doc.document_type !== 'other',
  );
  const documentsNeedingReview = documents.length - confirmedDocuments.length;

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [docsRes, analysesRes] = await Promise.all([
        getDocuments(),
        getAnalyses(),
      ]);

      setDocuments(docsRes.data.documents);
      setAnalyses(analysesRes.data.analyses);
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleRunAnalysis = async () => {
    if (!selectedDoc) {
      alert("Please select a document");
      return;
    }

    setRunning(true);

    try {
      const response = await runAnalysis({
        document_ids: [selectedDoc],
        analysis_type: "full",
        processing_mode: mode,
      });

      alert(
        `Analysis started in ${mode === "local" ? "Local" : "AWS"} mode! You will be notified when complete.`,
      );
      navigate(`/report/${response.data.analysis_id}`);
    } catch (error) {
      alert(error.response?.data?.error?.message || "Failed to start analysis");
    } finally {
      setRunning(false);
    }
  };

  const selectDocument = (docId) => {
    setSelectedDoc(docId);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-6 animate-fade-up">
      <h1 className="font-display text-4xl mb-6 text-[var(--text-primary)] tracking-wide">
        Analysis Control
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="surface-card p-8 flex flex-col h-full">
          <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)]">
            Run New Analysis
          </h2>

          <div className="mb-6">
            <label className="block font-mono text-[9px] tracking-widest text-[var(--text-muted)] mb-2 uppercase">
              Processing Mode
            </label>
            <select
              value={mode}
              disabled={modeLoading || running}
              onChange={(e) => setMode(e.target.value)}
              className="w-full bg-transparent border border-[var(--border-color)] text-[var(--text-primary)] font-mono text-sm px-3 py-2 focus:outline-none focus:border-[var(--primary-accent)]"
            >
              {(modes.length
                ? modes
                : [
                    { id: "aws", label: "AWS Mode" },
                    { id: "local", label: "Local Mode" },
                  ]
              ).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label || option.id}
                </option>
              ))}
            </select>
            <p className="mt-2 font-mono text-[10px] text-[var(--text-muted)] leading-relaxed">
              {mode === "local"
                ? "Local: sklearn document classifier + rule/ML analyzer. Chat uses Ollama."
                : "AWS: Bedrock Nova agents, Titan embeddings, and Sonic TTS."}
            </p>
          </div>

          {documents.length === 0 ? (
            <p className="text-[var(--text-secondary)] font-mono text-sm">
              No documents available. Please upload documents first.
            </p>
          ) : confirmedDocuments.length === 0 ? (
            <div className="space-y-4">
              <p className="text-[var(--text-secondary)] font-mono text-sm">
                Review and confirm document types before starting an analysis.
              </p>
              <button
                type="button"
                onClick={() => navigate('/documents')}
                className="btn-select w-full py-2 font-mono text-sm uppercase tracking-wider"
              >
                Review documents
              </button>
            </div>
          ) : (
            <>
              <div className="mb-6 flex-1">
                <p className="font-mono text-[9px] tracking-widest text-[var(--text-muted)] mt-2 mb-4 uppercase">
                  Select a confirmed document to analyze
                </p>
                {documentsNeedingReview > 0 && (
                  <p className="mb-3 font-mono text-[10px] text-[var(--primary-accent)]">
                    {documentsNeedingReview} document(s) still need type review.
                  </p>
                )}

                <div className="space-y-3 max-h-64 overflow-y-auto pr-2 custom-scrollbar">
                  {confirmedDocuments.map((doc) => (
                    <label
                      key={doc.document_id}
                      className={`flex items-center space-x-3 p-3 border rounded-sm cursor-pointer transition-colors
                        ${
                          selectedDoc === doc.document_id
                            ? "border-[var(--primary-accent)] bg-[rgba(205,127,50,0.05)]"
                            : "border-[var(--border-color)] hover:border-[var(--text-muted)]"
                        }`}
                    >
                      <input
                        type="radio"
                        name="document-select"
                        checked={selectedDoc === doc.document_id}
                        onChange={() => selectDocument(doc.document_id)}
                        className="border-[var(--primary-accent)] text-[var(--primary-accent)] focus:ring-[var(--primary-accent)] bg-transparent"
                      />
                      <span className="text-sm font-mono tracking-wide text-[var(--text-primary)] truncate">
                        {doc.filename}
                      </span>
                      <span className="ml-auto shrink-0 font-mono text-[9px] uppercase tracking-wider text-[var(--text-muted)]">
                        {doc.document_type?.replace(/_/g, ' ')}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              <button
                onClick={handleRunAnalysis}
                disabled={running || !selectedDoc}
                className="w-full bg-primary text-white py-2 rounded hover:bg-blue-700 disabled:bg-gray-400"
              >
                {running
                  ? "Starting Analysis..."
                  : `Start Analysis (${mode === "local" ? "Local" : "AWS"})`}
              </button>
            </>
          )}
        </div>

        <div className="surface-card p-8 flex flex-col h-full">
          <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)]">
            Analysis History
          </h2>

          {analyses.length === 0 ? (
            <p className="text-[var(--text-secondary)] font-mono text-sm">
              No analyses run yet.
            </p>
          ) : (
            <div className="space-y-4 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
              {analyses.map((analysis) => (
                <div
                  key={analysis.analysis_id}
                  className="border border-[var(--border-color)] rounded-sm p-5 cursor-pointer hover:border-[var(--secondary-accent)] transition-colors group"
                  onClick={() => navigate(`/report/${analysis.analysis_id}`)}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <p className="font-mono text-xs text-[var(--text-muted)] tracking-wider mb-1">
                        {new Date(analysis.created_at).toLocaleString()}
                      </p>
                      <p className="font-mono text-sm font-semibold text-[var(--text-primary)]">
                        {analysis.document_count} document(s)
                      </p>
                      <p className="font-mono text-[10px] text-[var(--text-muted)] mt-1 uppercase tracking-wider">
                        {(analysis.processing_mode || "aws") === "local"
                          ? "Local mode"
                          : "AWS mode"}
                      </p>
                    </div>

                    <span
                      className={`px-2 py-1 text-[9px] uppercase font-mono tracking-widest rounded-sm border ${
                        analysis.status === "completed"
                          ? "border-[var(--positive-color)] text-[var(--positive-color)]"
                          : analysis.status === "processing"
                            ? "border-[var(--primary-accent)] text-[var(--primary-accent)]"
                            : "border-[var(--negative-color)] text-[var(--negative-color)]"
                      }`}
                    >
                      {analysis.status}
                    </span>
                  </div>

                  {analysis.status === "completed" && (
                    <div className="mt-4 flex justify-end">
                      <span className="font-mono text-[10px] tracking-wider text-[var(--secondary-accent)] uppercase group-hover:underline">
                        View Report →
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Analysis;
