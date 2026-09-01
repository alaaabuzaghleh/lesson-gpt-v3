import { useState } from 'react'
import { Search } from 'lucide-react'
import { api } from '../api/client'
import type { SearchHit } from '../types/api'
import { ErrorBanner, JsonViewer } from '../components/ui'

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
      setError(err instanceof Error ? err.message : 'Search failed — is OpenSearch running?')
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Search indexed content</h1>
          <p>Query OpenSearch for extracted textbook records</p>
        </div>
      </header>

      {error && <ErrorBanner message={error} />}

      <section className="card">
        <form onSubmit={handleSearch} className="search-form">
          <div className="search-input-wrap">
            <Search size={20} />
            <input
              type="text"
              placeholder="Search query (Arabic or English)…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              dir="auto"
            />
          </div>
          <div className="form-row-inline">
            <label>
              Book ID filter
              <input
                type="text"
                placeholder="Optional book_id"
                value={bookId}
                onChange={(e) => setBookId(e.target.value)}
              />
            </label>
            <label>
              Results
              <input type="number" min={1} max={100} value={size} onChange={(e) => setSize(+e.target.value)} />
            </label>
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
            {loading ? 'Searching…' : 'Search'}
          </button>
        </form>
      </section>

      {searched && (
        <section className="card">
          <h2>Results ({results.length})</h2>
          {results.length === 0 ? (
            <p className="muted">No matches found.</p>
          ) : (
            <div className="results-list">
              {results.map((hit, i) => (
                <details key={i} className="result-item" open={results.length <= 3}>
                  <summary>
                    {String(hit.title ?? hit.lesson_title ?? hit.page ?? `Result ${i + 1}`)}
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
