import { useState } from 'react'
import { Search } from 'lucide-react'
import { api } from '../api/client'
import type { SearchHit } from '../types/api'
import { ErrorBanner, JsonViewer } from '../components/ui'
import { t } from '../i18n/ar'

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [bookId, setBookId] = useState('')
  const [size, setSize] = useState(15)
  const [results, setResults] = useState<SearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setSearched(true)
    try {
      const filters: Record<string, unknown> = {}
      if (bookId.trim()) filters.book_id = bookId.trim()
      const res = await api.search({ query: query.trim(), filters, size })
      setResults(res.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : t.search.failed)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{t.search.title}</h1>
          <p>{t.search.subtitle}</p>
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <section className="card">
        <form onSubmit={handleSearch} className="search-form">
          <div className="search-input-wrap">
            <Search size={20} />
            <input
              type="text"
              placeholder={t.search.placeholder}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              dir="auto"
            />
          </div>
          <div className="form-row-inline">
            <label>
              {t.search.bookIdFilter}
              <input
                type="text"
                placeholder={t.search.bookIdPlaceholder}
                value={bookId}
                onChange={(e) => setBookId(e.target.value)}
                dir="ltr"
              />
            </label>
            <label>
              {t.search.resultsCount}
              <input type="number" min={1} max={100} value={size} onChange={(e) => setSize(+e.target.value)} />
            </label>
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
            {loading ? t.search.searching : t.search.search}
          </button>
        </form>
      </section>

      {searched && (
        <section className="card">
          <h2>{t.search.results} ({results.length})</h2>
          {results.length === 0 ? (
            <p className="muted">{t.search.noMatches}</p>
          ) : (
            <div className="results-list">
              {results.map((hit, i) => (
                <details key={i} className="result-item" open={results.length <= 3}>
                  <summary>
                    {String(hit.title ?? hit.lesson_title ?? hit.page ?? `${t.common.result} ${i + 1}`)}
                  </summary>
                  <JsonViewer data={hit} />
                </details>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
