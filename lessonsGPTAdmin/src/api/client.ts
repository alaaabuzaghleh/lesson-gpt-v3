import type {
  Book,
  ExtractionJob,
  ExtractionJobRequest,
  HealthResponse,
  JobEvent,
  SearchHit,
  SearchRequest,
} from '../types/api'

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<HealthResponse>('/health'),

  listBooks: (limit = 100, offset = 0) =>
    request<{ items: Book[] }>(`/api/v1/books?limit=${limit}&offset=${offset}`),

  getBook: (resourceId: string) => request<Book>(`/api/v1/books/${resourceId}`),

  uploadBook: async (file: File, metadata: Record<string, unknown>) => {
    const form = new FormData()
    form.append('file', file)
    form.append('metadata', JSON.stringify(metadata))
    return request<Book>('/api/v1/books', { method: 'POST', body: form })
  },

  createJob: (resourceId: string, body: ExtractionJobRequest) =>
    request<ExtractionJob>(`/api/v1/books/${resourceId}/extraction-jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  listJobs: (params?: { status?: string; book_resource_id?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.book_resource_id) q.set('book_resource_id', params.book_resource_id)
    q.set('limit', String(params?.limit ?? 100))
    q.set('offset', String(params?.offset ?? 0))
    return request<{ items: ExtractionJob[] }>(`/api/v1/jobs?${q}`)
  },

  getJob: (jobId: string) => request<ExtractionJob>(`/api/v1/jobs/${jobId}`),

  cancelJob: (jobId: string) =>
    request<ExtractionJob>(`/api/v1/jobs/${jobId}/cancel`, { method: 'POST' }),

  retryJob: (jobId: string) =>
    request<ExtractionJob>(`/api/v1/jobs/${jobId}/retry`, { method: 'POST' }),

  listEvents: (jobId: string, afterId = 0, limit = 500) =>
    request<{ items: JobEvent[] }>(`/api/v1/jobs/${jobId}/events?after_id=${afterId}&limit=${limit}`),

  qualityReport: (jobId: string) =>
    request<Record<string, unknown>>(`/api/v1/jobs/${jobId}/quality-report`),

  manifest: (jobId: string) =>
    request<Record<string, unknown>>(`/api/v1/jobs/${jobId}/manifest`),

  structure: (jobId: string) =>
    request<Record<string, unknown>>(`/api/v1/jobs/${jobId}/structure`),

  errors: (jobId: string) =>
    request<{ items: Record<string, unknown>[] }>(`/api/v1/jobs/${jobId}/errors`),

  search: (body: SearchRequest) =>
    request<{ items: SearchHit[] }>('/api/v1/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  artifactUrl: (jobId: string, relativePath: string) =>
    `${BASE}/api/v1/jobs/${jobId}/artifacts/${relativePath}`,
}

export function subscribeJobEvents(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  afterId = 0,
): () => void {
  const url = `${BASE}/api/v1/jobs/${jobId}/events/stream?after_id=${afterId}`
  const source = new EventSource(url)

  source.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data) as JobEvent)
    } catch {
      /* ignore malformed */
    }
  }

  const handlers = ['queued', 'running', 'stage', 'progress', 'completed', 'failed', 'cancelled'] as const
  for (const type of handlers) {
    source.addEventListener(type, (e: MessageEvent) => {
      try {
        onEvent(JSON.parse(e.data) as JobEvent)
      } catch {
        /* ignore */
      }
    })
  }

  return () => source.close()
}
