import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { generateBrief, getUploadUrl, sendPacket, getInterview } from '../api'
import './Home.css'

const TEST_COMPANIES = [
  { name: 'Tesla', context: 'Electric vehicles and energy' },
  { name: 'Amazon', context: 'E-commerce and cloud' },
  { name: 'Acme Corp', context: '' },
]

export default function Home() {
  const navigate = useNavigate()
  const [companyName, setCompanyName] = useState('')
  const [context, setContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [fullBrief, setFullBrief] = useState(null)
  const [loadingFull, setLoadingFull] = useState(false)
  const [error, setError] = useState(null)
  const [uploadFile, setUploadFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadDone, setUploadDone] = useState(false)
  const [sendLink, setSendLink] = useState('')
  const [sendEmail, setSendEmail] = useState('')
  const [linkCopied, setLinkCopied] = useState(false)

  function tryTestCompany(company) {
    setCompanyName(company.name)
    setContext(company.context || '')
    setError(null)
    setResult(null)
    setFullBrief(null)
  }

  async function handleGenerate(e) {
    e.preventDefault()
    if (!companyName.trim()) return
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const data = await generateBrief({
        company_name: companyName.trim(),
        context: context.trim() || undefined,
      })
      setResult(data)
      setFullBrief(null)
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  async function loadFullBrief() {
    if (!result?.interview_id) return
    setLoadingFull(true)
    setError(null)
    try {
      const data = await getInterview(result.interview_id)
      setFullBrief(data)
    } catch (err) {
      setError(err.message || 'Failed to load full brief')
    } finally {
      setLoadingFull(false)
    }
  }

  async function handleUpload(e) {
    e.preventDefault()
    const file = uploadFile
    if (!file) return
    setError(null)
    setUploading(true)
    setUploadDone(false)
    try {
      const { upload_url, key } = await getUploadUrl({
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
      })
      await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
      })
      setUploadDone(true)
      setUploadFile(null)
    } catch (err) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function handleSendPacket() {
    if (!result?.interview_id) return
    setError(null)
    try {
      const data = await sendPacket({
        interview_id: result.interview_id,
        email: sendEmail.trim() || undefined,
      })
      setSendLink(data.shareable_link)
      if (data.shareable_link && navigator.clipboard) {
        navigator.clipboard.writeText(data.shareable_link)
        setLinkCopied(true)
        setTimeout(() => setLinkCopied(false), 2000)
      }
    } catch (err) {
      setError(err.message || 'Failed to get link')
    }
  }

  const displayLink = sendLink
    ? (sendLink.startsWith('http') ? sendLink : `${window.location.origin}${sendLink.startsWith('/') ? '' : '/'}${sendLink}`)
    : ''

  function copyLink() {
    if (displayLink && navigator.clipboard) {
      navigator.clipboard.writeText(displayLink)
      setLinkCopied(true)
      setTimeout(() => setLinkCopied(false), 2000)
    }
  }

  return (
    <div className="home">
      <section className="card form-card">
        <h2>Generate interviewer brief</h2>
        <p className="hint">Enter a company name (and optional context) or upload a document.</p>
        <p className="test-hint">Try a test case:</p>
        <div className="test-companies">
          {TEST_COMPANIES.map((c) => (
            <button
              key={c.name}
              type="button"
              className="btn-test"
              onClick={() => tryTestCompany(c)}
              disabled={loading}
            >
              {c.name}
            </button>
          ))}
        </div>
        <form onSubmit={handleGenerate}>
          <label>Company name <span className="required">*</span></label>
          <input
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="e.g. Acme Corp"
            disabled={loading}
            autoFocus
          />
          <label>Additional context (optional)</label>
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="e.g. Texas-based energy company, recent expansion..."
            rows={3}
            disabled={loading}
          />
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Generating…' : 'Generate brief'}
          </button>
        </form>
      </section>

      <section className="card upload-card">
        <h2>Upload document</h2>
        <p className="hint">Upload a PDF or document; it will be processed and can inform the brief.</p>
        <form onSubmit={handleUpload}>
          <input
            type="file"
            accept=".pdf,.txt,.csv,image/*"
            onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
            disabled={uploading}
          />
          <button type="submit" className="btn-secondary" disabled={!uploadFile || uploading}>
            {uploading ? 'Uploading…' : 'Upload'}
          </button>
          {uploadDone && <span className="upload-done">Uploaded.</span>}
        </form>
      </section>

      {error && (
        <section className="card error-card">
          <p className="error-text">{error}</p>
        </section>
      )}

      {result && (
        <section className="card result-card">
          <h2>Brief generated</h2>
          <p><strong>Company:</strong> {result.company_name}</p>
          <p><strong>Interview ID:</strong> <code>{result.interview_id}</code></p>
          <p className="preview-label">Brief preview</p>
          <pre className="preview">{result.brief_preview}</pre>
          <p className="success-msg">{result.message}</p>

          <div className="result-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={loadFullBrief}
              disabled={loadingFull}
            >
              {loadingFull ? 'Loading…' : 'Show full brief & packet here'}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => navigate(`/interview/${result.interview_id}`)}
            >
              Open in interview page
            </button>
          </div>

          {fullBrief && (
            <div className="full-brief">
              {fullBrief.brief_text && (
                <div className="full-section">
                  <h3>Interviewer brief (full)</h3>
                  <pre className="brief-full">{fullBrief.brief_text}</pre>
                </div>
              )}
              {fullBrief.packet_text && (
                <div className="full-section">
                  <h3>Pre-interview packet (full)</h3>
                  <pre className="packet-full">{fullBrief.packet_text}</pre>
                </div>
              )}
            </div>
          )}

          <div className="result-actions send-packet-actions">

            <div className="send-packet">
              <h3>Send to interviewee</h3>
              <button type="button" className="btn-secondary" onClick={handleSendPacket}>
                Get shareable link
              </button>
              {sendLink && (
                <div className="link-box">
                  <input type="text" readOnly value={displayLink} />
                  <button type="button" className="btn-small" onClick={copyLink}>
                    {linkCopied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
              )}
              <label>Or send by email (optional)</label>
              <input
                type="email"
                placeholder="interviewee@example.com"
                value={sendEmail}
                onChange={(e) => setSendEmail(e.target.value)}
              />
              <button
                type="button"
                className="btn-secondary"
                onClick={async () => {
                  try {
                    const d = await sendPacket({ interview_id: result.interview_id, email: sendEmail })
                    setSendLink(d.shareable_link || '')
                    setError(null)
                  } catch (e) {
                    setError(e.message)
                  }
                }}
              >
                Send email
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
