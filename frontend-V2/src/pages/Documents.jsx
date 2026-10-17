import React, { useState, useEffect } from 'react';
import { getDocuments, uploadDocuments, deleteDocument } from '../services/api';
import LoadingSpinner from '../components/Common/LoadingSpinner';

const Documents = () => {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState(null);

  const fetchDocuments = async () => {
    try {
      const response = await getDocuments();
      setDocuments(response.data.documents || []);
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

        {documents.length === 0 ? (
          <p className="text-[var(--text-secondary)] font-mono text-sm">No documents uploaded yet.</p>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <div
                key={doc.document_id}
                className="border border-[var(--border-color)] rounded-sm p-4 flex flex-col md:flex-row md:justify-between md:items-center gap-3"
              >
                <div className="mb-2 md:mb-0">
                  <h3 className="font-mono text-sm font-semibold text-[var(--text-primary)]">{doc.filename}</h3>
                  <div className="flex items-center space-x-3 mt-1">
                    <p className="font-mono text-[10px] text-[var(--text-muted)] tracking-wider">
                      {new Date(doc.uploaded_at).toLocaleDateString()} &bull; {(doc.size_bytes / 1024).toFixed(2)} KB
                    </p>
                    <span
                      className={`inline-block px-2 py-1 text-[9px] font-medium tracking-wider uppercase rounded-sm border ${doc.processed
                          ? 'border-[var(--positive-color)] text-[var(--positive-color)]'
                          : 'border-[var(--primary-accent)] text-[var(--primary-accent)]'
                        }`}
                    >
                      {doc.processed ? 'Processed' : 'Processing'}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => handleDelete(doc.document_id)}
                  className="font-mono text-[10px] tracking-wider uppercase text-[var(--negative-color)] hover:opacity-80 px-3 py-1 border border-transparent rounded-sm transition-colors"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Documents;
