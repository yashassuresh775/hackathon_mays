import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getInterview, submitPacketResponse } from '../api'
import './PacketPage.css'

const MAX_SELECT = 3
const NUM_QUESTIONS = 6

export default function PacketPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [corrections, setCorrections] = useState('')
  const [selected, setSelected] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    let cancelled = false
    getInterview(id)
      .then((d) => { if (!cancelled) setData(d) })
      .catch((e) => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [id])

  function toggleQuestion(i) {
    const idx = String(i)
    setSelected((prev) => {
      if (prev.includes(idx)) return prev.filter((x) => x !== idx)
      if (prev.length >= MAX_SELECT) return prev
      return [...prev, idx]
    })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await submitPacketResponse(id, {
        corrections: corrections.trim(),
        selected_question_ids: selected,
      })
      setSubmitted(true)
    } catch (err) {
      setError(err.message || 'Failed to submit')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="packet-page"><p className="loading">Loading…</p></div>
  if (error && !data) return <div className="packet-page"><p className="error-text">{error}</p></div>

  return (
    <div className="packet-page">
      <header className="packet-header">
        <h1>Pre-Interview Packet</h1>
        <p>{data?.company_name && `${data.company_name} — `}What we learned & what you’d like to discuss</p>
      </header>

      {data?.packet_text && (
        <section className="card packet-content">
          <h2>Here’s what we learned about your organization</h2>
          <pre className="packet-text">{data.packet_text}</pre>
        </section>
      )}

      {submitted ? (
        <section className="card success-card">
          <p>Thank you. Your corrections and question choices have been saved. The interviewer will use them to make the conversation more relevant.</p>
        </section>
      ) : (
        <section className="card form-card">
          <h2>Help us get it right</h2>
          <p className="hint">What did we get wrong or miss? (optional)</p>
          <form onSubmit={handleSubmit}>
            <textarea
              value={corrections}
              onChange={(e) => setCorrections(e.target.value)}
              placeholder="Tell us what to correct or add..."
              rows={4}
              disabled={submitting}
            />
            <p className="hint">Which of these questions interest you most? (Pick 2–3)</p>
            <div className="question-checkboxes">
              {Array.from({ length: NUM_QUESTIONS }, (_, i) => (
                <label key={i} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={selected.includes(String(i))}
                    onChange={() => toggleQuestion(i)}
                    disabled={submitting}
                  />
                  <span>Question {i + 1}</span>
                </label>
              ))}
            </div>
            {error && <p className="error-text">{error}</p>}
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Saving…' : 'Submit'}
            </button>
          </form>
        </section>
      )}
    </div>
  )
}
