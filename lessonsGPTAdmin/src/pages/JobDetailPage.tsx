import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowRight, Ban, RotateCcw } from 'lucide-react'
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
import { stageLabel, t } from '../i18n/ar'

type Tab = 'overview' | 'events' | 'quality' | 'manifest' | 'errors'

const TAB_KEYS: Tab[] = ['overview', 'events', 'quality', 'manifest', 'errors']

export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const [job, setJob] = useState<ExtractionJob | null>(null)
  const [events, setEvents] = useState<JobEvent[]>([])
  const [tab, setTab] = useState<Tab>('overview')
  const [artifact, setArtifact] = useState<unknown>(null)
  const [errors, setErrors] = useState<Record<string, unknown>[] | null>(null)
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
      setError(e instanceof Error ? e.message : t.jobDetail.loadError)
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    loadJob()
    const timer = setInterval(loadJob, 4000)
    return () => clearInterval(timer)
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
    setErrors(null)
    async function loadArtifact() {
      try {
        if (tab === 'quality') setArtifact(await api.qualityReport(jobId!))
        else if (tab === 'manifest') setArtifact(await api.manifest(jobId!))
        else if (tab === 'errors') {
          const r = await api.errors(jobId!)
          setErrors(r.items)
        }
      } catch (e) {
        setArtifact({ error: e instanceof Error ? e.message : t.jobDetail.notAvailable })
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
      setError(e instanceof Error ? e.message : t.jobDetail.cancelFailed)
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
      setError(e instanceof Error ? e.message : t.jobDetail.retryFailed)
      setActionLoading(false)
    }
  }

  if (loading) return <LoadingSpinner />
  if (!job) return <ErrorBanner message={t.jobDetail.notFound} />

  const canCancel = !['completed', 'failed', 'cancelled'].includes(job.status)
  const canRetry = ['failed', 'cancelled'].includes(job.status)

  return (
    <div className="page">
      <Link to="/jobs" className="back-link"><ArrowRight size={16} /> {t.jobDetail.back}</Link>

      <header className="page-header">
        <div>
          <h1>{t.jobDetail.title} <span dir="ltr">{job.job_id.slice(0, 16)}…</span></h1>
          <p>{job.message ?? t.jobDetail.pipeline}</p>
        </div>
        <div className="header-actions">
          <StatusBadge status={job.status} />
          {canCancel && (
            <button className="btn btn-danger" onClick={handleCancel} disabled={actionLoading}>
              <Ban size={16} /> {t.jobDetail.cancel}
            </button>
          )}
          {canRetry && (
            <button className="btn btn-primary" onClick={handleRetry} disabled={actionLoading}>
              <RotateCcw size={16} /> {t.jobDetail.retry}
            </button>
          )}
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      {(job.status === 'failed' || job.error) && (
        <section className="failure-banner" role="alert">
          <h2>{t.jobDetail.failureTitle}</h2>
          <p dir="auto">{job.error || job.message || t.jobDetail.loadError}</p>
          {job.traceback && (
            <details>
              <summary>{t.jobDetail.traceback}</summary>
              <pre className="failure-trace" dir="ltr">{job.traceback}</pre>
            </details>
          )}
        </section>
      )}

      <section className="card">
        <ProgressBar
          value={job.progress}
          label={job.stage ? `${t.jobDetail.stageLabel}: ${stageLabel(job.stage)}` : undefined}
        />
        <dl className="meta-grid meta-grid-wide">
          <div><dt>{t.jobDetail.book}</dt><dd><Link to={`/books/${job.book_resource_id}`} dir="ltr">{job.book_resource_id.slice(0, 16)}…</Link></dd></div>
          <div><dt>{t.jobDetail.page}</dt><dd>{job.current_page ?? t.common.dash} / {job.total_pages ?? t.common.dash}</dd></div>
          <div><dt>{t.jobDetail.records}</dt><dd>{job.extracted_records ?? t.common.dash}</dd></div>
          <div><dt>{t.jobDetail.visualAssets}</dt><dd>{job.visual_assets ?? t.common.dash}</dd></div>
          <div><dt>{t.jobDetail.indexed}</dt><dd>{job.indexed_records ?? t.common.dash}</dd></div>
          <div><dt>{t.jobDetail.started}</dt><dd>{formatDate(job.started_at)}</dd></div>
          <div><dt>{t.jobDetail.finished}</dt><dd>{formatDate(job.finished_at)}</dd></div>
          {job.error && <div className="span-full"><dt>{t.jobDetail.error}</dt><dd className="text-danger">{job.error}</dd></div>}
        </dl>
      </section>

      <div className="tabs">
        {TAB_KEYS.map((key) => (
          <button key={key} type="button" className={`tab${tab === key ? ' active' : ''}`} onClick={() => setTab(key)}>
            {t.tabs[key]}
          </button>
        ))}
      </div>

      <section className="card">
        {tab === 'overview' && <JsonViewer data={job} />}
        {tab === 'events' && (
          <div className="event-log">
            {events.length === 0 ? (
              <p className="muted">{t.jobDetail.waitingEvents}</p>
            ) : (
              events.map((ev) => (
                <div key={ev.id} className={`event-row${ev.event_type === 'failed' ? ' is-failed' : ''}`}>
                  <span className="event-type">{ev.event_type}</span>
                  <span className="muted">{formatDate(ev.created_at)}</span>
                  {ev.message && <p className="event-message">{ev.message}</p>}
                  {ev.payload != null && (
                    <pre dir="ltr">{JSON.stringify(ev.payload, null, 2)}</pre>
                  )}
                </div>
              ))
            )}
            <div ref={eventsEndRef} />
          </div>
        )}
        {tab === 'quality' && (artifact ? <JsonViewer data={artifact} /> : <LoadingSpinner />)}
        {tab === 'manifest' && (artifact ? <JsonViewer data={artifact} /> : <LoadingSpinner />)}
        {tab === 'errors' && (
          errors == null ? (
            <LoadingSpinner />
          ) : errors.length === 0 ? (
            <p className="muted">{t.jobDetail.noErrors}</p>
          ) : (
            <JsonViewer data={errors} />
          )
        )}
      </section>
    </div>
  )
}
