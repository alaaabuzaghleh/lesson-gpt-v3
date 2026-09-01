import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { ExtractionJob, JobStatus } from '../types/api'
import {
  EmptyState,
  ErrorBanner,
  LoadingSpinner,
  ProgressBar,
  StatusBadge,
  formatDate,
} from '../components/ui'

const STATUSES: (JobStatus | 'all')[] = [
  'all', 'queued', 'running', 'completed', 'failed', 'cancelled',
]

export function JobsPage() {
  const [jobs, setJobs] = useState<ExtractionJob[]>([])
  const [filter, setFilter] = useState<JobStatus | 'all'>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await api.listJobs({
        status: filter === 'all' ? undefined : filter,
        limit: 200,
      })
      setJobs(res.items)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    setLoading(true)
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [load])

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Extraction jobs</h1>
          <p>Track pipeline progress, cancel, or retry failed runs</p>
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <div className="filter-bar">
        {STATUSES.map((s) => (
          <button
            key={s}
            type="button"
            className={`filter-chip${filter === s ? ' active' : ''}`}
            onClick={() => setFilter(s)}
          >
            {s}
          </button>
        ))}
      </div>

      <section className="card">
        {loading && jobs.length === 0 ? (
          <LoadingSpinner />
        ) : jobs.length === 0 ? (
          <EmptyState message="No jobs match this filter." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Book</th>
                  <th>Status</th>
                  <th>Stage</th>
                  <th>Progress</th>
                  <th>Page</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <Link to={`/jobs/${job.job_id}`} className="link-mono">
                        {job.job_id.slice(0, 12)}…
                      </Link>
                    </td>
                    <td>
                      <Link to={`/books/${job.book_resource_id}`} className="muted">
                        {job.book_resource_id.slice(0, 10)}…
                      </Link>
                    </td>
                    <td><StatusBadge status={job.status} /></td>
                    <td>{job.stage ?? '—'}</td>
                    <td style={{ minWidth: 140 }}>
                      <ProgressBar value={job.progress} />
                    </td>
                    <td className="muted">
                      {job.current_page != null && job.total_pages != null
                        ? `${job.current_page} / ${job.total_pages}`
                        : '—'}
                    </td>
                    <td className="muted">{formatDate(job.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
