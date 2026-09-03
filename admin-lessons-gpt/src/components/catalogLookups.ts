import type { Country, EducationSystem, Grade, Subject } from '../types/api'

export type CatalogLookups = {
  countries: Country[]
  systems: EducationSystem[]
  grades: Grade[]
  countryById: Map<string, Country>
  systemById: Map<string, EducationSystem>
  gradeById: Map<string, Grade>
}

export function buildCatalogLookups(tree: Country[]): CatalogLookups {
  const countries = tree
  const systems: EducationSystem[] = []
  const grades: Grade[] = []
  const countryById = new Map<string, Country>()
  const systemById = new Map<string, EducationSystem>()
  const gradeById = new Map<string, Grade>()

  for (const c of tree) {
    countryById.set(c.id, c)
    for (const s of c.education_systems ?? []) {
      systems.push(s)
      systemById.set(s.id, s)
      for (const g of s.grades ?? []) {
        grades.push(g)
        gradeById.set(g.id, g)
      }
    }
  }

  return { countries, systems, grades, countryById, systemById, gradeById }
}

export function labelPair(name: string, nameAr?: string | null) {
  const ar = nameAr?.trim()
  const en = name.trim()
  if (ar && en && ar !== en) return `${ar} · ${en}`
  return ar || en
}

export function systemLabel(system: EducationSystem, lookups: CatalogLookups) {
  const country = lookups.countryById.get(system.country_id)
  const cName = country ? labelPair(country.name, country.name_ar) : '—'
  return `${cName} › ${labelPair(system.name, system.name_ar)}`
}

export function gradeLabel(grade: Grade, lookups: CatalogLookups) {
  const system = lookups.systemById.get(grade.education_system_id)
  if (!system) return labelPair(grade.name, grade.name_ar)
  return `${systemLabel(system, lookups)} › ${labelPair(grade.name, grade.name_ar)}`
}

export function subjectParentLabel(subject: Subject, lookups: CatalogLookups) {
  const grade = lookups.gradeById.get(subject.grade_id)
  if (!grade) return '—'
  return gradeLabel(grade, lookups)
}
