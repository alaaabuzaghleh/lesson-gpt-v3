import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, BookOpen, CheckCircle2, Search as SearchIcon, Briefcase, XCircle, Loader2 } from 'lucide-react'
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
import { stageLabel, t } from '../i18n/ar'

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
        if (!cancelled) setError(e instanceof Error ? e.message : t.dashboard.loadError)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    const timer = setInterval(load, 8000)
    return () => {
      cancelled = true
      clearInterval(timer)
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
          <h1>{t.dashboard.title}</h1>
          <p>{t.dashboard.subtitle}</p>
        </div>
        {health && (
          <div className="health-pill">
            <Activity size={16} />
            {t.dashboard.apiOk} · v{health.version}
          </div>
        )}
      </header>

      {error && <ErrorBanner message={error} />}

      <div className="stat-grid">
        <StatCard
          title={t.dashboard.booksUploaded}
          value={bookCount}
          accent="#4f46e5"
          icon={<BookOpen size={20} />}
        />
        <StatCard
          title={t.dashboard.activeJobs}
          value={running}
          subtitle={`${jobs.length} ${t.dashboard.total}`}
          accent="#0284c7"
          icon={<Loader2 size={20} />}
        />
        <StatCard
          title={t.dashboard.completed}
          value={completed}
          accent="#059669"
          icon={<CheckCircle2 size={20} />}
        />
        <StatCard
          title={t.dashboard.failed}
          value={failed}
          accent="#dc2626"
          icon={<XCircle size={20} />}
        />
      </div>

      {health && (
        <section className="card">
          <h2>{t.dashboard.service}</h2>
          <dl className="meta-grid">
            <div><dt>{t.dashboard.workers}</dt><dd>{health.workers}</dd></div>
            <div><dt>{t.dashboard.opensearchIndex}</dt><dd dir="ltr">{health.opensearch_index}</dd></div>
            <div><dt>{t.dashboard.serviceName}</dt><dd dir="ltr">{health.service}</dd></div>
          </dl>
        </section>
      )}

      <section className="card">
        <div className="card-header">
          <h2>{t.dashboard.activeRecentJobs}</h2>
          <Link to="/jobs" className="btn btn-ghost">{t.common.viewAll}</Link>
        </div>
        {active.length === 0 ? (
          <p className="muted">{t.dashboard.noActiveJobs}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.dashboard.job}</th>
                  <th>{t.dashboard.status}</th>
                  <th>{t.dashboard.stage}</th>
                  <th>{t.dashboard.progress}</th>
                  <th>{t.dashboard.updated}</th>
                </tr>
              </thead>
              <tbody>
                {active.slice(0, 8).map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <Link to={`/jobs/${job.job_id}`} className="link-mono" dir="ltr">
                        {job.job_id.slice(0, 12)}…
                      </Link>
                    </td>
                    <td><StatusBadge status={job.status} /></td>
                    <td>{stageLabel(job.stage)}</td>
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
        <h2>{t.dashboard.quickLinks}</h2>
        <div className="quick-links">
          <Link to="/books" className="quick-link">
            <BookOpen size={20} />
            {t.dashboard.uploadTextbook}
          </Link>
          <Link to="/jobs" className="quick-link">
            <Briefcase size={20} />
            {t.dashboard.manageJobs}
          </Link>
          <Link to="/search" className="quick-link">
            <SearchIcon size={20} />
            {t.dashboard.searchContent}
          </Link>
        </div>
      </section>
    </div>
  )
}
