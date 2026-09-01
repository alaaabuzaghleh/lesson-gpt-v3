import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Ban, RotateCcw } from 'lucide-react'
import { api, subscribeJobEvents } from '../api/client'
import type { ExtractionJob, JobEvent } from '../types/api'
import {
  ErrorBanner,
  JsonViewer,
  LoadingSpinner,
  ProgressBar,
  StatusBadge,
  formatDate,
} from '../components/ui'

type Tab = 'overview' | 'events' | 'quality' | 'manifest' | 'errors'

export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const [job, setJob] = useState<ExtractionJob | null>(null)
  const [events, setEvents] = useState<JobEvent[]>([])
  const [tab, setTab] = useState<Tab>('overview')
  const [artifact, setArtifact] = useState<unknown>(null)
  const [errors, setErrors] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const eventsEndRef = useRef<HTMLDivElement>(null)

  const loadJob = useCallback(async () => {
    if (!jobId) return
    try {
      const j = await api.getJob(jobId)
      setJob(j)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load job')
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    loadJob()
    const t = setInterval(loadJob, 4000)
    return () => clearInterval(t)
  }, [loadJob])

  useEffect(() => {
    if (!jobId) return
    api.listEvents(jobId).then((r) => setEvents(r.items)).catch(() => {})
    const unsub = subscribeJobEvents(jobId, (ev) => {
      setEvents((prev) => {
        if (prev.some((e) => e.id === ev.id)) return prev
        return [...prev, ev]
      })
      loadJob()
    })
    return unsub
  }, [jobId, loadJob])

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  useEffect(() => {
    if (!jobId || tab === 'overview' || tab === 'events') return
    setArtifact(null)
    async function loadArtifact() {
      try {
        if (tab === 'quality') setArtifact(await api.qualityReport(jobId!))
        else if (tab === 'manifest') setArtifact(await api.manifest(jobId!))
        else if (tab === 'errors') {
          const r = await api.errors(jobId!)
          setErrors(r.items)
        }
      } catch (e) {
        setArtifact({ error: e instanceof Error ? e.message : 'Not available yet' })
      }
    }
    loadArtifact()
  }, [jobId, tab])

  async function handleCancel() {
    if (!jobId) return
    setActionLoading(true)
    try {
      await api.cancelJob(jobId)
      await loadJob()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Cancel failed')
    } finally {
      setActionLoading(false)
    }
  }

  async function handleRetry() {
    if (!jobId) return
    setActionLoading(true)
    try {
      const newJob = await api.retryJob(jobId)
      window.location.href = `/jobs/${newJob.job_id}`
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Retry failed')
      setActionLoading(false)
    }
  }

  if (loading) return <LoadingSpinner />
  if (!job) return <ErrorBanner message="Job not found" />

  const canCancel = !['completed', 'failed', 'cancelled'].includes(job.status)
  const canRetry = ['failed', 'cancelled'].includes(job.status)

  return (
    <div className="page">
      <Link to="/jobs" className="back-link"><ArrowLeft size={16} /> Jobs</Link>

      <header className="page-header">
        <div>
          <h1>Job {job.job_id.slice(0, 16)}…</h1>
          <p>{job.message ?? 'Extraction pipeline'}</p>
        </div>
        <div className="header-actions">
          <StatusBadge status={job.status} />
          {canCancel && (
            <button className="btn btn-danger" onClick={handleCancel} disabled={actionLoading}>
              <Ban size={16} /> Cancel
            </button>
          )}
          {canRetry && (
            <button className="btn btn-primary" onClick={handleRetry} disabled={actionLoading}>
              <RotateCcw size={16} /> Retry
            </button>
          )}
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <section className="card">
        <ProgressBar
          value={job.progress}
          label={job.stage ? `Stage: ${job.stage.replace(/_/g, ' ')}` : undefined}
        />
        <dl className="meta-grid meta-grid-wide">
          <div><dt>Book</dt><dd><Link to={`/books/${job.book_resource_id}`}>{job.book_resource_id.slice(0, 16)}…</Link></dd></div>
          <div><dt>Page</dt><dd>{job.current_page ?? '—'} / {job.total_pages ?? '—'}</dd></div>
          <div><dt>Records</dt><dd>{job.extracted_records ?? '—'}</dd></div>
          <div><dt>Visual assets</dt><dd>{job.visual_assets ?? '—'}</dd></div>
          <div><dt>Indexed</dt><dd>{job.indexed_records ?? '—'}</dd></div>
          <div><dt>Started</dt><dd>{formatDate(job.started_at)}</dd></div>
          <div><dt>Finished</dt><dd>{formatDate(job.finished_at)}</dd></div>
          {job.error && <div className="span-full"><dt>Error</dt><dd className="text-danger">{job.error}</dd></div>}
        </dl>
      </section>

      <div className="tabs">
        {(['overview', 'events', 'quality', 'manifest', 'errors'] as Tab[]).map((t) => (
          <button key={t} type="button" className={`tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>

      <section className="card">
        {tab === 'overview' && <JsonViewer data={job} />}
        {tab === 'events' && (
          <div className="event-log">
            {events.length === 0 ? (
              <p className="muted">Waiting for events…</p>
            ) : (
              events.map((ev) => (
                <div key={ev.id} className="event-row">
                  <span className="event-type">{ev.event_type}</span>
                  <span className="muted">{formatDate(ev.created_at)}</span>
                  <pre>{JSON.stringify(ev.payload, null, 2)}</pre>
                </div>
              ))
            )}
            <div ref={eventsEndRef} />
          </div>
        )}
        {tab === 'quality' && (artifact ? <JsonViewer data={artifact} /> : <LoadingSpinner />)}
        {tab === 'manifest' && (artifact ? <JsonViewer data={artifact} /> : <LoadingSpinner />)}
        {tab === 'errors' && (
          errors.length === 0 ? (
            <p className="muted">No errors recorded.</p>
          ) : (
            <JsonViewer data={errors} />
          )
        )}
      </section>
    </div>
  )
}
