import type { ConfigResponse, ReportResponse } from './types'

/** Thrown for a request the backend rejected with a 4xx — e.g. an uploaded
 * CSV with no DateTime column. `message` is the backend's own explanation,
 * safe to show directly to the user (see main.py's HTTPException details). */
export class ApiError extends Error {}

export async function fetchConfig(): Promise<ConfigResponse> {
  const res = await fetch('/api/config')
  if (!res.ok) throw new ApiError(`Could not load app config (HTTP ${res.status}).`)
  return res.json()
}

export async function uploadReport(
  cyclicFiles: File[],
  logFiles: File[],
  variables: string[],
): Promise<ReportResponse> {
  const form = new FormData()
  cyclicFiles.forEach((f) => form.append('cyclic_files', f))
  logFiles.forEach((f) => form.append('log_files', f))
  if (variables.length) form.append('variables', variables.join(','))

  const res = await fetch('/api/report', { method: 'POST', body: form })
  if (!res.ok) {
    let message = `Upload failed (HTTP ${res.status}).`
    try {
      const body = await res.json()
      if (body?.detail) message = body.detail
    } catch {
      // non-JSON error body — keep the generic message
    }
    throw new ApiError(message)
  }
  return res.json()
}
