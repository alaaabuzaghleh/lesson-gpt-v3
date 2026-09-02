import type {
  AuthResponse,
  Book,
  CatalogEntityType,
  Country,
  EducationSystem,
  ExtractionJob,
  ExtractionJobRequest,
  Grade,
  HealthResponse,
  JobEvent,
  SearchHit,
  SearchRequest,
  Subject,
  SubjectOption,
  UpdateCatalogSeoPayload,
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

  catalogTree: () =>
    request<{ items: Country[] }>(`/api/v1/catalog/tree?t=${Date.now()}`),

  listCountries: () => request<{ items: Country[] }>('/api/v1/catalog/countries'),

  listEducationSystems: (countryId?: string) => {
    const q = countryId ? `?country_id=${encodeURIComponent(countryId)}` : ''
    return request<{ items: EducationSystem[] }>(`/api/v1/catalog/education-systems${q}`)
  },

  listGrades: (educationSystemId?: string) => {
    const q = educationSystemId ? `?education_system_id=${encodeURIComponent(educationSystemId)}` : ''
    return request<{ items: Grade[] }>(`/api/v1/catalog/grades${q}`)
  },

  listSubjects: (gradeId?: string) => {
    const q = gradeId ? `?grade_id=${encodeURIComponent(gradeId)}` : ''
    return request<{ items: Subject[] }>(`/api/v1/catalog/subjects${q}`)
  },

  getCountry: (id: string) => request<Country>(`/api/v1/catalog/countries/${id}`),

  getEducationSystem: (id: string) =>
    request<EducationSystem>(`/api/v1/catalog/education-systems/${id}`),

  getGrade: (id: string) => request<Grade>(`/api/v1/catalog/grades/${id}`),

  getSubject: (id: string) => request<Subject>(`/api/v1/catalog/subjects/${id}`),

  getCatalogItem: (type: CatalogEntityType, id: string) => {
    switch (type) {
      case 'country':
        return api.getCountry(id)
      case 'system':
        return api.getEducationSystem(id)
      case 'grade':
        return api.getGrade(id)
      case 'subject':
        return api.getSubject(id)
    }
  },

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

  updateCountry: (id: string, body: Record<string, unknown>) =>
    request<Country>(`/api/v1/catalog/countries/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  deleteCountry: (id: string) =>
    request<void>(`/api/v1/catalog/countries/${id}`, { method: 'DELETE' }),

  updateEducationSystem: (id: string, body: Record<string, unknown>) =>
    request(`/api/v1/catalog/education-systems/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  deleteEducationSystem: (id: string) =>
    request<void>(`/api/v1/catalog/education-systems/${id}`, { method: 'DELETE' }),

  updateGrade: (id: string, body: Record<string, unknown>) =>
    request(`/api/v1/catalog/grades/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  deleteGrade: (id: string) =>
    request<void>(`/api/v1/catalog/grades/${id}`, { method: 'DELETE' }),

  updateSubject: (id: string, body: Record<string, unknown>) =>
    request(`/api/v1/catalog/subjects/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateCatalogSeo: (type: CatalogEntityType, id: string, body: UpdateCatalogSeoPayload) =>
    api.updateCatalogItem(type, id, body as Record<string, unknown>),

  updateCatalogItem: (type: CatalogEntityType, id: string, body: Record<string, unknown>) => {
    switch (type) {
      case 'country':
        return api.updateCountry(id, body)
      case 'system':
        return api.updateEducationSystem(id, body)
      case 'grade':
        return api.updateGrade(id, body)
      case 'subject':
        return api.updateSubject(id, body)
    }
  },

  createCountryFull: (body: Record<string, unknown>) =>
    request<Country>('/api/v1/catalog/countries', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  createEducationSystemFull: (body: Record<string, unknown>) =>
    request('/api/v1/catalog/education-systems', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  createGradeFull: (body: Record<string, unknown>) =>
    request('/api/v1/catalog/grades', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  createSubjectFull: (body: Record<string, unknown>) =>
    request('/api/v1/catalog/subjects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  uploadCatalogHero: async (type: CatalogEntityType, id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request(`/api/v1/catalog/${type}/${id}/hero`, { method: 'POST', body: form })
  },

  deleteCatalogHero: (type: CatalogEntityType, id: string) =>
    request(`/api/v1/catalog/${type}/${id}/hero`, { method: 'DELETE' }),

  catalogHeroUrl: (type: CatalogEntityType, id: string, cacheBust?: number) => {
    const suffix = cacheBust ? `?t=${cacheBust}` : ''
    return `${BASE}/api/v1/catalog/hero/${type}/${id}${suffix}`
  },

  deleteSubject: (id: string) =>
    request<{ deleted: boolean; linked_books: number }>(`/api/v1/catalog/subjects/${id}`, {
      method: 'DELETE',
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

  deleteBook: (resourceId: string) =>
    request<{ deleted: boolean; deleted_jobs: number }>(`/api/v1/books/${resourceId}`, {
      method: 'DELETE',
    }),

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
