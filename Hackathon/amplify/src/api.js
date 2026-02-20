const API_BASE = import.meta.env.VITE_API_URL || ''

function base() {
  return API_BASE.replace(/\/$/, '')
}

export function apiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  return API_BASE ? `${base()}${p}` : `/api${p}`
}

/** Parse response as JSON; avoid "Unexpected end of JSON input" on empty/non-JSON body. */
async function parseJson(res) {
  const text = await res.text()
  if (!text || text.trim() === '') {
    if (!res.ok) throw new Error(res.statusText || `Request failed (${res.status})`)
    return {}
  }
  try {
    return JSON.parse(text)
  } catch {
    throw new Error(res.ok ? 'Invalid JSON from server' : (text.slice(0, 200) || res.statusText))
  }
}

export async function generateBrief(body) {
  const res = await fetch(apiUrl('generate-brief'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await parseJson(res)
  if (!res.ok) throw new Error(data.error || data.message || (res.status >= 500 ? 'Server error — check backend logs' : 'Request failed'))
  return data
}

/** Fetch external web data (Google, Bing, DuckDuckGo, News) for a company; writes to S3 for Kendra/Glue. */
export async function ingestExternal(body) {
  const res = await fetch(apiUrl('ingest-external'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await parseJson(res)
  if (!res.ok) throw new Error(data.error || data.message || (res.status >= 500 ? 'Server error — check backend logs' : 'Request failed'))
  return data
}

export async function getUploadUrl(body) {
  const res = await fetch(apiUrl('upload-url'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await parseJson(res)
  if (!res.ok) throw new Error(data.error || data.message || (res.status >= 500 ? 'Server error — check backend logs' : 'Request failed'))
  return data
}

/** Extract text from a document in S3 (Textract) and save to cleaned/ for brief context. */
export async function extractDocument(body) {
  const res = await fetch(apiUrl('extract-document'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await parseJson(res)
  if (!res.ok) throw new Error(data.error || data.message || (res.status >= 500 ? 'Server error — check backend logs' : 'Request failed'))
  return data
}

export async function getInterview(id) {
  const res = await fetch(apiUrl(`interview/${id}`))
  const data = await parseJson(res)
  if (!res.ok) throw new Error(data.error || data.message || (res.status >= 500 ? 'Server error — check backend logs' : 'Request failed'))
  return data
}

export async function submitPacketResponse(id, body) {
  const res = await fetch(apiUrl(`interview/${id}/packet-response`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await parseJson(res)
  if (!res.ok) throw new Error(data.error || data.message || (res.status >= 500 ? 'Server error — check backend logs' : 'Request failed'))
  return data
}

export async function sendPacket(body) {
  const res = await fetch(apiUrl('send-packet'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await parseJson(res)
  if (!res.ok) throw new Error(data.error || data.message || (res.status >= 500 ? 'Server error — check backend logs' : 'Request failed'))
  return data
}
