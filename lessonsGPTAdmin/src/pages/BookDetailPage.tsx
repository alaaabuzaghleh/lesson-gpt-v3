import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Play, ArrowRight } from 'lucide-react'
import { api } from '../api/client'
import type { Book, ExtractionJob } from '../types/api'
import {
  ErrorBanner,
  JsonViewer,
  LoadingSpinner,
  StatusBadge,
  formatBytes,
  formatDate,
} from '../components/ui'
import { t } from '../i18n/ar'

export function BookDetailPage() {
  const { resourceId } = useParams<{ resourceId: string }>()
  const [book, setBook] = useState<Book | null>(null)
  const [jobs, setJobs] = useState<ExtractionJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [startPage, setStartPage] = useState(1)
  const [endPage, setEndPage] = useState('')
  const [indexToOs, setIndexToOs] = useState(true)

  const load = useCallback(async () => {
    if (!resourceId) return
    try {
      const [b, j] = await Promise.all([
        api.getBook(resourceId),
        api.listJobs({ book_resource_id: resourceId }),
      ])
      setBook(b)
      setJobs(j.items)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : t.bookDetail.loadError)
    } finally {
      setLoading(false)
    }
  }, [resourceId])

  useEffect(() => {
    load()
  }, [load])

  async function startExtraction() {
    if (!resourceId) return
    setStarting(true)
    setError(null)
    try {
      const job = await api.createJob(resourceId, {
        start_page: startPage,
        end_page: endPage ? parseInt(endPage, 10) : null,
        resume: true,
        index_to_opensearch: indexToOs,
        recreate_index: false,
      })
      window.location.href = `/jobs/${job.job_id}`
    } catch (e) {
      setError(e instanceof Error ? e.message : t.bookDetail.startError)
      setStarting(false)
    }
  }

  if (loading) return <LoadingSpinner />
  if (!book) return <ErrorBanner message={t.bookDetail.notFound} />

  return (
    <div className="page">
      <Link to="/books" className="back-link"><ArrowRight size={16} /> {t.bookDetail.back}</Link>

      <header className="page-header">
        <div>
          <h1>{book.filename}</h1>
          <p className="mono" dir="ltr">{book.resource_id}</p>
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <div className="two-col">
        <section className="card">
          <h2>{t.bookDetail.details}</h2>
          <dl className="meta-grid">
            <div><dt>{t.books.size}</dt><dd>{formatBytes(book.size_bytes)}</dd></div>
            <div><dt>SHA256</dt><dd className="mono truncate" dir="ltr">{book.sha256.slice(0, 24)}…</dd></div>
            <div><dt>{t.books.uploaded}</dt><dd>{formatDate(book.created_at)}</dd></div>
          </dl>
          <h3>{t.bookDetail.metadata}</h3>
          <JsonViewer data={book.metadata} />
        </section>

        <section className="card">
          <h2><Play size={18} /> {t.bookDetail.startExtraction}</h2>
          <div className="form-stack">
            <label>
              {t.bookDetail.startPage}
              <input type="number" min={1} value={startPage} onChange={(e) => setStartPage(+e.target.value)} />
            </label>
            <label>
              {t.bookDetail.endPage}
              <input
                type="number"
                min={1}
                value={endPage}
                onChange={(e) => setEndPage(e.target.value)}
                placeholder={t.bookDetail.allPages}
              />
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={indexToOs} onChange={(e) => setIndexToOs(e.target.checked)} />
              {t.bookDetail.indexOpenSearch}
            </label>
            <button className="btn btn-primary" onClick={startExtraction} disabled={starting}>
              {starting ? t.bookDetail.starting : t.bookDetail.startJob}
            </button>
          </div>
        </section>
      </div>

      <section className="card">
        <h2>{t.bookDetail.extractionJobs} ({jobs.length})</h2>
        {jobs.length === 0 ? (
          <p className="muted">{t.bookDetail.noJobs}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.bookDetail.jobId}</th>
                  <th>{t.jobs.status}</th>
                  <th>{t.jobs.progress}</th>
                  <th>{t.bookDetail.created}</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <Link to={`/jobs/${job.job_id}`} className="link-mono" dir="ltr">
                        {job.job_id.slice(0, 14)}…
                      </Link>
                    </td>
                    <td><StatusBadge status={job.status} /></td>
                    <td>{job.progress.toFixed(1)}%</td>
                    <td className="muted">{formatDate(job.created_at)}</td>
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
