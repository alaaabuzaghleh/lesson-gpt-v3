export type JobStatus =
  | 'queued'
  | 'running'
  | 'cancel_requested'
  | 'cancelled'
  | 'failed'
  | 'completed'

export type UserRole = 'super_admin' | 'admin' | 'student'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active?: boolean
  created_at?: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface HealthResponse {
  status: string
  service: string
  version: string
  workers: number
  opensearch_index: string
  database?: string
}

export interface CatalogSeo {
  seo_title_en?: string | null
  seo_title_ar?: string | null
  seo_meta_description_en?: string | null
  seo_meta_description_ar?: string | null
  seo_keywords_en?: string | null
  seo_keywords_ar?: string | null
  seo_description_en?: string | null
  seo_description_ar?: string | null
  slug_en?: string | null
  slug_ar?: string | null
  hero_image_path?: string | null
}

export type CatalogEntityType = 'country' | 'system' | 'grade' | 'subject'

export interface UpdateCatalogSeoPayload {
  seo_title_en?: string
  seo_title_ar?: string
  seo_meta_description_en?: string
  seo_meta_description_ar?: string
  seo_keywords_en?: string
  seo_keywords_ar?: string
  seo_description_en?: string
  seo_description_ar?: string
  slug_en?: string
  slug_ar?: string
}

export interface CatalogPath {
  country_id?: string
  country_name?: string
  education_system_id?: string
  education_system_name?: string
  grade_id?: string
  grade_name?: string
  subject_id?: string
  subject_name?: string
}

export interface Country {
  id: string
  code?: string | null
  name: string
  name_ar?: string | null
  is_active?: boolean
  seo?: CatalogSeo
  hero_image_url?: string
  has_custom_hero?: boolean
  education_systems?: EducationSystem[]
}

export interface EducationSystem {
  id: string
  country_id: string
  name: string
  name_ar?: string | null
  seo?: CatalogSeo
  hero_image_url?: string
  has_custom_hero?: boolean
  grades?: Grade[]
}

export interface Grade {
  id: string
  education_system_id: string
  name: string
  name_ar?: string | null
  sort_order?: number
  seo?: CatalogSeo
  hero_image_url?: string
  has_custom_hero?: boolean
  subjects?: Subject[]
}

export interface Subject {
  id: string
  grade_id: string
  name: string
  name_ar?: string | null
  seo?: CatalogSeo
  hero_image_url?: string
  has_custom_hero?: boolean
}

export interface Book {
  resource_id: string
  subject_id?: string | null
  catalog_path?: CatalogPath | null
  filename: string
  size_bytes: number
  sha256: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface JobLinks {
  self: string
  events: string
  event_stream: string
  quality: string
  manifest: string
  errors: string
}

export interface ExtractionJob {
  job_id: string
  book_resource_id: string
  status: JobStatus
  progress: number
  stage: string | null
  message: string | null
  current_page: number | null
  total_pages: number | null
  start_page: number
  end_page: number | null
  resume: boolean
  index_to_opensearch: boolean
  recreate_index: boolean
  metadata_overrides: Record<string, unknown>
  book_id: string | null
  extracted_records: number | null
  visual_assets: number | null
  indexed_records: number | null
  result: Record<string, unknown> | null
  error: string | null
  traceback?: string | null
  retry_of: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  updated_at: string
  links: JobLinks
}

export interface JobEvent {
  id: number
  job_id: string
  event_type: string
  stage?: string | null
  progress?: number | null
  message?: string | null
  payload: Record<string, unknown> | null
  created_at: string
}

export interface ExtractionJobRequest {
  start_page?: number
  end_page?: number | null
  resume?: boolean
  index_to_opensearch?: boolean
  recreate_index?: boolean
  metadata_overrides?: Record<string, unknown>
}

export interface SearchRequest {
  query: string
  filters?: Record<string, unknown>
  size?: number
}

export interface SearchHit {
  [key: string]: unknown
}

export interface SubjectOption {
  id: string
  label: string
  countryId: string
  systemId: string
  gradeId: string
}
