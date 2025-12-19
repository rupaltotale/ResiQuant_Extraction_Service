import { useState, useRef } from 'react';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export default function Home() {
  const [emailPdf, setEmailPdf] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const attachmentsInputRef = useRef(null);
  const emailPdfInputRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleEmailPdfChange = (e) => {
    const f = (e.target.files || [])[0] || null;
    setEmailPdf(f);
  };

  const handleClearEmailPdf = () => {
    setEmailPdf(null);
    if (emailPdfInputRef.current) {
      emailPdfInputRef.current.value = '';
    }
  };

  const handleAttachmentsChange = (e) => {
    setAttachments(Array.from(e.target.files || []));
  };

  const handleClearAttachments = () => {
    setAttachments([]);
    if (attachmentsInputRef.current) {
      attachmentsInputRef.current.value = '';
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setResult(null);
    setLoading(true);

    try {
      const formData = new FormData();
      if (emailPdf) formData.append('email_pdf', emailPdf);
      for (const f of attachments) {
        formData.append('attachments', f);
      }

      const res = await fetch(`${BACKEND_URL}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Upload failed' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }

      const json = await res.json();
      setResult(json);
    } catch (e) {
      setError(e.message || 'Unexpected error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: 16, fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto' }}>
      <h1>Document Uploader</h1>
      <p>Upload one or more documents with your email to see structured JSON.</p>

      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 12, marginTop: 16 }}>
        <label>
          Email Chain (PDF)
          <input
            type="file"
            accept="application/pdf"
            onChange={handleEmailPdfChange}
            required
            ref={emailPdfInputRef}
            style={{ width: '100%', padding: 8, marginTop: 4 }}
          />
          {emailPdf && (
            <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
              <small>{emailPdf.name}</small>
              <button type="button" onClick={handleClearEmailPdf} disabled={loading} style={{ padding: '6px 10px' }}>
                Clear Email PDF
              </button>
            </div>
          )}
        </label>

        <label>
          Attachments (optional, PDF/XLSX)
          <input
            type="file"
            accept="application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            multiple
            ref={attachmentsInputRef}
            onChange={handleAttachmentsChange}
            style={{ width: '100%', padding: 8, marginTop: 4 }}
          />
          {attachments.length > 0 && (
            <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
              <small>{attachments.length} attachment{attachments.length > 1 ? 's' : ''} selected</small>
              <button type="button" onClick={handleClearAttachments} disabled={loading} style={{ padding: '6px 10px' }}>
                Clear Attachments
              </button>
            </div>
          )}
        </label>

        <button type="submit" disabled={loading} style={{ padding: '10px 14px' }}>
          {loading ? 'Uploading…' : 'Upload'}
        </button>
      </form>

      {error && (
        <div style={{ marginTop: 16, color: '#b00020' }}>
          Error: {error}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 24 }}>
          <h2>Response</h2>
          <pre style={{ background: '#f6f8fa', padding: 12, overflowX: 'auto' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}

      <div style={{ marginTop: 24, opacity: 0.7 }}>
        <small>Backend: {BACKEND_URL}</small>
      </div>
    </div>
  );
}
