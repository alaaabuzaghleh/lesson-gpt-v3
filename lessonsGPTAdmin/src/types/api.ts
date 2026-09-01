export type JobStatus =
  | 'queued'
  | 'running'
  | 'cancel_requested'
  | 'cancelled'
  | 'failed'
  | 'completed'

export interface HealthResponse {
  status: string
  service: string
  version: string
  workers: number
  opensearch_index: string
}

export interface Book {
  resource_id: string
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
  payload: Record<string, unknown>
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
