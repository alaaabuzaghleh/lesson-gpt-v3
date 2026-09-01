import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Upload } from 'lucide-react'
import { api } from '../api/client'
import type { Book } from '../types/api'
import {
  EmptyState,
  ErrorBanner,
  LoadingSpinner,
  formatBytes,
  formatDate,
} from '../components/ui'

export function BooksPage() {
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [metaJson, setMetaJson] = useState(
    JSON.stringify(
      { country: 'Jordan', grade: 'Grade 8', subject: 'Science', language: 'ar' },
      null,
      2,
    ),
  )

  const load = useCallback(async () => {
    try {
      const res = await api.listBooks()
      setBooks(res.items)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load books')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!file) return
    let metadata: Record<string, unknown> = {}
    try {
      metadata = JSON.parse(metaJson)
      if (typeof metadata !== 'object' || metadata === null) throw new Error('Must be object')
    } catch {
      setError('Metadata must be valid JSON object')
      return
    }
    setUploading(true)
    setError(null)
    try {
      await api.uploadBook(file, metadata)
      setFile(null)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Books</h1>
          <p>Upload PDF textbooks and manage metadata</p>
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <section className="card upload-card">
        <h2><Upload size={20} /> Upload textbook</h2>
        <form onSubmit={handleUpload} className="upload-form">
          <div className="form-row">
            <label className="file-drop">
              <input
                type="file"
                accept="application/pdf,.pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              {file ? file.name : 'Choose PDF file…'}
            </label>
          </div>
          <div className="form-row">
            <label>Metadata (JSON)</label>
            <textarea
              value={metaJson}
              onChange={(e) => setMetaJson(e.target.value)}
              rows={6}
              spellCheck={false}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={!file || uploading}>
            {uploading ? 'Uploading…' : 'Upload book'}
          </button>
        </form>
      </section>

      <section className="card">
        <h2>Registered books ({books.length})</h2>
        {loading ? (
          <LoadingSpinner />
        ) : books.length === 0 ? (
          <EmptyState message="No books yet. Upload a PDF to get started." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Subject / Grade</th>
                  <th>Size</th>
                  <th>Uploaded</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {books.map((book) => (
                  <tr key={book.resource_id}>
                    <td>
                      <strong>{book.filename}</strong>
                      <div className="mono muted">{book.resource_id.slice(0, 16)}…</div>
                    </td>
                    <td>
                      {String(book.metadata.subject ?? '—')} · {String(book.metadata.grade ?? '—')}
                    </td>
                    <td>{formatBytes(book.size_bytes)}</td>
                    <td className="muted">{formatDate(book.created_at)}</td>
                    <td>
                      <Link to={`/books/${book.resource_id}`} className="btn btn-sm">
                        Open
                      </Link>
                    </td>
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
