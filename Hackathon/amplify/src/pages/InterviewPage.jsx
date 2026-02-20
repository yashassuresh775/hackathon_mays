import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getInterview } from '../api'
import './InterviewPage.css'

export default function InterviewPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    getInterview(id)
      .then((d) => { if (!cancelled) setData(d) })
      .catch((e) => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [id])

  if (loading) return <div className="interview-page"><p className="loading">Loading…</p></div>
  if (error && !data) return <div className="interview-page"><p className="error-text">{error}</p></div>

  const response = data?.packet_response

  return (
    <div className="interview-page">
      <header className="interview-header">
        <Link to="/" className="back-link">← Back to home</Link>
        <h1>Interview: {data?.company_name}</h1>
        <p>Interview ID: <code>{data?.interview_id}</code></p>
      </header>

      {data?.brief_text && (
        <section className="card">
          <h2>Interviewer brief (2–3 pages)</h2>
          <pre className="brief-text">{data.brief_text}</pre>
        </section>
      )}

      {data?.packet_text && (
        <section className="card">
          <h2>Pre-interview packet (sent to interviewee)</h2>
          <pre className="packet-text">{data.packet_text}</pre>
        </section>
      )}

      {response && (response.corrections || (response.selected_question_ids && response.selected_question_ids.length > 0)) && (
        <section className="card response-card">
          <h2>Interviewee response (use for warm opening & focus)</h2>
          {response.corrections && (
            <div className="response-block">
              <h3>What they said we got wrong or missed</h3>
              <p className="corrections">{response.corrections}</p>
            </div>
          )}
          {response.selected_question_ids?.length > 0 && (
            <div className="response-block">
              <h3>Questions they want to discuss (2–3)</h3>
              <ul>
                {response.selected_question_ids.map((q, i) => (
                  <li key={i}>Question {Number(q) + 1}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {data && (!response || (!response.corrections && (!response.selected_question_ids || response.selected_question_ids.length === 0))) && (
        <section className="card hint-card">
          <p>No interviewee response yet. Share the packet link so they can submit corrections and select 2–3 questions.</p>
        </section>
      )}
    </div>
  )
}
