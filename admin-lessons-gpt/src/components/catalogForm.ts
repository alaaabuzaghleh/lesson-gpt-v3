import type { CatalogEntityType, CatalogSeo, Country, EducationSystem, Grade, Subject } from '../types/api'

export type CatalogItem = Country | EducationSystem | Grade | Subject

export type CatalogFormData = {
  name: string
  name_ar: string
  code: string
  sort_order: number
  seo_title_en: string
  seo_title_ar: string
  seo_meta_description_en: string
  seo_meta_description_ar: string
  seo_keywords_en: string
  seo_keywords_ar: string
  seo_description_en: string
  seo_description_ar: string
  slug_en: string
  slug_ar: string
}

export function emptyCatalogForm(): CatalogFormData {
  return {
    name: '',
    name_ar: '',
    code: '',
    sort_order: 0,
    seo_title_en: '',
    seo_title_ar: '',
    seo_meta_description_en: '',
    seo_meta_description_ar: '',
    seo_keywords_en: '',
    seo_keywords_ar: '',
    seo_description_en: '',
    seo_description_ar: '',
    slug_en: '',
    slug_ar: '',
  }
}

export function catalogSeoOf(item: CatalogItem): CatalogSeo {
  const nested = item.seo ?? {}
  const flat = item as CatalogItem & CatalogSeo
  const pick = (key: keyof CatalogSeo) => {
    const value = nested[key] ?? flat[key]
    return typeof value === 'string' ? value : value ?? null
  }
  return {
    seo_title_en: pick('seo_title_en'),
    seo_title_ar: pick('seo_title_ar'),
    seo_meta_description_en: pick('seo_meta_description_en'),
    seo_meta_description_ar: pick('seo_meta_description_ar'),
    seo_keywords_en: pick('seo_keywords_en'),
    seo_keywords_ar: pick('seo_keywords_ar'),
    seo_description_en: pick('seo_description_en'),
    seo_description_ar: pick('seo_description_ar'),
    slug_en: pick('slug_en'),
    slug_ar: pick('slug_ar'),
    hero_image_path: pick('hero_image_path'),
  }
}

export function itemToCatalogForm(item: CatalogItem): CatalogFormData {
  const seo = catalogSeoOf(item)
  return {
    name: item.name ?? '',
    name_ar: item.name_ar ?? '',
    code: 'code' in item ? (item.code ?? '') : '',
    sort_order: 'sort_order' in item ? (item.sort_order ?? 0) : 0,
    seo_title_en: seo.seo_title_en ?? '',
    seo_title_ar: seo.seo_title_ar ?? '',
    seo_meta_description_en: seo.seo_meta_description_en ?? '',
    seo_meta_description_ar: seo.seo_meta_description_ar ?? '',
    seo_keywords_en: seo.seo_keywords_en ?? '',
    seo_keywords_ar: seo.seo_keywords_ar ?? '',
    seo_description_en: seo.seo_description_en ?? '',
    seo_description_ar: seo.seo_description_ar ?? '',
    slug_en: seo.slug_en ?? '',
    slug_ar: seo.slug_ar ?? '',
  }
}

export function catalogFormToPayload(form: CatalogFormData, type: CatalogEntityType) {
  const base: Record<string, unknown> = {
    name: form.name.trim(),
    name_ar: form.name_ar.trim(),
    seo_title_en: form.seo_title_en.trim(),
    seo_title_ar: form.seo_title_ar.trim(),
    seo_meta_description_en: form.seo_meta_description_en.trim(),
    seo_meta_description_ar: form.seo_meta_description_ar.trim(),
    seo_keywords_en: form.seo_keywords_en.trim(),
    seo_keywords_ar: form.seo_keywords_ar.trim(),
    seo_description_en: form.seo_description_en.trim(),
    seo_description_ar: form.seo_description_ar.trim(),
    slug_en: form.slug_en.trim(),
    slug_ar: form.slug_ar.trim(),
  }
  if (type === 'country') {
    base.code = form.code.trim() || null
  }
  if (type === 'grade') {
    base.sort_order = form.sort_order
  }
  return base
}

export function slugifyEn(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u0600-\u06FF\s-]/g, '')
    .replace(/[\s_]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120) || 'item'
}

export function slugifyAr(text: string): string {
  return text
    .trim()
    .replace(/[\s_]+/g, '-')
    .replace(/[^\w\u0600-\u06FF-]/g, '')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120) || 'عنصر'
}

export function syncSeoFromNames(form: CatalogFormData): CatalogFormData {
  const next = { ...form }
  if (!next.seo_title_en.trim()) next.seo_title_en = next.name.trim()
  if (!next.seo_title_ar.trim()) next.seo_title_ar = next.name_ar.trim()
  if (!next.slug_en.trim()) next.slug_en = slugifyEn(next.name)
  if (!next.slug_ar.trim()) next.slug_ar = slugifyAr(next.name_ar || next.name)
  return next
}
