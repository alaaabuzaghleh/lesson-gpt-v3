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
import { stageLabel, statusLabel, t } from '../i18n/ar'

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
      setError(e instanceof Error ? e.message : t.jobs.loadError)
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    setLoading(true)
    load()
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [load])

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{t.jobs.title}</h1>
          <p>{t.jobs.subtitle}</p>
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
            {s === 'all' ? t.common.all : statusLabel(s)}
          </button>
        ))}
      </div>

      <section className="card">
        {loading && jobs.length === 0 ? (
          <LoadingSpinner />
        ) : jobs.length === 0 ? (
          <EmptyState message={t.jobs.noMatch} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.jobs.job}</th>
                  <th>{t.jobs.book}</th>
                  <th>{t.jobs.status}</th>
                  <th>{t.jobs.stage}</th>
                  <th>{t.jobs.progress}</th>
                  <th>{t.jobs.page}</th>
                  <th>{t.jobs.updated}</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <Link to={`/jobs/${job.job_id}`} className="link-mono" dir="ltr">
                        {job.job_id.slice(0, 12)}…
                      </Link>
                    </td>
                    <td>
                      <Link to={`/books/${job.book_resource_id}`} className="muted" dir="ltr">
                        {job.book_resource_id.slice(0, 10)}…
                      </Link>
                    </td>
                    <td><StatusBadge status={job.status} /></td>
                    <td>{stageLabel(job.stage)}</td>
                    <td style={{ minWidth: 140 }}>
                      <ProgressBar value={job.progress} />
                    </td>
                    <td className="muted">
                      {job.current_page != null && job.total_pages != null
                        ? `${job.current_page} / ${job.total_pages}`
                        : t.common.dash}
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
