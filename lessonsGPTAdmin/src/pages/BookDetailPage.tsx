import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Play, ArrowLeft } from 'lucide-react'
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
      setError(e instanceof Error ? e.message : 'Failed to load book')
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
      setError(e instanceof Error ? e.message : 'Failed to start job')
      setStarting(false)
    }
  }

  if (loading) return <LoadingSpinner />
  if (!book) return <ErrorBanner message="Book not found" />

  return (
    <div className="page">
      <Link to="/books" className="back-link"><ArrowLeft size={16} /> Books</Link>

      <header className="page-header">
        <div>
          <h1>{book.filename}</h1>
          <p className="mono">{book.resource_id}</p>
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <div className="two-col">
        <section className="card">
          <h2>Book details</h2>
          <dl className="meta-grid">
            <div><dt>Size</dt><dd>{formatBytes(book.size_bytes)}</dd></div>
            <div><dt>SHA256</dt><dd className="mono truncate">{book.sha256.slice(0, 24)}…</dd></div>
            <div><dt>Uploaded</dt><dd>{formatDate(book.created_at)}</dd></div>
          </dl>
          <h3>Metadata</h3>
          <JsonViewer data={book.metadata} />
        </section>

        <section className="card">
          <h2><Play size={18} /> Start extraction</h2>
          <div className="form-stack">
            <label>
              Start page
              <input type="number" min={1} value={startPage} onChange={(e) => setStartPage(+e.target.value)} />
            </label>
            <label>
              End page (empty = all)
              <input type="number" min={1} value={endPage} onChange={(e) => setEndPage(e.target.value)} placeholder="All pages" />
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={indexToOs} onChange={(e) => setIndexToOs(e.target.checked)} />
              Index to OpenSearch when complete
            </label>
            <button className="btn btn-primary" onClick={startExtraction} disabled={starting}>
              {starting ? 'Starting…' : 'Start extraction job'}
            </button>
          </div>
        </section>
      </div>

      <section className="card">
        <h2>Extraction jobs ({jobs.length})</h2>
        {jobs.length === 0 ? (
          <p className="muted">No jobs yet for this book.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <Link to={`/jobs/${job.job_id}`} className="link-mono">
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
