import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Country } from '../types/api'
import { ErrorBanner, LoadingSpinner } from '../components/ui'
import { t } from '../i18n/ar'

export function CatalogPage() {
  const [tree, setTree] = useState<Country[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [countryName, setCountryName] = useState('')
  const [systemName, setSystemName] = useState('')
  const [gradeName, setGradeName] = useState('')
  const [subjectName, setSubjectName] = useState('')
  const [selectedCountry, setSelectedCountry] = useState('')
  const [selectedSystem, setSelectedSystem] = useState('')
  const [selectedGrade, setSelectedGrade] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await api.catalogTree()
      setTree(res.items)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : t.catalog.loadError)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function addCountry() {
    if (!countryName.trim()) return
    await api.createCountry({ name: countryName.trim(), name_ar: countryName.trim() })
    setCountryName('')
    await load()
  }

  async function addSystem() {
    if (!selectedCountry || !systemName.trim()) return
    await api.createEducationSystem({ country_id: selectedCountry, name: systemName.trim(), name_ar: systemName.trim() })
    setSystemName('')
    await load()
  }

  async function addGrade() {
    if (!selectedSystem || !gradeName.trim()) return
    await api.createGrade({ education_system_id: selectedSystem, name: gradeName.trim(), name_ar: gradeName.trim() })
    setGradeName('')
    await load()
  }

  async function addSubject() {
    if (!selectedGrade || !subjectName.trim()) return
    await api.createSubject({ grade_id: selectedGrade, name: subjectName.trim(), name_ar: subjectName.trim() })
    setSubjectName('')
    await load()
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{t.catalog.title}</h1>
          <p>{t.catalog.subtitle}</p>
        </div>
      </header>
      {error && <ErrorBanner message={error} />}

      <div className="two-col">
        <section className="card form-stack">
          <h2>{t.catalog.addCountry}</h2>
          <input value={countryName} onChange={(e) => setCountryName(e.target.value)} placeholder={t.catalog.countryName} />
          <button className="btn btn-primary" onClick={addCountry}>{t.catalog.add}</button>

          <h2>{t.catalog.addSystem}</h2>
          <select value={selectedCountry} onChange={(e) => setSelectedCountry(e.target.value)}>
            <option value="">{t.catalog.selectCountry}</option>
            {tree.map((c) => <option key={c.id} value={c.id}>{c.name_ar ?? c.name}</option>)}
          </select>
          <input value={systemName} onChange={(e) => setSystemName(e.target.value)} placeholder={t.catalog.systemName} />
          <button className="btn btn-primary" onClick={addSystem}>{t.catalog.add}</button>

          <h2>{t.catalog.addGrade}</h2>
          <select value={selectedSystem} onChange={(e) => setSelectedSystem(e.target.value)}>
            <option value="">{t.catalog.selectSystem}</option>
            {tree.flatMap((c) => (c.education_systems ?? []).map((s) => (
              <option key={s.id} value={s.id}>{c.name} › {s.name_ar ?? s.name}</option>
            )))}
          </select>
          <input value={gradeName} onChange={(e) => setGradeName(e.target.value)} placeholder={t.catalog.gradeName} />
          <button className="btn btn-primary" onClick={addGrade}>{t.catalog.add}</button>

          <h2>{t.catalog.addSubject}</h2>
          <select value={selectedGrade} onChange={(e) => setSelectedGrade(e.target.value)}>
            <option value="">{t.catalog.selectGrade}</option>
            {tree.flatMap((c) => (c.education_systems ?? []).flatMap((s) => (s.grades ?? []).map((g) => (
              <option key={g.id} value={g.id}>{g.name_ar ?? g.name} ({s.name})</option>
            ))))}
          </select>
          <input value={subjectName} onChange={(e) => setSubjectName(e.target.value)} placeholder={t.catalog.subjectName} />
          <button className="btn btn-primary" onClick={addSubject}>{t.catalog.add}</button>
        </section>

        <section className="card">
          <h2>{t.catalog.treeTitle}</h2>
          {tree.length === 0 ? (
            <p className="muted">{t.catalog.empty}</p>
          ) : (
            <div className="catalog-tree">
              {tree.map((c) => (
                <details key={c.id} open>
                  <summary>{c.name_ar ?? c.name}</summary>
                  {(c.education_systems ?? []).map((s) => (
                    <details key={s.id}>
                      <summary>{s.name_ar ?? s.name}</summary>
                      {(s.grades ?? []).map((g) => (
                        <details key={g.id}>
                          <summary>{g.name_ar ?? g.name}</summary>
                          <ul>
                            {(g.subjects ?? []).map((sub) => (
                              <li key={sub.id}>{sub.name_ar ?? sub.name}</li>
                            ))}
                          </ul>
                        </details>
                      ))}
                    </details>
                  ))}
                </details>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
