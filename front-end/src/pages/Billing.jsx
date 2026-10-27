import React, { useCallback, useEffect, useState } from "react";
import {
  Upload,
  Shield,
  AlertTriangle,
  RefreshCw,
  PieChart as PieIcon,
  Search,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import PageHeader from "../components/Common/PageHeader";
import LoadingSpinner from "../components/Common/LoadingSpinner";
import {
  getBillFlowOverview,
  importBillFlowCsv,
  getBillFlowTransactions,
  getBillFlowAnomalies,
  askBillFlowMoneyGone,
  categorizeBillFlow,
  getBillFlowCategories,
  updateBillFlowTransaction,
} from "../services/api";

const COLORS = ["#ff5a1f", "#ededea", "#a3a3a0", "#6b6b68", "#3a3a3a", "#f87171", "#4ade80", "#60a5fa"];

const tooltipStyle = {
  backgroundColor: "#111111",
  border: "1px solid #262626",
  borderRadius: 6,
  fontFamily: "IBM Plex Mono, monospace",
  fontSize: 12,
};

const money = (v) =>
  `$${Number(v || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function Billing() {
  const [overview, setOverview] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [anomalies, setAnomalies] = useState(null);
  const [moneyGone, setMoneyGone] = useState(null);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);
  const [detectedType, setDetectedType] = useState("");
  const [detectedConfidence, setDetectedConfidence] = useState(0);
  const [previewRows, setPreviewRows] = useState([]);

  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setErrors([]);
    const errs = [];
    const results = await Promise.allSettled([
      getBillFlowOverview(),
      getBillFlowTransactions({ limit: 50 }),
      getBillFlowAnomalies({ types: ["all"] }),
      askBillFlowMoneyGone({}),
      getBillFlowCategories(),
    ]);
    const [ov, tx, an, ask, cats] = results;
    if (ov.status === "fulfilled") setOverview(ov.value.data);
    else errs.push(ov.reason?.response?.data?.detail || "Overview failed");
    if (tx.status === "fulfilled") setTransactions(tx.value.data.transactions || []);
    else errs.push(tx.reason?.response?.data?.detail || "Transactions failed");
    if (an.status === "fulfilled") setAnomalies(an.value.data);
    else errs.push(an.reason?.response?.data?.detail || "Anomalies failed");
    if (ask.status === "fulfilled") setMoneyGone(ask.value.data);
    else errs.push(ask.reason?.response?.data?.detail || "Summary failed");
    if (cats.status === "fulfilled") setCategories(cats.value.data.categories || []);
    else errs.push(cats.reason?.response?.data?.detail || "Categories failed");
    setErrors(errs);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const isCsv = /\\.(csv|txt)$/i.test(file.name);
    setUploading(true);
    setMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      if (isCsv) {
        const res = await importBillFlowCsv(form);
        setMessage(
          res.data.status === "duplicate_file"
            ? "File already imported (hash match) — privacy-safe dedupe worked."
            : `Imported ${res.data.inserted} transactions (${res.data.document_type || "csv"}).`
        );
        setDetectedType(res.data.document_type || "");
        setDetectedConfidence(res.data.confidence || 0);
        await refresh();
    } else {
      const res = await importBillFlowCsv(form, true);
      setDetectedType(res.data.document_type || "");
      setDetectedConfidence(res.data.confidence || 0);
      setPreviewRows(res.data.preview || []);
      setPendingFile(file);
      setReviewOpen(true);
      setMessage(
        res.data.status === "rejected"
          ? res.data.message
          : `Detected: ${res.data.document_type || "document"} (${Math.round((res.data.confidence || 0) * 100)}%). Review extracted rows.`
      );
    }
    } catch (err) {
      setMessage(err.response?.data?.detail || "Import failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const confirmImport = async () => {
    if (!pendingFile) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", pendingFile);
      const res = await importBillFlowCsv(form);
      setMessage(
        res.data.status === "duplicate_file"
          ? "File already imported (hash match)."
          : `Imported ${res.data.inserted} transactions from ${res.data.document_type || "document"}.`
      );
      setReviewOpen(false);
      setPendingFile(null);
      setPreviewRows([]);
      await refresh();
    } catch (err) {
      setMessage(err.response?.data?.detail || "Import failed");
    } finally {
      setUploading(false);
    }
  };

  const handleCategorize = async () => {
    if (!transactions.length) {
      setMessage("Nothing to categorize — import a bank CSV first.");
      return;
    }
    try {
      const res = await categorizeBillFlow();
      const updated = res.data.updated ?? 0;
      const scanned = res.data.scanned ?? 0;
      setMessage(
        updated > 0
          ? `Re-categorized ${updated} of ${scanned} rows locally.`
          : `All ${scanned} rows already categorized.`
      );
      await refresh();
    } catch (err) {
      setMessage(err.response?.data?.detail || "Categorize failed");
    }
  };

  const handleCategoryChange = async (id, category) => {
    try {
      await updateBillFlowTransaction(id, { category });
      setTransactions((rows) =>
        rows.map((r) => (r.id === id ? { ...r, category, user_verified: true } : r))
      );
    } catch (err) {
      alert(err.response?.data?.detail || "Update failed");
    }
  };

  const filtered = search
    ? transactions.filter((t) => t.description.toLowerCase().includes(search.toLowerCase()))
    : transactions;

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  const pieData = (overview?.by_category || []).map((c) => ({
    name: c.category,
    value: c.total,
  }));

  const trend = moneyGone?.monthly_trend || [];

  return (
    <div>
      <PageHeader
        eyebrow="BillFlow · Local ledger"
        title="Billing"
        description="Bank CSV → 18 categories → anomalies. Data never leaves this machine."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--primary-accent)] px-3 py-2 text-[11px] uppercase tracking-[0.15em] text-[#0a0a0a]">
              <Upload className="h-3.5 w-3.5" />
              {uploading ? "Importing…" : "Import File"}
              <input type="file" accept=".csv,.txt,.xlsx,.xls,.pdf,.docx,.png,.jpg,.jpeg" className="hidden" onChange={handleUpload} disabled={uploading} />
            </label>
            <button
              type="button"
              onClick={handleCategorize}
              disabled={!transactions.length}
              className="inline-flex items-center gap-2 rounded-md border border-[var(--border-color)] px-3 py-2 text-[11px] uppercase tracking-[0.15em] text-[var(--text-secondary)] hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Categorize
            </button>
          </div>
        }
      />

      {message && (
        <p className="mb-4 rounded-md border border-[var(--border-color)] bg-[var(--surface-raised)] px-4 py-3 text-xs text-[var(--text-secondary)]">
          {message}
        </p>
      )}

      {errors.length > 0 && (
        <div className="mb-4 rounded-md border border-[var(--negative-color)] bg-[var(--surface-raised)] px-4 py-3 text-xs text-[var(--negative-color)]">
          {errors.join(" · ")}
        </div>
      )}

      {!loading && transactions.length === 0 && (
        <div className="surface-card mb-6 p-6 text-center">
          <p className="text-sm text-[var(--text-secondary)]">
            No transactions yet. Import a bank statement, invoice, receipt, or cost file.
          </p>
          <p className="mt-2 text-xs text-[var(--text-muted)]">
            Supported: CSV, TXT, XLSX, XLS, PDF, DOCX, PNG, JPG
          </p>
        </div>
      )}

      <div className="mb-4 flex items-center gap-2 text-[11px] uppercase tracking-[0.15em] text-[var(--positive-color)]">
        <Shield className="h-3.5 w-3.5" />
        Privacy-first · SQLite on-device · {overview?.privacy || "local_only"}
      </div>

      <div className="mb-6 grid gap-4 md:grid-cols-4">
        {[
          { label: "Spending", value: money(overview?.totals?.spending), tone: "negative" },
          { label: "Income", value: money(overview?.totals?.income), tone: "positive" },
          { label: "Net", value: money(overview?.totals?.net), tone: "accent" },
          {
            label: "Anomaly flags",
            value: overview?.anomaly_summary?.total_flags ?? 0,
            tone: "default",
          },
        ].map((tile) => (
          <div key={tile.label} className="surface-card p-5">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">{tile.label}</p>
            <p
              className={`mt-3 font-display text-5xl leading-none ${
                tile.tone === "positive"
                  ? "text-[var(--positive-color)]"
                  : tile.tone === "negative"
                    ? "text-[var(--negative-color)]"
                    : tile.tone === "accent"
                      ? "text-[var(--primary-accent)]"
                      : "text-[var(--text-primary)]"
              }`}
            >
              {tile.value}
            </p>
          </div>
        ))}
      </div>

      {moneyGone?.answer_text && (
        <div className="surface-card mb-6 p-5">
          <p className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-[var(--primary-accent)]">
            <PieIcon className="h-3.5 w-3.5" />
            Where did my money go?
          </p>
          <p className="text-sm text-[var(--text-secondary)]">{moneyGone.answer_text}</p>
          {overview?.anomaly_summary?.potential_annual_savings > 0 && (
            <p className="mt-3 text-xs text-[var(--text-muted)]">
              Potential annual savings from flags:{" "}
              <span className="text-[var(--primary-accent)]">
                {money(overview.anomaly_summary.potential_annual_savings)}
              </span>
            </p>
          )}
        </div>
      )}

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <div className="surface-card p-5">
          <p className="mb-4 text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">By category</p>
          {pieData.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => money(v)} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-16 text-center text-[11px] uppercase tracking-[0.15em] text-[var(--text-muted)]">
              Import a bank CSV to see categories
            </p>
          )}
          <ul className="mt-2 space-y-1">
            {(overview?.by_category || []).slice(0, 6).map((c) => (
              <li key={c.category} className="flex justify-between text-xs text-[var(--text-secondary)]">
                <span>{c.category}</span>
                <span>
                  {money(c.total)} · {c.share_pct}%
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="surface-card p-5">
          <p className="mb-4 text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Monthly trend</p>
          {trend.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={trend}>
                <CartesianGrid stroke="#262626" strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fill: "#6b6b68", fontSize: 10 }} />
                <YAxis tick={{ fill: "#6b6b68", fontSize: 10 }} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => money(v)} />
                <Bar dataKey="spending" fill="#ff5a1f" name="Spending" radius={[2, 2, 0, 0]} />
                <Bar dataKey="income" fill="#4ade80" name="Income" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-16 text-center text-[11px] uppercase tracking-[0.15em] text-[var(--text-muted)]">
              No monthly trend yet
            </p>
          )}
        </div>
      </div>

      <div className="surface-card mb-6 p-5">
        <p className="mb-4 flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">
          <AlertTriangle className="h-3.5 w-3.5 text-[var(--primary-accent)]" />
          Anomalies — duplicates, spikes, forgotten subscriptions
        </p>
        {!anomalies?.summary?.total_flags ? (
          <p className="text-xs text-[var(--text-muted)]">No anomalies flagged yet.</p>
        ) : (
          <ul className="space-y-3">
            {[
              ...(anomalies.duplicates || []),
              ...(anomalies.spikes || []),
              ...(anomalies.forgotten_subscriptions || []),
            ]
              .slice(0, 12)
              .map((f, idx) => (
                <li
                  key={`${f.type}-${idx}`}
                  className="flex flex-col gap-1 border-b border-[var(--border-color)] pb-3 last:border-0 md:flex-row md:items-start md:justify-between"
                >
                  <div>
                    <span className="mr-2 rounded border border-[var(--border-color)] px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-[var(--primary-accent)]">
                      {f.type}
                    </span>
                    <span className="text-xs text-[var(--text-secondary)]">{f.reason}</span>
                  </div>
                  {f.potential_savings > 0 && (
                    <span className="shrink-0 text-xs text-[var(--positive-color)]">
                      save ~{money(f.potential_savings)}
                    </span>
                  )}
                </li>
              ))}
          </ul>
        )}
      </div>

      <div className="surface-card p-5">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Transactions</p>
          <label className="relative block w-full max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-[var(--text-muted)]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search description"
              className="w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-color)] py-2 pl-8 pr-3 text-xs text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none"
            />
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead>
              <tr className="border-b border-[var(--border-color)] text-[10px] uppercase tracking-[0.15em] text-[var(--text-muted)]">
                <th className="pb-2 pr-3 font-normal">Date</th>
                <th className="pb-2 pr-3 font-normal">Description</th>
                <th className="pb-2 pr-3 font-normal">Amount</th>
                <th className="pb-2 font-normal">Category</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.id} className="border-b border-[var(--border-color)]/60">
                  <td className="py-2.5 pr-3 tabular-nums text-[var(--text-muted)]">{t.date}</td>
                  <td className="py-2.5 pr-3 text-[var(--text-secondary)]">
                    {t.description}
                    {t.is_recurring && (
                      <span className="ml-2 text-[10px] uppercase tracking-wider text-[var(--primary-accent)]">
                        recurring
                      </span>
                      )}
                  </td>
                  <td
                    className={`py-2.5 pr-3 tabular-nums ${
                      t.amount < 0 ? "text-[var(--negative-color)]" : "text-[var(--positive-color)]"
                    }`}
                  >
                    {money(t.amount)}
                  </td>
                  <td className="py-2.5">
                    <select
                      value={t.category || "Other"}
                      onChange={(e) => handleCategoryChange(t.id, e.target.value)}
                      className="rounded border border-[var(--border-color)] bg-[var(--bg-color)] px-2 py-1 text-[var(--text-primary)]"
                    >
                      {categories.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
              {!filtered.length && (
                <tr>
                  <td colSpan={4} className="py-10 text-center text-[var(--text-muted)]">
                    No transactions — import{" "}
                    <code className="text-[var(--primary-accent)]">data/billflow/sample_chase_transactions.csv</code>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      {reviewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="surface-card max-h-[80vh] w-full max-w-2xl overflow-auto p-6">
            <h3 className="mb-2 text-sm uppercase tracking-[0.15em] text-[var(--text-primary)]">
              Review extracted rows
            </h3>
            <p className="mb-4 text-xs text-[var(--text-muted)]">
              Type: {detectedType} · Confidence {Math.round(detectedConfidence * 100)}%
            </p>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--border-color)] text-[10px] uppercase tracking-[0.15em] text-[var(--text-muted)]">
                  <th className="pb-2 pr-3">Date</th>
                  <th className="pb-2 pr-3">Description</th>
                  <th className="pb-2 pr-3">Amount</th>
                  <th className="pb-2">Category</th>
                </tr>
              </thead>
              <tbody>
                {previewRows.map((r, i) => (
                  <tr key={i} className="border-b border-[var(--border-color)]/60">
                    <td className="py-2 pr-3 tabular-nums text-[var(--text-muted)]">{r.date}</td>
                    <td className="py-2 pr-3 text-[var(--text-secondary)]">{r.description}</td>
                    <td className="py-2 pr-3 tabular-nums text-[var(--text-primary)]">
                      ${Number(r.amount).toFixed(2)}
                    </td>
                    <td className="py-2 text-[var(--text-secondary)]">{r.category}</td>
                  </tr>
                ))}
                {!previewRows.length && (
                  <tr>
                    <td colSpan={4} className="py-6 text-center text-[var(--text-muted)]">No rows extracted</td>
                  </tr>
                )}
              </tbody>
            </table>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => { setReviewOpen(false); setPendingFile(null); setPreviewRows([]); }}
                className="rounded-md border border-[var(--border-color)] px-3 py-2 text-[11px] uppercase tracking-[0.15em] text-[var(--text-secondary)]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmImport}
                disabled={uploading || !previewRows.length}
                className="rounded-md border border-[var(--border-color)] bg-[var(--primary-accent)] px-3 py-2 text-[11px] uppercase tracking-[0.15em] text-[#0a0a0a] disabled:opacity-40"
              >
                {uploading ? "Importing…" : "Confirm import"}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}