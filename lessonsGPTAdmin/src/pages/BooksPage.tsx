import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Upload } from 'lucide-react'
import { api, flattenSubjects } from '../api/client'
import type { Book, SubjectOption } from '../types/api'
import {
  EmptyState,
  ErrorBanner,
  LoadingSpinner,
  formatBytes,
  formatDate,
} from '../components/ui'
import { t } from '../i18n/ar'

export function BooksPage() {
  const [books, setBooks] = useState<Book[]>([])
  const [subjects, setSubjects] = useState<SubjectOption[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [subjectId, setSubjectId] = useState('')
  const [metaJson, setMetaJson] = useState(JSON.stringify({ language: 'ar' }, null, 2))

  const load = useCallback(async () => {
    try {
      const [booksRes, treeRes] = await Promise.all([api.listBooks(), api.catalogTree()])
      setBooks(booksRes.items)
      setSubjects(flattenSubjects(treeRes.items))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : t.books.loadError)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault()
    if (!file || !subjectId) {
      setError(t.books.selectSubjectRequired)
      return
    }
    let metadata: Record<string, unknown> = {}
    try {
      metadata = JSON.parse(metaJson)
      if (typeof metadata !== 'object' || metadata === null) throw new Error('invalid')
    } catch {
      setError(t.books.metadataInvalid)
      return
    }
    setUploading(true)
    setError(null)
    try {
      await api.uploadBook(file, subjectId, metadata)
      setFile(null)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.books.uploadFailed)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{t.books.title}</h1>
          <p>{t.books.subtitle}</p>
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <section className="card upload-card">
        <h2><Upload size={20} /> {t.books.uploadTitle}</h2>
        {subjects.length === 0 ? (
          <p className="muted">{t.books.noSubjects} <Link to="/catalog">{t.nav.catalog}</Link></p>
        ) : (
          <form onSubmit={handleUpload} className="upload-form">
            <div className="form-row">
              <label>{t.catalog.selectSubject}</label>
              <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} required>
                <option value="">{t.catalog.selectSubject}</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <label className="file-drop">
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                {file ? file.name : t.books.choosePdf}
              </label>
            </div>
            <div className="form-row">
              <label>{t.books.metadata}</label>
              <textarea
                value={metaJson}
                onChange={(e) => setMetaJson(e.target.value)}
                rows={4}
                spellCheck={false}
                dir="ltr"
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={!file || !subjectId || uploading}>
              {uploading ? t.books.uploading : t.books.uploadBook}
            </button>
          </form>
        )}
      </section>

      <section className="card">
        <h2>{t.books.registered} ({books.length})</h2>
        {loading ? (
          <LoadingSpinner />
        ) : books.length === 0 ? (
          <EmptyState message={t.books.noBooks} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.books.filename}</th>
                  <th>{t.books.subjectGrade}</th>
                  <th>{t.books.size}</th>
                  <th>{t.books.uploaded}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {books.map((book) => (
                  <tr key={book.resource_id}>
                    <td>
                      <strong>{book.filename}</strong>
                      <div className="mono muted" dir="ltr">{book.resource_id.slice(0, 16)}…</div>
                    </td>
                    <td>
                      {book.catalog_path
                        ? `${book.catalog_path.country_name ?? ''} › ${book.catalog_path.grade_name ?? ''} › ${book.catalog_path.subject_name ?? ''}`
                        : String(book.metadata.subject ?? t.common.dash)}
                    </td>
                    <td>{formatBytes(book.size_bytes)}</td>
                    <td className="muted">{formatDate(book.created_at)}</td>
                    <td>
                      <Link to={`/books/${book.resource_id}`} className="btn btn-sm">
                        {t.common.open}
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
