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
      setDocuments(response.data.documents);
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
        <LoadingSpinner size="large" />
      </div>
    );
  }

  return (
    <div className="flex flex-col space-y-6 animate-fade-up">
      <h1 className="font-display text-4xl mb-4 text-[var(--text-primary)] tracking-wide">Documents</h1>

      <div className="surface-card p-8">
        <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)]">Upload Documents</h2>
        <form onSubmit={handleUpload} className="space-y-6">
          <div>
            <input
              type="file"
              onChange={handleFileChange}
              multiple
              accept=".pdf,.xlsx,.xls"
              className="block w-full text-sm text-[var(--text-muted)]
                file:mr-4 file:py-2.5 file:px-6
                file:rounded-sm file:border file:border-[var(--primary-accent)]
                file:text-xs file:font-mono file:tracking-wider
                file:bg-transparent file:text-[var(--primary-accent)]
                hover:file:bg-[var(--primary-accent)] hover:file:text-[var(--bg-color)] file:transition-colors file:cursor-pointer custom-file-input"
            />
            <p className="text-xs font-mono text-[var(--text-muted)] mt-4 tracking-wide">
              ACCEPTED FORMATS: PDF, EXCEL (.XLSX, .XLS). MAX 10MB PER FILE.
            </p>
          </div>

          <button
            type="submit"
            disabled={uploading}
            className="btn-select py-3 px-8 font-mono text-[11px] tracking-wider uppercase font-bold"
          >
            {uploading ? 'UPLOADING...' : 'UPLOAD FILES'}
          </button>
        </form>
      </div>

      <div className="surface-card p-8">
        <h2 className="font-display text-2xl font-semibold mb-6 text-[var(--text-primary)]">Your Documents</h2>

        {documents.length === 0 ? (
          <p className="text-[var(--text-secondary)] font-mono text-sm">No documents uploaded yet.</p>
        ) : (
          <div className="space-y-4">
            {documents.map((doc) => (
              <div
                key={doc.document_id}
                className="border border-[var(--border-color)] rounded-sm p-5 flex flex-col md:flex-row md:justify-between md:items-center bg-[var(--surface-card)] hover:brightness-110 transition-all"
              >
                <div className="mb-4 md:mb-0">
                  <h3 className="font-mono text-sm font-semibold text-[var(--text-primary)] opacity-90">{doc.filename}</h3>
                  <div className="flex items-center space-x-4 mt-2">
                    <p className="font-mono text-[10px] text-[var(--text-muted)] tracking-wider">
                      {new Date(doc.uploaded_at).toLocaleDateString()} •{' '}
                      {(doc.size_bytes / 1024).toFixed(2)} KB
                    </p>
                    <span
                      className={`inline-block px-2.5 py-1 text-[9px] font-mono tracking-widest uppercase rounded-sm border ${doc.processed
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
                  className="font-mono text-[10px] tracking-wider uppercase text-[var(--negative-color)] hover:text-red-400 px-4 py-2 border border-transparent hover:border-[var(--negative-color)] transition-colors rounded-sm"
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
