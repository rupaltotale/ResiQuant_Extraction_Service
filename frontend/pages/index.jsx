import { useState } from 'react';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

export default function Home() {
  const [emailPdf, setEmailPdf] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleEmailPdfChange = (e) => {
    const f = (e.target.files || [])[0] || null;
    setEmailPdf(f);
  };

  const handleAttachmentsChange = (e) => {
    setAttachments(Array.from(e.target.files || []));
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
            style={{ width: '100%', padding: 8, marginTop: 4 }}
          />
        </label>

        <label>
          Attachments (optional, PDF/XLSX)
          <input
            type="file"
            accept="application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            multiple
            onChange={handleAttachmentsChange}
            style={{ width: '100%', padding: 8, marginTop: 4 }}
          />
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
