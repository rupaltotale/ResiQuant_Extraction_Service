import { useState, useRef } from 'react';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

function Info({ sources, confidence, matchText }) {
  const [open, setOpen] = useState(false);
  const hasSources = sources && sources.length > 0;
  const hasConfidence = confidence && (typeof confidence.score === 'number' || confidence.explanation);
  if (!hasSources && !hasConfidence) return null;

  const highlightSnippet = (snippet, match) => {
    const s = String(snippet || '');
    const m = String(match || '').trim();
    if (!s) return s;
    if (!m) return s;
    const idx = s.toLowerCase().indexOf(m.toLowerCase());
    if (idx === -1) return s;
    const before = s.slice(0, idx);
    const mid = s.slice(idx, idx + m.length);
    const after = s.slice(idx + m.length);
    return (
      <>
        <span>{before}</span>
        <span style={{ background: 'yellow' }}>{mid}</span>
        <span>{after}</span>
      </>
    );
  };
  return (
    <span style={{ marginLeft: 8, position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Show info"
        style={{
          border: '1px solid #e1e4e8',
          background: '#f6f8fa',
          borderRadius: 12,
          padding: '0 6px',
          cursor: 'pointer',
          fontSize: 12,
          lineHeight: '18px',
        }}
      >
        ⓘ
      </button>
      {open && (
        <div
          role="dialog"
          style={{
            position: 'absolute',
            zIndex: 20,
            top: '120%',
            left: 0,
            minWidth: 280,
            maxWidth: 460,
            background: '#ffffff',
            border: '1px solid #e1e4e8',
            borderRadius: 6,
            boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
            padding: 10,
          }}
        >
          {hasConfidence && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 600 }}>Confidence</div>
              <div style={{ marginTop: 6, color: '#333' }}>
                <div><strong>Score:</strong> <span>{typeof confidence.score === 'number' ? confidence.score.toFixed(2) : '—'}</span></div>
                <div style={{ marginTop: 4 }}><strong>Why:</strong> <span>{confidence.explanation || '—'}</span></div>
              </div>
            </div>
          )}
          {hasSources && (
            <div>
              <div style={{ fontWeight: 600 }}>Provenance</div>
              <div style={{ display: 'grid', gap: 8, marginTop: 6 }}>
                {sources.map((s, idx) => (
                  <div key={idx}>
                    <div><strong>Doc:</strong> <span style={{ fontFamily: 'monospace' }}>{s.doc || '—'}</span></div>
                    <div style={{ marginTop: 4 }}>
                      <strong>Snippet:</strong>
                      <div style={{
                        marginTop: 4,
                        background: '#f6f8fa',
                        border: '1px dashed #e1e4e8',
                        borderRadius: 4,
                        padding: 8,
                        whiteSpace: 'normal',
                        overflowWrap: 'anywhere',
                        wordBreak: 'break-word',
                      }}>
                        {highlightSnippet(s.snippet || '—', s.match || matchText)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </span>
  );
}

export default function Home() {
  const [emailPdf, setEmailPdf] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const attachmentsInputRef = useRef(null);
  const emailPdfInputRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const formatSize = (bytes) => {
    if (!bytes && bytes !== 0) return '—';
    const kb = bytes / 1024;
    if (kb < 1024) return `${Math.round(kb)} KB`;
    return `${(kb / 1024).toFixed(2)} MB`;
  };

  const fileKind = (f) => {
    const name = String(f?.name || '').toLowerCase();
    const type = String(f?.type || '').toLowerCase();
    if (type.includes('pdf') || name.endsWith('.pdf')) return 'PDFs';
    if (type.includes('spreadsheet') || name.endsWith('.xlsx')) return 'Spreadsheets';
    return 'Other';
  };

  const groupedAttachments = (() => {
    const groups = { PDFs: [], Spreadsheets: [], Other: [] };
    attachments.forEach((f, index) => {
      const k = fileKind(f);
      groups[k].push({ file: f, index });
    });
    return groups;
  })();

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

  const handleRemoveAttachment = (idx) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
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
      <h1>ResiQuant Extraction Service</h1>
      <p>Upload the email chain PDF and optional attachments to see relevant information.</p>

      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 12, marginTop: 16 }}>
        <div style={{
          border: '1px solid #e1e4e8',
          borderRadius: 6,
          padding: 10,
          background: '#fafbfc'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <label htmlFor="email-pdf" style={{ fontWeight: 600 }}>Email Chain (PDF)</label>
            {emailPdf && (
              <button type="button" onClick={handleClearEmailPdf} disabled={loading} style={{ padding: '6px 10px' }}>
                Clear
              </button>
            )}
          </div>
          <input
            id="email-pdf"
            type="file"
            accept="application/pdf"
            onChange={handleEmailPdfChange}
            required
            ref={emailPdfInputRef}
            style={{ width: '100%', padding: 8, marginTop: 6 }}
          />
          {emailPdf && (
            <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
              <small>{emailPdf.name}</small>
            </div>
          )}
        </div>

        <div style={{
          border: '1px solid #e1e4e8',
          borderRadius: 6,
          padding: 10,
          background: '#fafbfc'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <label htmlFor="attachments-input" style={{ fontWeight: 600 }}>Attachments (optional, PDF/XLSX)</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {attachments.length > 0 && (
                <small style={{ color: '#444' }}>{attachments.length} attachment{attachments.length > 1 ? 's' : ''} selected</small>
              )}
              <button type="button" onClick={handleClearAttachments} disabled={loading || attachments.length === 0} style={{ padding: '6px 10px' }}>
                Clear All
              </button>
            </div>
          </div>
          <input
            id="attachments-input"
            type="file"
            accept="application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            multiple
            ref={attachmentsInputRef}
            onChange={handleAttachmentsChange}
            style={{ width: '100%', padding: 8, marginTop: 6 }}
          />
          {attachments.length > 0 && (
            <div style={{ display: 'grid', gap: 10, marginTop: 8 }}>
              {(['PDFs', 'Spreadsheets', 'Other']).map((groupName) => {
                const items = groupedAttachments[groupName] || [];
                if (items.length === 0) return null;
                return (
                  <div key={groupName}>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{groupName}</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 6 }}>
                      {items.map(({ file, index }) => (
                        <div key={`${groupName}-${index}`} style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 8,
                          border: '1px solid #e1e4e8',
                          background: '#ffffff',
                          borderRadius: 20,
                          padding: '6px 10px'
                        }}>
                          <span style={{ fontSize: 12 }}>{file.name}</span>
                          <span style={{ fontSize: 12, color: '#586069' }}>{formatSize(file.size)}</span>
                          <button
                            type="button"
                            onClick={() => handleRemoveAttachment(index)}
                            disabled={loading}
                            aria-label={`Remove ${file.name}`}
                            style={{
                              border: 'none',
                              background: '#f6f8fa',
                              borderRadius: 12,
                              padding: '0 6px',
                              cursor: 'pointer',
                              fontSize: 12,
                              lineHeight: '18px'
                            }}
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

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
        <div style={{ marginTop: 24, display: 'grid', gap: 16 }}>
          {/* LLM Parsed Box */}
          {result.llm_parsed && result.llm_parsed.status === 'ok' && (
            <div style={{ border: '1px solid #e1e4e8', borderRadius: 6, padding: 12 }}>
              <h2 style={{ marginTop: 0 }}>LLM Parsed</h2>
              <div style={{ display: 'grid', gap: 8 }}>
                {(() => { const fc = result.llm_parsed.data?.field_confidence || {}; return (
                  <>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <strong>Broker Name:</strong>
                  <span style={{ marginLeft: 6 }}>{result.llm_parsed.data?.broker_name ?? '—'}</span>
                  <Info sources={result.provenance?.broker_name} confidence={fc.broker_name} matchText={result.llm_parsed.data?.broker_name} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <strong>Broker Email:</strong>
                  <span style={{ marginLeft: 6 }}>{result.llm_parsed.data?.broker_email ?? '—'}</span>
                  <Info sources={result.provenance?.broker_email} confidence={fc.broker_email} matchText={result.llm_parsed.data?.broker_email} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <strong>Brokerage:</strong>
                  <span style={{ marginLeft: 6 }}>{result.llm_parsed.data?.brokerage ?? '—'}</span>
                  <Info sources={result.provenance?.brokerage} confidence={fc.brokerage} matchText={result.llm_parsed.data?.brokerage} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <strong>Brokerage Address:</strong>
                  <span style={{ marginLeft: 6 }}>{result.llm_parsed.data?.complete_brokerage_address ?? '—'}</span>
                  <Info sources={result.provenance?.complete_brokerage_address} confidence={fc.complete_brokerage_address} matchText={result.llm_parsed.data?.complete_brokerage_address} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <strong>Property Addresses:</strong>
                    <Info sources={result.provenance?.property_addresses} confidence={fc.property_addresses} />
                  </div>
                  <ul style={{ marginTop: 6 }}>
                    {(result.llm_parsed.data?.property_addresses || []).map((addr, i) => {
                      const per = (fc.property_addresses?.per_address || []).find((x) => x && x.address === addr) || null;
                      return (
                        <li key={i} style={{ display: 'flex', alignItems: 'center' }}>
                          <span>{addr}</span>
                          {per && (
                            <Info sources={null} confidence={{ score: per.score, explanation: per.explanation }} />
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
                  </>
                ); })()}
              </div>
            </div>
          )}

          {/* Raw Response for debugging */}
          <div>
            <h2>Raw Response</h2>
            <pre style={{ background: '#f6f8fa', padding: 12, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', wordBreak: 'break-word', overflowX: 'hidden' }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
