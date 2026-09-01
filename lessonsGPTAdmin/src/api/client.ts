import type {
  AuthResponse,
  Book,
  Country,
  ExtractionJob,
  ExtractionJobRequest,
  HealthResponse,
  JobEvent,
  SearchHit,
  SearchRequest,
  SubjectOption,
  User,
} from '../types/api'

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''

let authToken: string | null = null

export function setAuthToken(token: string | null) {
  authToken = token
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {}
  if (authToken) headers.Authorization = `Bearer ${authToken}`
  return { ...headers, ...(extra as Record<string, string> | undefined) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: authHeaders(init?.headers as HeadersInit),
  })
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
  login: (email: string, password: string) =>
    request<AuthResponse>('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<User>('/api/v1/auth/me'),

  listAdminUsers: () => request<{ items: User[] }>('/api/v1/admin/users'),

  createAdmin: (body: { email: string; password: string; full_name: string }) =>
    request<User>('/api/v1/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  catalogTree: () => request<{ items: Country[] }>('/api/v1/catalog/tree'),

  createCountry: (body: { name: string; name_ar?: string; code?: string }) =>
    request<Country>('/api/v1/catalog/countries', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  createEducationSystem: (body: { country_id: string; name: string; name_ar?: string }) =>
    request('/api/v1/catalog/education-systems', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  createGrade: (body: { education_system_id: string; name: string; name_ar?: string; sort_order?: number }) =>
    request('/api/v1/catalog/grades', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  createSubject: (body: { grade_id: string; name: string; name_ar?: string }) =>
    request('/api/v1/catalog/subjects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  health: () => request<HealthResponse>('/health'),

  listBooks: (params?: { limit?: number; offset?: number; subject_id?: string }) => {
    const q = new URLSearchParams()
    q.set('limit', String(params?.limit ?? 100))
    q.set('offset', String(params?.offset ?? 0))
    if (params?.subject_id) q.set('subject_id', params.subject_id)
    return request<{ items: Book[] }>(`/api/v1/books?${q}`)
  },

  getBook: (resourceId: string) => request<Book>(`/api/v1/books/${resourceId}`),

  uploadBook: async (file: File, subjectId: string, metadata: Record<string, unknown>) => {
    const form = new FormData()
    form.append('file', file)
    form.append('subject_id', subjectId)
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

  errors: (jobId: string) =>
    request<{ items: Record<string, unknown>[] }>(`/api/v1/jobs/${jobId}/errors`),

  search: (body: SearchRequest) =>
    request<{ items: SearchHit[] }>('/api/v1/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}

export function flattenSubjects(tree: Country[]): SubjectOption[] {
  const out: SubjectOption[] = []
  for (const c of tree) {
    for (const s of c.education_systems ?? []) {
      for (const g of s.grades ?? []) {
        for (const sub of g.subjects ?? []) {
          out.push({
            id: sub.id,
            countryId: c.id,
            systemId: s.id,
            gradeId: g.id,
            label: `${c.name_ar ?? c.name} › ${s.name_ar ?? s.name} › ${g.name_ar ?? g.name} › ${sub.name_ar ?? sub.name}`,
          })
        }
      }
    }
  }
  return out
}

export function subscribeJobEvents(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  afterId = 0,
): () => void {
  const tokenPart = authToken ? `&token=${encodeURIComponent(authToken)}` : ''
  const url = `${BASE}/api/v1/jobs/${jobId}/events/stream?after_id=${afterId}${tokenPart}`
  const source = new EventSource(url)

  const handle = (e: MessageEvent) => {
    try {
      onEvent(JSON.parse(e.data) as JobEvent)
    } catch {
      /* ignore */
    }
  }

  source.onmessage = handle
  for (const type of ['queued', 'running', 'stage', 'progress', 'completed', 'failed', 'cancelled']) {
    source.addEventListener(type, handle)
  }
  return () => source.close()
}
