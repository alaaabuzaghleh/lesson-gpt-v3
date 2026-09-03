import { useCallback, useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import type { CatalogEntityType, Country, EducationSystem, Grade, Subject } from '../types/api'
import { CatalogAddForm, CatalogItemEditor } from './CatalogSeoEditor'
import { catalogFormToPayload, catalogSeoOf, type CatalogFormData } from './catalogForm'
import {
  buildCatalogLookups,
  labelPair,
  subjectParentLabel,
  gradeLabel,
  type CatalogLookups,
} from './catalogLookups'
import { EmptyState, ErrorBanner, LoadingSpinner, SelectField } from './ui'
import { t } from '../i18n/ar'

export type CatalogSection = 'countries' | 'systems' | 'grades' | 'subjects'

type CatalogRow = Country | EducationSystem | Grade | Subject

const SECTION_META: Record<CatalogSection, { type: CatalogEntityType; title: string; subtitle: string }> = {
  countries: { type: 'country', title: t.catalog.navCountries, subtitle: t.catalog.countriesPageSubtitle },
  systems: { type: 'system', title: t.catalog.navSystems, subtitle: t.catalog.systemsPageSubtitle },
  grades: { type: 'grade', title: t.catalog.navGrades, subtitle: t.catalog.gradesPageSubtitle },
  subjects: { type: 'subject', title: t.catalog.navSubjects, subtitle: t.catalog.subjectsPageSubtitle },
}

export function CatalogSectionPage({ section }: { section: CatalogSection }) {
  const meta = SECTION_META[section]
  const [lookups, setLookups] = useState<CatalogLookups | null>(null)
  const [items, setItems] = useState<CatalogRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [editItem, setEditItem] = useState<CatalogRow | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const [filterCountry, setFilterCountry] = useState('')
  const [filterSystem, setFilterSystem] = useState('')
  const [filterGrade, setFilterGrade] = useState('')
  const [addCountry, setAddCountry] = useState('')
  const [addSystem, setAddSystem] = useState('')
  const [addGrade, setAddGrade] = useState('')

  const loadTree = useCallback(async () => {
    const res = await api.catalogTree()
    setLookups(buildCatalogLookups(res.items))
  }, [])

  const loadItems = useCallback(async () => {
    setLoading(true)
    try {
      let rows: CatalogRow[] = []
      switch (section) {
        case 'countries':
          rows = (await api.listCountries()).items
          break
        case 'systems':
          rows = (await api.listEducationSystems(filterCountry || undefined)).items
          break
        case 'grades':
          rows = (await api.listGrades(filterSystem || undefined)).items
          break
        case 'subjects':
          rows = (await api.listSubjects(filterGrade || undefined)).items
          break
      }
      setItems(rows)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : t.catalog.loadError)
    } finally {
      setLoading(false)
    }
  }, [section, filterCountry, filterSystem, filterGrade])

  useEffect(() => {
    void loadTree()
  }, [loadTree])

  useEffect(() => {
    void loadItems()
  }, [loadItems])

  const filteredSystems = useMemo(() => {
    if (!lookups) return []
    if (!filterCountry && section !== 'systems') return lookups.systems
    const cid = filterCountry || addCountry
    return cid ? lookups.systems.filter((s) => s.country_id === cid) : lookups.systems
  }, [lookups, filterCountry, addCountry, section])

  const filteredGrades = useMemo(() => {
    if (!lookups) return []
    const sid = filterSystem || addSystem
    return sid ? lookups.grades.filter((g) => g.education_system_id === sid) : lookups.grades
  }, [lookups, filterSystem, addSystem])

  const refresh = async () => {
    await loadTree()
    await loadItems()
  }

  const handleCreate = async (form: CatalogFormData) => {
    const payload = catalogFormToPayload(form, meta.type)
    switch (section) {
      case 'countries':
        await api.createCountryFull(payload)
        break
      case 'systems':
        if (!addCountry) throw new Error(t.catalog.selectCountry)
        await api.createEducationSystemFull({ ...payload, country_id: addCountry })
        break
      case 'grades':
        if (!addSystem) throw new Error(t.catalog.selectSystem)
        await api.createGradeFull({ ...payload, education_system_id: addSystem })
        break
      case 'subjects':
        if (!addGrade) throw new Error(t.catalog.selectGrade)
        await api.createSubjectFull({ ...payload, grade_id: addGrade })
        break
    }
    setShowAdd(false)
    await refresh()
  }

  const handleDelete = async (item: CatalogRow) => {
    const name = labelPair(item.name, item.name_ar)
    const msg =
      section === 'subjects'
        ? t.catalog.confirmDeleteSubject.replace('{name}', name)
        : t.catalog.confirmDelete.replace('{name}', name)
    if (!window.confirm(msg)) return

    setDeletingId(item.id)
    setError(null)
    try {
      switch (section) {
        case 'countries':
          await api.deleteCountry(item.id)
          break
        case 'systems':
          await api.deleteEducationSystem(item.id)
          break
        case 'grades':
          await api.deleteGrade(item.id)
          break
        case 'subjects': {
          const res = await api.deleteSubject(item.id)
          if (res.linked_books > 0) {
            setError(t.catalog.deletedWithBooks.replace('{count}', String(res.linked_books)))
          }
          break
        }
      }
      if (editItem?.id === item.id) setEditItem(null)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : t.catalog.deleteFailed)
    } finally {
      setDeletingId(null)
    }
  }

  if (loading && !lookups) return <LoadingSpinner />

  return (
    <div className="catalog-section-page">
      <div className="catalog-section-head">
        <div>
          <h2>{meta.title}</h2>
          <p className="muted">{meta.subtitle}</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowAdd((v) => !v)}>
          <Plus size={16} /> {showAdd ? t.catalog.cancel : t.catalog.addNew}
        </button>
      </div>

      {error && <ErrorBanner message={error} />}

      {lookups && section !== 'countries' && (
        <section className="card catalog-filters">
          <div className="catalog-filter-row">
            {(section === 'systems' || section === 'grades' || section === 'subjects') && (
              <SelectField
                label={t.catalog.filterByCountry}
                value={filterCountry}
                onChange={(e) => {
                  setFilterCountry(e.target.value)
                  setFilterSystem('')
                  setFilterGrade('')
                }}
              >
                <option value="">{t.catalog.allCountries}</option>
                {lookups.countries.map((c) => (
                  <option key={c.id} value={c.id}>{labelPair(c.name, c.name_ar)}</option>
                ))}
              </SelectField>
            )}
            {(section === 'grades' || section === 'subjects') && (
              <SelectField
                label={t.catalog.filterBySystem}
                value={filterSystem}
                onChange={(e) => {
                  setFilterSystem(e.target.value)
                  setFilterGrade('')
                }}
              >
                <option value="">{t.catalog.allSystems}</option>
                {filteredSystems.map((s) => (
                  <option key={s.id} value={s.id}>{labelPair(s.name, s.name_ar)}</option>
                ))}
              </SelectField>
            )}
            {section === 'subjects' && (
              <SelectField
                label={t.catalog.filterByGrade}
                value={filterGrade}
                onChange={(e) => setFilterGrade(e.target.value)}
              >
                <option value="">{t.catalog.allGrades}</option>
                {filteredGrades.map((g) => (
                  <option key={g.id} value={g.id}>{labelPair(g.name, g.name_ar)}</option>
                ))}
              </SelectField>
            )}
          </div>
        </section>
      )}

      {showAdd && (
        <section className="card catalog-add-card">
          <h3>{t.catalog.addNewItem}</h3>
          {section === 'systems' && lookups && (
            <SelectField label={t.catalog.selectCountry} value={addCountry} onChange={(e) => setAddCountry(e.target.value)} required>
              <option value="">{t.catalog.selectCountry}</option>
              {lookups.countries.map((c) => (
                <option key={c.id} value={c.id}>{labelPair(c.name, c.name_ar)}</option>
              ))}
            </SelectField>
          )}
          {section === 'grades' && lookups && (
            <>
              <SelectField label={t.catalog.selectCountry} value={addCountry} onChange={(e) => { setAddCountry(e.target.value); setAddSystem('') }}>
                <option value="">{t.catalog.selectCountry}</option>
                {lookups.countries.map((c) => (
                  <option key={c.id} value={c.id}>{labelPair(c.name, c.name_ar)}</option>
                ))}
              </SelectField>
              <SelectField label={t.catalog.selectSystem} value={addSystem} onChange={(e) => setAddSystem(e.target.value)} required>
                <option value="">{t.catalog.selectSystem}</option>
                {filteredSystems.map((s) => (
                  <option key={s.id} value={s.id}>{labelPair(s.name, s.name_ar)}</option>
                ))}
              </SelectField>
            </>
          )}
          {section === 'subjects' && lookups && (
            <>
              <SelectField label={t.catalog.selectCountry} value={addCountry} onChange={(e) => { setAddCountry(e.target.value); setAddSystem(''); setAddGrade('') }}>
                <option value="">{t.catalog.selectCountry}</option>
                {lookups.countries.map((c) => (
                  <option key={c.id} value={c.id}>{labelPair(c.name, c.name_ar)}</option>
                ))}
              </SelectField>
              <SelectField label={t.catalog.selectSystem} value={addSystem} onChange={(e) => { setAddSystem(e.target.value); setAddGrade('') }}>
                <option value="">{t.catalog.selectSystem}</option>
                {filteredSystems.map((s) => (
                  <option key={s.id} value={s.id}>{labelPair(s.name, s.name_ar)}</option>
                ))}
              </SelectField>
              <SelectField label={t.catalog.selectGrade} value={addGrade} onChange={(e) => setAddGrade(e.target.value)} required>
                <option value="">{t.catalog.selectGrade}</option>
                {filteredGrades.map((g) => (
                  <option key={g.id} value={g.id}>{labelPair(g.name, g.name_ar)}</option>
                ))}
              </SelectField>
            </>
          )}
          <CatalogAddForm
            type={meta.type}
            submitLabel={t.catalog.add}
            onSubmit={async (form) => {
              try {
                await handleCreate(form)
              } catch (e) {
                setError(e instanceof Error ? e.message : t.catalog.updateFailed)
                throw e
              }
            }}
          />
        </section>
      )}

      <section className="card catalog-table-card">
        {loading ? (
          <LoadingSpinner />
        ) : items.length === 0 ? (
          <EmptyState message={t.catalog.emptySection} />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t.catalog.nameAr}</th>
                  <th>{t.catalog.nameEn}</th>
                  {section === 'countries' && <th>{t.catalog.countryCode}</th>}
                  {section === 'grades' && <th>{t.catalog.sortOrder}</th>}
                  {section !== 'countries' && <th>{t.catalog.parentColumn}</th>}
                  <th dir="ltr">{t.catalog.seoSlug} (EN)</th>
                  <th>{t.catalog.seoSlug} (AR)</th>
                  <th>{t.catalog.actionsColumn}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.name_ar ?? '—'}</td>
                    <td dir="ltr">{item.name}</td>
                    {section === 'countries' && (
                      <td dir="ltr">{(item as Country).code ?? '—'}</td>
                    )}
                    {section === 'grades' && (
                      <td dir="ltr">{(item as Grade).sort_order ?? 0}</td>
                    )}
                    {section === 'systems' && lookups && (
                      <td>
                        {(() => {
                          const country = lookups.countryById.get((item as EducationSystem).country_id)
                          return country ? labelPair(country.name, country.name_ar) : '—'
                        })()}
                      </td>
                    )}
                    {section === 'grades' && lookups && (
                      <td>{gradeLabel(item as Grade, lookups)}</td>
                    )}
                    {section === 'subjects' && lookups && (
                      <td>{subjectParentLabel(item as Subject, lookups)}</td>
                    )}
                    <td dir="ltr" className="mono-cell">{catalogSeoOf(item).slug_en || '—'}</td>
                    <td className="mono-cell">{catalogSeoOf(item).slug_ar || '—'}</td>
                    <td>
                      <div className="table-actions">
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => setEditItem(item)}
                          title={t.catalog.edit}
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          onClick={() => void handleDelete(item)}
                          disabled={deletingId === item.id}
                          title={t.catalog.delete}
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

      {editItem && (
        <CatalogItemEditor
          type={meta.type}
          item={editItem}
          label={labelPair(editItem.name, editItem.name_ar)}
          onClose={() => setEditItem(null)}
          onSaved={refresh}
          onError={(msg) => setError(msg || null)}
        />
      )}
    </div>
  )
}
