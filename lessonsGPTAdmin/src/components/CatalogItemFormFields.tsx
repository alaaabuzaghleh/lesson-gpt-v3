import type { CatalogEntityType } from '../types/api'
import { TextAreaField, TextField } from './ui'
import { RichTextEditor } from './RichTextEditor'
import { t } from '../i18n/ar'
import type { CatalogFormData } from './catalogForm'

type CatalogItemFormFieldsProps = {
  type: CatalogEntityType
  form: CatalogFormData
  langTab?: 'ar' | 'en'
  onChange: (patch: Partial<CatalogFormData>) => void
}

export function CatalogItemFormFields({ type, form, langTab, onChange }: CatalogItemFormFieldsProps) {
  const showAr = !langTab || langTab === 'ar'
  const showEn = !langTab || langTab === 'en'

  return (
    <>
      {showAr && (
        <div className="seo-lang-panel">
          <h4 className="seo-lang-heading">{t.catalog.seoTabAr}</h4>
          <TextField
            label={t.catalog.nameAr}
            value={form.name_ar}
            onChange={(e) => onChange({ name_ar: e.target.value })}
            required
          />
          <TextField
            label={t.catalog.seoPageTitle}
            value={form.seo_title_ar}
            onChange={(e) => onChange({ seo_title_ar: e.target.value })}
          />
          <TextField
            label={t.catalog.seoSlug}
            value={form.slug_ar}
            onChange={(e) => onChange({ slug_ar: e.target.value })}
            hint={t.catalog.seoSlugScopedHint}
          />
          <TextAreaField
            label={t.catalog.seoMetaDescription}
            value={form.seo_meta_description_ar}
            onChange={(e) => onChange({ seo_meta_description_ar: e.target.value })}
            rows={3}
          />
          <TextField
            label={t.catalog.seoKeywords}
            value={form.seo_keywords_ar}
            onChange={(e) => onChange({ seo_keywords_ar: e.target.value })}
            hint={t.catalog.seoKeywordsHint}
          />
          <RichTextEditor
            label={t.catalog.seoDescription}
            value={form.seo_description_ar}
            onChange={(html) => onChange({ seo_description_ar: html })}
            dir="rtl"
          />
        </div>
      )}

      {showEn && (
        <div className="seo-lang-panel" dir="ltr">
          <h4 className="seo-lang-heading">{t.catalog.seoTabEn}</h4>
          <TextField
            label={t.catalog.nameEn}
            value={form.name}
            onChange={(e) => onChange({ name: e.target.value })}
            required
          />
          <TextField
            label={t.catalog.seoPageTitle}
            value={form.seo_title_en}
            onChange={(e) => onChange({ seo_title_en: e.target.value })}
          />
          <TextField
            label={t.catalog.seoSlug}
            value={form.slug_en}
            onChange={(e) => onChange({ slug_en: e.target.value })}
            hint={t.catalog.seoSlugScopedHint}
          />
          <TextAreaField
            label={t.catalog.seoMetaDescription}
            value={form.seo_meta_description_en}
            onChange={(e) => onChange({ seo_meta_description_en: e.target.value })}
            rows={3}
          />
          <TextField
            label={t.catalog.seoKeywords}
            value={form.seo_keywords_en}
            onChange={(e) => onChange({ seo_keywords_en: e.target.value })}
            hint={t.catalog.seoKeywordsHint}
          />
          <RichTextEditor
            label={t.catalog.seoDescription}
            value={form.seo_description_en}
            onChange={(html) => onChange({ seo_description_en: html })}
            dir="ltr"
          />
          {type === 'country' && (
            <TextField
              label={t.catalog.countryCode}
              value={form.code}
              onChange={(e) => onChange({ code: e.target.value })}
              placeholder="JO"
            />
          )}
          {type === 'grade' && (
            <TextField
              label={t.catalog.sortOrder}
              type="number"
              value={form.sort_order}
              onChange={(e) => onChange({ sort_order: +e.target.value })}
            />
          )}
        </div>
      )}
    </>
  )
}
