import { useMemo, useState, type ReactNode } from 'react'
import { Check, ChevronDown, ChevronLeft, FolderTree, Search } from 'lucide-react'
import type { Country, EducationSystem, Grade, Subject } from '../types/api'
import { SelectField } from './ui'
import { t } from '../i18n/ar'

export type CatalogPathSelection = {
  countryId: string
  systemId: string
  gradeId: string
  subjectId: string
}

export const emptyCatalogPath = (): CatalogPathSelection => ({
  countryId: '',
  systemId: '',
  gradeId: '',
  subjectId: '',
})

type Props = {
  tree: Country[]
  value: CatalogPathSelection
  onChange: (next: CatalogPathSelection) => void
  requireSubject?: boolean
  allowEmpty?: boolean
  variant?: 'guided' | 'compact'
  idPrefix?: string
}

type SubjectHit = {
  id: string
  label: string
  path: CatalogPathSelection
}

function arName(name: string, nameAr?: string | null) {
  return nameAr?.trim() || name.trim()
}

function countryLabel(c: Country) {
  return arName(c.name, c.name_ar)
}

function systemLabel(s: EducationSystem) {
  return arName(s.name, s.name_ar)
}

function gradeLabel(g: Grade) {
  return arName(g.name, g.name_ar)
}

function subjectLabel(s: Subject) {
  return arName(s.name, s.name_ar)
}

function collectSubjectHits(tree: Country[], query: string, scope: CatalogPathSelection): SubjectHit[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  const scored: (SubjectHit & { score: number })[] = []
  for (const c of tree) {
    if (scope.countryId && c.id !== scope.countryId) continue
    for (const s of c.education_systems ?? []) {
      if (scope.systemId && s.id !== scope.systemId) continue
      for (const g of s.grades ?? []) {
        if (scope.gradeId && g.id !== scope.gradeId) continue
        for (const sub of g.subjects ?? []) {
          const names = [sub.name, sub.name_ar, g.name, g.name_ar].filter(Boolean).map((n) => n!.toLowerCase())
          if (!names.some((n) => n.includes(q))) continue
          const subjectHit = [sub.name, sub.name_ar].some((n) => n?.toLowerCase().includes(q))
          scored.push({
            id: sub.id,
            label: `${countryLabel(c)} › ${systemLabel(s)} › ${gradeLabel(g)} › ${subjectLabel(sub)}`,
            path: { countryId: c.id, systemId: s.id, gradeId: g.id, subjectId: sub.id },
            score: subjectHit ? 5 : 1,
          })
        }
      }
    }
  }
  scored.sort((a, b) => b.score - a.score)
  if (scope.countryId) return scored.slice(0, 20)

  const byCountry = new Map<string, SubjectHit[]>()
  for (const hit of scored) {
    const list = byCountry.get(hit.path.countryId) ?? []
    list.push(hit)
    byCountry.set(hit.path.countryId, list)
  }
  const buckets = [...byCountry.values()]
  const mixed: SubjectHit[] = []
  let i = 0
  while (mixed.length < 20 && buckets.some((b) => b.length > 0)) {
    const next = buckets[i % buckets.length].shift()
    if (next) mixed.push(next)
    i += 1
  }
  return mixed
}

export function catalogPathLabel(tree: Country[], value: CatalogPathSelection): string {
  const country = tree.find((c) => c.id === value.countryId)
  if (!country) return ''
  const parts = [countryLabel(country)]
  const system = (country.education_systems ?? []).find((s) => s.id === value.systemId)
  if (!system) return parts.join(' › ')
  parts.push(systemLabel(system))
  const grade = (system.grades ?? []).find((g) => g.id === value.gradeId)
  if (!grade) return parts.join(' › ')
  parts.push(gradeLabel(grade))
  const subject = (grade.subjects ?? []).find((s) => s.id === value.subjectId)
  if (subject) parts.push(subjectLabel(subject))
  return parts.join(' › ')
}

export function CatalogPathPicker({
  tree,
  value,
  onChange,
  requireSubject = false,
  allowEmpty = true,
  variant = 'guided',
  idPrefix = 'catalog-path',
}: Props) {
  const [query, setQuery] = useState('')
  const [showTree, setShowTree] = useState(false)
  const [openIds, setOpenIds] = useState<Set<string>>(() => new Set())

  const country = tree.find((c) => c.id === value.countryId)
  const systems = country?.education_systems ?? []
  const system = systems.find((s) => s.id === value.systemId)
  const grades = system?.grades ?? []
  const grade = grades.find((g) => g.id === value.gradeId)
  const subjects = grade?.subjects ?? []
  const hits = useMemo(() => collectSubjectHits(tree, query, value), [tree, query, value])
  const compact = variant === 'compact'

  function select(next: CatalogPathSelection) {
    onChange(next)
    setOpenIds(new Set([next.countryId, next.systemId, next.gradeId].filter(Boolean)))
  }

  function toggleOpen(id: string) {
    setOpenIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const steps = [
    {
      key: 'country',
      n: 1,
      label: t.catalog.selectCountry,
      value: value.countryId,
      enabled: true,
      done: Boolean(value.countryId),
      placeholder: compact || allowEmpty ? t.catalog.allCountries : t.catalog.selectCountry,
      options: tree.map((c) => ({ id: c.id, label: countryLabel(c) })),
      onChange: (id: string) => select({ countryId: id, systemId: '', gradeId: '', subjectId: '' }),
    },
    {
      key: 'system',
      n: 2,
      label: t.catalog.selectSystem,
      value: value.systemId,
      enabled: Boolean(value.countryId),
      done: Boolean(value.systemId),
      placeholder: compact || allowEmpty ? t.catalog.allSystems : t.catalog.selectSystem,
      options: systems.map((s) => ({ id: s.id, label: systemLabel(s) })),
      onChange: (id: string) => select({
        countryId: value.countryId,
        systemId: id,
        gradeId: '',
        subjectId: '',
      }),
    },
    {
      key: 'grade',
      n: 3,
      label: t.catalog.selectGrade,
      value: value.gradeId,
      enabled: Boolean(value.systemId),
      done: Boolean(value.gradeId),
      placeholder: compact || allowEmpty ? t.catalog.allGrades : t.catalog.selectGrade,
      options: grades.map((g) => ({ id: g.id, label: gradeLabel(g) })),
      onChange: (id: string) => select({
        countryId: value.countryId,
        systemId: value.systemId,
        gradeId: id,
        subjectId: '',
      }),
    },
    {
      key: 'subject',
      n: 4,
      label: t.catalog.selectSubject,
      value: value.subjectId,
      enabled: Boolean(value.gradeId),
      done: Boolean(value.subjectId),
      placeholder: compact || allowEmpty ? t.books.allSubjects : t.catalog.selectSubject,
      options: subjects.map((s) => ({ id: s.id, label: subjectLabel(s) })),
      onChange: (id: string) => select({
        countryId: value.countryId,
        systemId: value.systemId,
        gradeId: value.gradeId,
        subjectId: id,
      }),
    },
  ]

  const selects = (
    <div className={compact ? 'catalog-filter-row' : 'catalog-stepper'}>
      {steps.map((step) => (
        compact ? (
          <SelectField
            key={step.key}
            id={`${idPrefix}-${step.key}`}
            label={step.label}
            value={step.value}
            required={requireSubject}
            disabled={!step.enabled}
            onChange={(e) => step.onChange(e.target.value)}
          >
            <option value="">{step.placeholder}</option>
            {step.options.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </SelectField>
        ) : (
          <div
            key={step.key}
            className={`catalog-step${step.done ? ' is-done' : ''}${step.enabled && !step.done ? ' is-current' : ''}`}
          >
            <div className="catalog-step-head">
              <span className="catalog-step-num" aria-hidden>
                {step.done ? <Check size={14} /> : step.n}
              </span>
              <span className="catalog-step-label">{step.label}</span>
            </div>
            <SelectField
              id={`${idPrefix}-${step.key}`}
              value={step.value}
              required={requireSubject}
              disabled={!step.enabled}
              aria-label={step.label}
              onChange={(e) => step.onChange(e.target.value)}
            >
              <option value="">{step.placeholder}</option>
              {step.options.map((o) => (
                <option key={o.id} value={o.id}>{o.label}</option>
              ))}
            </SelectField>
          </div>
        )
      ))}
    </div>
  )

  return (
    <div className={`catalog-picker${compact ? ' is-compact' : ''}`}>
      {!compact && (
        <div className="catalog-picker-search">
          <Search size={16} aria-hidden />
          <input
            id={`${idPrefix}-search`}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t.books.searchSubject}
            aria-label={t.books.searchSubject}
          />
        </div>
      )}

      {query.trim() && !compact ? (
        <ul className="catalog-picker-hits">
          {hits.length === 0 ? (
            <li className="muted">{t.books.noSubjectMatch}</li>
          ) : (
            hits.map((hit) => (
              <li key={hit.id}>
                <button
                  type="button"
                  className={`catalog-picker-hit${value.subjectId === hit.id ? ' selected' : ''}`}
                  onClick={() => {
                    select(hit.path)
                    setQuery('')
                  }}
                >
                  {hit.label}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : (
        selects
      )}

      {compact && value.countryId && (
        <button type="button" className="btn btn-ghost btn-sm catalog-picker-clear" onClick={() => select(emptyCatalogPath())}>
          {t.books.clearFilters}
        </button>
      )}

      {!compact && (
        <div className="catalog-tree-toggle-wrap">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setShowTree((v) => !v)}
          >
            <FolderTree size={14} /> {showTree ? t.books.hideTree : t.books.chooseFromTree}
          </button>
        </div>
      )}

      {showTree && !compact && (
        <div className="catalog-picker-tree" role="tree">
          <ul className="catalog-tree-list">
            {tree.map((c) => (
              <TreeBranch
                key={c.id}
                id={c.id}
                label={countryLabel(c)}
                open={openIds.has(c.id) || value.countryId === c.id}
                selected={value.countryId === c.id && !value.systemId}
                leafSelectable={!requireSubject}
                onToggle={() => toggleOpen(c.id)}
                onSelect={() => select({ countryId: c.id, systemId: '', gradeId: '', subjectId: '' })}
              >
                {(c.education_systems ?? []).map((s) => (
                  <TreeBranch
                    key={s.id}
                    id={s.id}
                    label={systemLabel(s)}
                    open={openIds.has(s.id) || value.systemId === s.id}
                    selected={value.systemId === s.id && !value.gradeId}
                    leafSelectable={!requireSubject}
                    onToggle={() => toggleOpen(s.id)}
                    onSelect={() => select({
                      countryId: c.id,
                      systemId: s.id,
                      gradeId: '',
                      subjectId: '',
                    })}
                  >
                    {(s.grades ?? []).map((g) => (
                      <TreeBranch
                        key={g.id}
                        id={g.id}
                        label={gradeLabel(g)}
                        open={openIds.has(g.id) || value.gradeId === g.id}
                        selected={value.gradeId === g.id && !value.subjectId}
                        leafSelectable={!requireSubject}
                        onToggle={() => toggleOpen(g.id)}
                        onSelect={() => select({
                          countryId: c.id,
                          systemId: s.id,
                          gradeId: g.id,
                          subjectId: '',
                        })}
                      >
                        {(g.subjects ?? []).map((sub) => (
                          <li key={sub.id} role="treeitem" aria-selected={value.subjectId === sub.id}>
                            <button
                              type="button"
                              className={`catalog-tree-item is-leaf${value.subjectId === sub.id ? ' selected' : ''}`}
                              onClick={() => {
                                select({
                                  countryId: c.id,
                                  systemId: s.id,
                                  gradeId: g.id,
                                  subjectId: sub.id,
                                })
                                setShowTree(false)
                              }}
                            >
                              {subjectLabel(sub)}
                            </button>
                          </li>
                        ))}
                      </TreeBranch>
                    ))}
                  </TreeBranch>
                ))}
              </TreeBranch>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function TreeBranch({
  id,
  label,
  open,
  selected,
  leafSelectable,
  onToggle,
  onSelect,
  children,
}: {
  id: string
  label: string
  open: boolean
  selected: boolean
  leafSelectable: boolean
  onToggle: () => void
  onSelect: () => void
  children: ReactNode
}) {
  return (
    <li role="treeitem" aria-expanded={open} aria-selected={selected} data-id={id}>
      <div className={`catalog-tree-item${selected ? ' selected' : ''}`}>
        <button type="button" className="catalog-tree-toggle" onClick={onToggle} aria-expanded={open}>
          {open ? <ChevronDown size={16} /> : <ChevronLeft size={16} />}
        </button>
        <button type="button" className="catalog-tree-label" onClick={leafSelectable ? onSelect : onToggle}>
          {label}
        </button>
      </div>
      {open && <ul className="catalog-tree-children">{children}</ul>}
    </li>
  )
}
