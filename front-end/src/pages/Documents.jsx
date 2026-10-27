import React, { useState, useEffect } from 'react';
import {
  getDocuments,
  uploadDocuments,
  deleteDocument,
  updateDocumentClassification,
} from '../services/api';
import LoadingSpinner from '../components/Common/LoadingSpinner';

const DOCUMENT_TYPE_OPTIONS = [
  { value: 'bank_statement', label: 'Bank statement' },
  { value: 'invoice', label: 'Invoice' },
  { value: 'profit_loss', label: 'Income statement / P&L' },
  { value: 'balance_sheet', label: 'Balance sheet' },
  { value: 'cash_flow_statement', label: 'Cash-flow statement' },
  { value: 'tax_document', label: 'Tax document' },
  { value: 'financial_document', label: 'Other financial document' },
  { value: 'other', label: 'Not a financial document' },
];

const Documents = () => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState(null);
  const [classificationChoices, setClassificationChoices] = useState({});
  const [savingClassificationId, setSavingClassificationId] = useState(null);

  const fetchDocuments = async () => {
    try {
      const response = await getDocuments();
      const nextDocuments = response.data.documents || [];
      setDocuments(nextDocuments);
      setClassificationChoices((previous) => {
        const next = { ...previous };
        nextDocuments.forEach((doc) => {
          if (!(doc.document_id in next)) {
            next[doc.document_id] = doc.document_type || doc.suggested_document_type || '';
          }
        });
        return next;
      });
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleFileChange = (e) => {
    setSelectedFiles(e.target.files);
  };

  const handleConfirmClassification = async (documentId) => {
    const documentType = classificationChoices[documentId];
    if (!documentType) return;

    setSavingClassificationId(documentId);
    try {
      const response = await updateDocumentClassification(documentId, documentType);
      setDocuments((current) => current.map((doc) => (
        doc.document_id === documentId ? response.data : doc
      )));
    } catch (error) {
      alert(error.response?.data?.detail || 'Could not save document type');
    } finally {
      setSavingClassificationId(null);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();

    if (!selectedFiles || selectedFiles.length === 0) {
      alert('Please select files to upload');
      return;
    }

    setUploading(true);

    const formData = new FormData();
    Array.from(selectedFiles).forEach((file) => {
      formData.append('files', file);
    });

    try {
      await uploadDocuments(formData);
      setSelectedFiles(null);
      e.target.reset();
      fetchDocuments();
    } catch (error) {
      alert(error.response?.data?.error?.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await deleteDocument(id);
      fetchDocuments();
    } catch (error) {
      alert('Failed to delete document');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <LoadingSpinner size="medium" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="border-b border-[var(--border-color)] pb-4 mb-6">
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-wide">Documents</h1>
        <p className="font-mono text-sm text-[var(--text-muted)] tracking-wide uppercase">
          Upload and manage your financial documents
        </p>
      </div>

      <div className="surface-card p-6">
        <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">Upload Documents</h2>
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <input
              type="file"
              onChange={handleFileChange}
              multiple
              accept=".pdf,.xlsx,.xls"
              className="block w-full text-sm text-[var(--text-muted)]
                file:mr-4 file:py-2 file:px-4
                file:rounded-sm file:border file:border-[var(--primary-accent)]
                file:text-xs file:font-medium file:tracking-wider
                file:bg-transparent file:text-[var(--primary-accent)]
                hover:file:bg-[var(--primary-accent)] hover:file:text-[var(--bg-color)] file:transition-colors file:cursor-pointer"
            />
            <p className="text-xs text-[var(--text-muted)] mt-2 tracking-wide">
              ACCEPTED FORMATS: PDF, EXCEL (.XLSX, .XLS). MAX 10MB PER FILE.
            </p>
          </div>

          <button
            type="submit"
            disabled={uploading}
            className="btn-primary py-2 px-6 text-sm font-medium uppercase tracking-wider disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading ? 'Uploading...' : 'Upload Files'}
          </button>
        </form>
      </div>

      <div className="surface-card p-6">
        <h2 className="font-mono text-sm font-semibold text-[var(--text-primary)] mb-4 uppercase tracking-wider border-b border-[var(--border-color)] pb-2">Your Documents</h2>

        <p className="mb-4 font-mono text-[10px] leading-relaxed text-[var(--text-muted)]">
          Confirm each detected document type before using it in an analysis. The classifier is a suggestion and may be wrong.
        </p>

        {documents.length === 0 ? (
          <p className="text-[var(--text-secondary)] font-mono text-sm">No documents uploaded yet.</p>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
                <div
                key={doc.document_id}
                className="border border-[var(--border-color)] rounded-sm p-4 flex flex-col gap-4"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0">
                    <h3 className="break-all font-mono text-sm font-semibold text-[var(--text-primary)]">{doc.filename}</h3>
                    <div className="mt-1 flex flex-wrap items-center gap-3">
                      <p className="font-mono text-[10px] text-[var(--text-muted)] tracking-wider">
                        {new Date(doc.uploaded_at).toLocaleDateString()} &bull; {(doc.size_bytes / 1024).toFixed(2)} KB
                      </p>
                      <span className={`inline-block border px-2 py-1 text-[9px] font-medium uppercase tracking-wider ${doc.processed
                        ? 'border-[var(--positive-color)] text-[var(--positive-color)]'
                        : 'border-[var(--primary-accent)] text-[var(--primary-accent)]'
                      }`}>
                        {doc.processed ? 'Analyzed' : 'Not analyzed'}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleDelete(doc.document_id)}
                    className="self-start font-mono text-[10px] uppercase tracking-wider text-[var(--negative-color)] hover:opacity-80"
                  >
                    Delete
                  </button>
                </div>

                <div className="flex flex-col gap-3 border-t border-[var(--border-color)] pt-3 sm:flex-row sm:items-end">
                  <label className="flex-1 font-mono text-[9px] uppercase tracking-widest text-[var(--text-muted)]">
                    Detected type: {doc.suggested_document_type || 'Unknown'}
                    {Number.isFinite(doc.classification_confidence) && (
                      <span className="ml-2 normal-case tracking-normal">
                        {Math.round(doc.classification_confidence * 100)}% confidence
                      </span>
                    )}
                    <select
                      value={classificationChoices[doc.document_id] ?? ''}
                      onChange={(event) => setClassificationChoices((current) => ({
                        ...current,
                        [doc.document_id]: event.target.value,
                      }))}
                      className="mt-1 block w-full border border-[var(--border-color)] bg-[var(--bg-color)] px-3 py-2 text-xs normal-case tracking-normal text-[var(--text-primary)]"
                    >
                      <option value="">Choose document type</option>
                      {DOCUMENT_TYPE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </label>
                  <div className="flex items-center gap-3">
                    <span className={`font-mono text-[9px] uppercase tracking-widest ${doc.classification_status === 'confirmed'
                      ? 'text-[var(--positive-color)]'
                      : doc.classification_status === 'rejected'
                        ? 'text-[var(--negative-color)]'
                        : doc.document_readable === false
                          ? 'text-[var(--negative-color)]'
                        : 'text-[var(--primary-accent)]'
                    }`}>
                      {doc.document_readable === false
                        ? 'Unreadable'
                        : doc.classification_status === 'confirmed'
                        ? 'Confirmed'
                        : doc.classification_status === 'rejected'
                          ? 'Not a financial document'
                          : 'Needs review'}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleConfirmClassification(doc.document_id)}
                      disabled={doc.document_readable === false || !classificationChoices[doc.document_id] || savingClassificationId === doc.document_id}
                      className="border border-[var(--primary-accent)] px-3 py-2 font-mono text-[9px] uppercase tracking-widest text-[var(--primary-accent)] hover:bg-[var(--primary-accent)] hover:text-[var(--bg-color)] disabled:opacity-40"
                    >
                      {savingClassificationId === doc.document_id ? 'Saving...' : 'Confirm type'}
                    </button>
                  </div>
                </div>
                {doc.classification_message && (
                  <p className="font-mono text-[10px] text-[var(--text-muted)]">{doc.classification_message}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Documents;
