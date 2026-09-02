import { useCallback, useEffect, useMemo, useState, type DragEvent, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Search, Trash2, Upload } from 'lucide-react'
import { api } from '../api/client'
import type { Book, Country } from '../types/api'
import {
  CatalogPathPicker,
  catalogPathLabel,
  emptyCatalogPath,
  type CatalogPathSelection,
} from '../components/CatalogPathPicker'
import {
  EmptyState,
  ErrorBanner,
  LoadingSpinner,
  TextAreaField,
  formatBytes,
  formatDate,
} from '../components/ui'
import { t } from '../i18n/ar'

const LAST_PATH_KEY = 'lessons_gpt_last_catalog_path'

function bookMatchesPath(book: Book, path: CatalogPathSelection) {
  const p = book.catalog_path
  if (path.countryId && p?.country_id !== path.countryId) return false
  if (path.systemId && p?.education_system_id !== path.systemId) return false
  if (path.gradeId && p?.grade_id !== path.gradeId) return false
  if (path.subjectId && (p?.subject_id ?? book.subject_id) !== path.subjectId) return false
  return true
}

function bookSubject(book: Book) {
  return book.catalog_path?.subject_name
    || String(book.metadata.subject ?? t.common.dash)
}

function bookParents(book: Book) {
  const p = book.catalog_path
  if (!p) return ''
  return [p.country_name, p.education_system_name, p.grade_name].filter(Boolean).join(' › ')
}

function readSavedPath(): CatalogPathSelection {
  try {
    const raw = localStorage.getItem(LAST_PATH_KEY)
    if (!raw) return emptyCatalogPath()
    const parsed = JSON.parse(raw) as CatalogPathSelection
    if (!parsed?.countryId) return emptyCatalogPath()
    return {
      countryId: parsed.countryId ?? '',
      systemId: parsed.systemId ?? '',
      gradeId: parsed.gradeId ?? '',
      subjectId: parsed.subjectId ?? '',
    }
  } catch {
    return emptyCatalogPath()
  }
}

function pathStillValid(tree: Country[], path: CatalogPathSelection) {
  const country = tree.find((c) => c.id === path.countryId)
  if (!path.countryId) return true
  if (!country) return false
  if (!path.systemId) return true
  const system = (country.education_systems ?? []).find((s) => s.id === path.systemId)
  if (!system) return false
  if (!path.gradeId) return true
  const grade = (system.grades ?? []).find((g) => g.id === path.gradeId)
  if (!grade) return false
  if (!path.subjectId) return true
  return (grade.subjects ?? []).some((s) => s.id === path.subjectId)
}

export function BooksPage() {
  const [books, setBooks] = useState<Book[]>([])
  const [tree, setTree] = useState<Country[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [uploadPath, setUploadPath] = useState<CatalogPathSelection>(readSavedPath)
  const [filterPath, setFilterPath] = useState<CatalogPathSelection>(emptyCatalogPath)
  const [nameQuery, setNameQuery] = useState('')
  const [metaJson, setMetaJson] = useState(JSON.stringify({ language: 'ar' }, null, 2))
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deletingAll, setDeletingAll] = useState(false)

  const hasCatalog = tree.some((c) => (c.education_systems ?? []).some((s) =>
    (s.grades ?? []).some((g) => (g.subjects ?? []).length > 0),
  ))

  const filteredBooks = useMemo(() => {
    const q = nameQuery.trim().toLowerCase()
    return books.filter((b) => {
      if (!bookMatchesPath(b, filterPath)) return false
      if (q && !b.filename.toLowerCase().includes(q) && !bookSubject(b).toLowerCase().includes(q)) return false
      return true
    })
  }, [books, filterPath, nameQuery])

  const load = useCallback(async () => {
    try {
      const [booksRes, treeRes] = await Promise.all([api.listBooks(), api.catalogTree()])
      setBooks(booksRes.items)
      setTree(treeRes.items)
      setUploadPath((prev) => (pathStillValid(treeRes.items, prev) ? prev : emptyCatalogPath()))
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

  function setPdf(next: File | null) {
    if (!next) {
      setFile(null)
      return
    }
    const ok = next.type === 'application/pdf' || next.name.toLowerCase().endsWith('.pdf')
    if (!ok) {
      setError(t.books.pdfOnly)
      return
    }
    setError(null)
    setFile(next)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragOver(false)
    setPdf(e.dataTransfer.files[0] ?? null)
  }

  async function handleUpload(e: FormEvent) {
    e.preventDefault()
    if (!file || !uploadPath.subjectId) {
      setError(t.books.selectSubjectRequired)
      return
    }
    let metadata: Record<string, unknown> = { language: 'ar' }
    if (showAdvanced) {
      try {
        metadata = JSON.parse(metaJson)
        if (typeof metadata !== 'object' || metadata === null) throw new Error('invalid')
      } catch {
        setError(t.books.metadataInvalid)
        return
      }
    }
    setUploading(true)
    setError(null)
    try {
      await api.uploadBook(file, uploadPath.subjectId, metadata)
      localStorage.setItem(LAST_PATH_KEY, JSON.stringify(uploadPath))
      setFile(null)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.books.uploadFailed)
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(book: Book) {
    if (!window.confirm(t.books.confirmDelete.replace('{name}', book.filename))) return
    setDeletingId(book.resource_id)
    setError(null)
    try {
      await api.deleteBook(book.resource_id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.books.deleteFailed)
    } finally {
      setDeletingId(null)
    }
  }

  async function handleDeleteAll() {
    if (filteredBooks.length === 0) return
    if (!window.confirm(t.books.confirmDeleteAll.replace('{count}', String(filteredBooks.length)))) return
    setDeletingAll(true)
    setError(null)
    try {
      for (const book of filteredBooks) {
        await api.deleteBook(book.resource_id)
      }
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.books.deleteFailed)
      await load()
    } finally {
      setDeletingAll(false)
    }
  }

  const selectedLabel = catalogPathLabel(tree, uploadPath)
  const canUpload = Boolean(file && uploadPath.subjectId && !uploading)

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
        <p className="muted upload-hint">{t.books.uploadHint}</p>
        {hasCatalog ? (
          <form onSubmit={handleUpload} className="upload-form">
            <div className="upload-grid">
              <div className="upload-where">
                <h3>{t.books.whereToSave}</h3>
                <CatalogPathPicker
                  tree={tree}
                  value={uploadPath}
                  onChange={setUploadPath}
                  requireSubject
                  allowEmpty={false}
                  variant="guided"
                  idPrefix="upload-path"
                />
                {uploadPath.subjectId && (
                  <p className="upload-target">{t.books.willSaveTo}: <strong>{selectedLabel}</strong></p>
                )}
              </div>
              <div className="upload-file">
                <h3>{t.books.attachPdf}</h3>
                <label
                  className={`file-drop${dragOver ? ' is-dragover' : ''}${file ? ' has-file' : ''}`}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={onDrop}
                >
                  <input
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={(e) => setPdf(e.target.files?.[0] ?? null)}
                  />
                  <FileText size={28} />
                  <span>{file ? file.name : t.books.dropPdf}</span>
                  {file && <span className="muted">{formatBytes(file.size)}</span>}
                </label>
                <button type="submit" className="btn btn-primary upload-submit" disabled={!canUpload}>
                  {uploading ? t.books.uploading : t.books.uploadBook}
                </button>
              </div>
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? t.books.hideAdvanced : t.books.advanced}
            </button>
            {showAdvanced && (
              <TextAreaField
                label={t.books.metadata}
                value={metaJson}
                onChange={(e) => setMetaJson(e.target.value)}
                rows={4}
                spellCheck={false}
                dir="ltr"
              />
            )}
          </form>
        ) : loading ? (
          <LoadingSpinner />
        ) : (
          <p className="muted">
            {t.books.noSubjects} <Link to="/catalog/subjects">{t.nav.catalog}</Link>
          </p>
        )}
      </section>

      <section className="card books-list-card">
        <div className="books-list-head">
          <h2>
            {`${t.books.registered} (${
              filteredBooks.length !== books.length
                ? `${filteredBooks.length} / ${books.length}`
                : filteredBooks.length
            })`}
          </h2>
          {filteredBooks.length > 0 && (
            <button
              type="button"
              className="btn btn-sm btn-danger"
              onClick={() => void handleDeleteAll()}
              disabled={deletingAll || deletingId !== null}
            >
              <Trash2 size={14} /> {deletingAll ? t.books.deleting : t.books.deleteAll}
            </button>
          )}
        </div>
        <div className="books-toolbar">
          <div className="catalog-picker-search books-name-search">
            <Search size={16} aria-hidden />
            <input
              type="search"
              value={nameQuery}
              onChange={(e) => setNameQuery(e.target.value)}
              placeholder={t.books.searchBooks}
              aria-label={t.books.searchBooks}
            />
          </div>
          {tree.length > 0 && (
            <CatalogPathPicker
              tree={tree}
              value={filterPath}
              onChange={setFilterPath}
              allowEmpty
              variant="compact"
              idPrefix="books-filter"
            />
          )}
        </div>
        {loading ? (
          <LoadingSpinner />
        ) : books.length === 0 ? (
          <EmptyState message={t.books.noBooks} />
        ) : filteredBooks.length === 0 ? (
          <EmptyState message={t.books.noSubjectMatch} />
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
                {filteredBooks.map((book) => (
                  <tr key={book.resource_id}>
                    <td>
                      <strong>{book.filename}</strong>
                    </td>
                    <td>
                      <div className="book-path">
                        <strong>{bookSubject(book)}</strong>
                        {bookParents(book) && <span className="muted">{bookParents(book)}</span>}
                      </div>
                    </td>
                    <td>{formatBytes(book.size_bytes)}</td>
                    <td className="muted">{formatDate(book.created_at)}</td>
                    <td>
                      <div className="table-actions">
                        <Link to={`/books/${book.resource_id}`} className="btn btn-sm">
                          {t.common.open}
                        </Link>
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          title={t.books.delete}
                          onClick={() => void handleDelete(book)}
                          disabled={deletingAll || deletingId === book.resource_id}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
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
