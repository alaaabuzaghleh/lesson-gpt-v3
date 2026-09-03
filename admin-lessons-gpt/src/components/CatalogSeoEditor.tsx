import { useEffect, useRef, useState } from 'react'
import { ImageIcon, Trash2, X } from 'lucide-react'
import { api } from '../api/client'
import type { CatalogEntityType } from '../types/api'
import { FormSection } from './ui'
import { CatalogItemFormFields } from './CatalogItemFormFields'
import {
  catalogFormToPayload,
  emptyCatalogForm,
  itemToCatalogForm,
  syncSeoFromNames,
  type CatalogFormData,
  type CatalogItem,
} from './catalogForm'
import { t } from '../i18n/ar'

type CatalogItemEditorProps = {
  type: CatalogEntityType
  item: CatalogItem
  label: string
  onClose: () => void
  onSaved: () => Promise<void>
  onError: (message: string) => void
}

export function CatalogItemEditor({ type, item, label, onClose, onSaved, onError }: CatalogItemEditorProps) {
  const [form, setForm] = useState<CatalogFormData>(() => itemToCatalogForm(item))
  const [loadingItem, setLoadingItem] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [hasCustomHero, setHasCustomHero] = useState(Boolean(item.has_custom_hero))
  const [heroVersion, setHeroVersion] = useState(Date.now())
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoadingItem(true)
    api.getCatalogItem(type, item.id)
      .then((full) => {
        if (cancelled) return
        setForm(itemToCatalogForm(full))
        setHasCustomHero(Boolean(full.has_custom_hero))
        setHeroVersion(Date.now())
      })
      .catch((e) => {
        if (cancelled) return
        setForm(itemToCatalogForm(item))
        onError(e instanceof Error ? e.message : t.catalog.loadError)
      })
      .finally(() => {
        if (!cancelled) setLoadingItem(false)
      })
    return () => {
      cancelled = true
    }
  }, [item.id, type])

  const patchForm = (patch: Partial<CatalogFormData>) => setForm((prev) => ({ ...prev, ...patch }))

  const handleSave = async () => {
    if (!form.name.trim() || !form.name_ar.trim()) {
      onError(t.catalog.namesRequired)
      return
    }
    setSaving(true)
    onError('')
    try {
      const payload = catalogFormToPayload(syncSeoFromNames(form), type)
      await api.updateCatalogItem(type, item.id, payload)
      await onSaved()
      onClose()
    } catch (e) {
      onError(e instanceof Error ? e.message : t.catalog.seoSaveFailed)
    } finally {
      setSaving(false)
    }
  }

  const handleHeroUpload = async (file: File) => {
    setUploading(true)
    onError('')
    try {
      await api.uploadCatalogHero(type, item.id, file)
      setHasCustomHero(true)
      setHeroVersion(Date.now())
      await onSaved()
    } catch (e) {
      onError(e instanceof Error ? e.message : t.catalog.seoHeroUploadFailed)
    } finally {
      setUploading(false)
    }
  }

  const handleHeroRemove = async () => {
    if (!window.confirm(t.catalog.seoRemoveHeroConfirm)) return
    setUploading(true)
    onError('')
    try {
      await api.deleteCatalogHero(type, item.id)
      setHasCustomHero(false)
      setHeroVersion(Date.now())
      await onSaved()
    } catch (e) {
      onError(e instanceof Error ? e.message : t.catalog.seoHeroRemoveFailed)
    } finally {
      setUploading(false)
    }
  }

  const heroUrl = api.catalogHeroUrl(type, item.id, heroVersion)

  return (
    <div className="seo-modal-backdrop" onClick={onClose} role="presentation">
      <div className="seo-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <header className="seo-modal-header">
          <div>
            <h2 className="seo-modal-title">{t.catalog.editItem}</h2>
            <p className="seo-modal-subtitle">{label}</p>
          </div>
          <button type="button" className="tree-action-btn" onClick={onClose} aria-label={t.catalog.cancel}>
            <X size={18} />
          </button>
        </header>

        <div className="seo-modal-body">
          <FormSection title={t.catalog.seoHeroSection}>
            <div className="seo-hero-preview-wrap">
              <img src={heroUrl} alt="" className="seo-hero-preview" />
              <div className="seo-hero-meta">
                <span className={`seo-hero-badge${hasCustomHero ? ' is-custom' : ''}`}>
                  {hasCustomHero ? t.catalog.seoHeroCustom : t.catalog.seoHeroDefault}
                </span>
                <p className="field-hint">{t.catalog.seoHeroHint}</p>
              </div>
            </div>
            <div className="seo-hero-actions">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/svg+xml"
                className="seo-file-input"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) void handleHeroUpload(file)
                  e.target.value = ''
                }}
              />
              <button
                type="button"
                className="btn btn-sm"
                disabled={uploading}
                onClick={() => fileInputRef.current?.click()}
              >
                <ImageIcon size={14} /> {uploading ? t.catalog.saving : t.catalog.seoUploadHero}
              </button>
              {hasCustomHero && (
                <button type="button" className="btn btn-sm btn-danger" disabled={uploading} onClick={() => void handleHeroRemove()}>
                  <Trash2 size={14} /> {t.catalog.seoRemoveHero}
                </button>
              )}
            </div>
          </FormSection>

          {loadingItem ? (
            <p className="muted">{t.common.loading}</p>
          ) : (
            <CatalogItemFormFields type={type} form={form} onChange={patchForm} />
          )}
        </div>

        <footer className="seo-modal-footer">
          <button type="button" className="btn btn-primary" onClick={() => void handleSave()} disabled={saving || uploading}>
            {saving ? t.catalog.saving : t.catalog.save}
          </button>
          <button type="button" className="btn" onClick={onClose} disabled={saving || uploading}>
            {t.catalog.cancel}
          </button>
        </footer>
      </div>
    </div>
  )
}

type CatalogAddFormProps = {
  type: CatalogEntityType
  onSubmit: (form: CatalogFormData) => Promise<void>
  submitLabel?: string
}

export function CatalogAddForm({ type, onSubmit, submitLabel }: CatalogAddFormProps) {
  const [form, setForm] = useState<CatalogFormData>(emptyCatalogForm)
  const [saving, setSaving] = useState(false)

  const handleSubmit = async () => {
    if (!form.name.trim() || !form.name_ar.trim()) return
    setSaving(true)
    try {
      await onSubmit(syncSeoFromNames(form))
      setForm(emptyCatalogForm())
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="catalog-add-form">
      <CatalogItemFormFields
        type={type}
        form={form}
        onChange={(patch) => setForm((prev) => ({ ...prev, ...patch }))}
      />
      <button
        type="button"
        className="btn btn-primary"
        onClick={() => void handleSubmit()}
        disabled={saving || !form.name.trim() || !form.name_ar.trim()}
      >
        {saving ? t.catalog.saving : (submitLabel ?? t.catalog.add)}
      </button>
    </div>
  )
}

// Backward-compatible export name
export { CatalogItemEditor as CatalogSeoEditor }
