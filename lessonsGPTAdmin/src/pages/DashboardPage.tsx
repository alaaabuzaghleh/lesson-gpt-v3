import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, BookOpen, CheckCircle2, XCircle } from 'lucide-react'
import { api } from '../api/client'
import type { ExtractionJob, HealthResponse } from '../types/api'
import {
  ErrorBanner,
  LoadingSpinner,
  ProgressBar,
  StatCard,
  StatusBadge,
  formatDate,
} from '../components/ui'

export function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [jobs, setJobs] = useState<ExtractionJob[]>([])
  const [bookCount, setBookCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [h, j, b] = await Promise.all([
          api.health(),
          api.listJobs({ limit: 200 }),
          api.listBooks(),
        ])
        if (!cancelled) {
          setHealth(h)
          setJobs(j.items)
          setBookCount(b.items.length)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load dashboard')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    const t = setInterval(load, 8000)
    return () => {
      cancelled = true
      clearInterval(t)
    }
  }, [])

  if (loading) return <LoadingSpinner />

  const running = jobs.filter((j) => j.status === 'running').length
  const completed = jobs.filter((j) => j.status === 'completed').length
  const failed = jobs.filter((j) => j.status === 'failed').length
  const active = jobs.filter((j) => ['running', 'queued', 'cancel_requested'].includes(j.status))

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Monitor textbook ingestion pipeline and worker health</p>
        </div>
        {health && (
          <div className="health-pill">
            <Activity size={16} />
            API {health.status} · v{health.version}
          </div>
        )}
      </header>

      {error && <ErrorBanner message={error} />}

      <div className="stat-grid">
        <StatCard title="Books uploaded" value={bookCount} accent="#6366f1" />
        <StatCard title="Active jobs" value={running} subtitle={`${jobs.length} total`} accent="#0ea5e9" />
        <StatCard title="Completed" value={completed} accent="#22c55e" />
        <StatCard title="Failed" value={failed} accent="#ef4444" />
      </div>

      {health && (
        <section className="card">
          <h2>Service</h2>
          <dl className="meta-grid">
            <div><dt>Workers</dt><dd>{health.workers}</dd></div>
            <div><dt>OpenSearch index</dt><dd>{health.opensearch_index}</dd></div>
            <div><dt>Service</dt><dd>{health.service}</dd></div>
          </dl>
        </section>
      )}

      <section className="card">
        <div className="card-header">
          <h2>Active & recent jobs</h2>
          <Link to="/jobs" className="btn btn-ghost">View all</Link>
        </div>
        {active.length === 0 ? (
          <p className="muted">No active jobs. Upload a book and start extraction.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Status</th>
                  <th>Stage</th>
                  <th>Progress</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {active.slice(0, 8).map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <Link to={`/jobs/${job.job_id}`} className="link-mono">
                        {job.job_id.slice(0, 12)}…
                      </Link>
                    </td>
                    <td><StatusBadge status={job.status} /></td>
                    <td>{job.stage ?? '—'}</td>
                    <td style={{ minWidth: 160 }}>
                      <ProgressBar value={job.progress} />
                    </td>
                    <td className="muted">{formatDate(job.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Quick links</h2>
        <div className="quick-links">
          <Link to="/books" className="quick-link">
            <BookOpen size={20} />
            Upload textbook
          </Link>
          <Link to="/jobs" className="quick-link">
            <CheckCircle2 size={20} />
            Manage jobs
          </Link>
          <Link to="/search" className="quick-link">
            <XCircle size={20} />
            Search indexed content
          </Link>
        </div>
      </section>
    </div>
  )
}
