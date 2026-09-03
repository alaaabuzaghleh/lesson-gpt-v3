import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { useId } from 'react'
import type { JobStatus } from '../types/api'
import { formatDateAr, statusLabel, t } from '../i18n/ar'

const STATUS_STYLES: Record<JobStatus, string> = {
  queued: 'badge-queued',
  running: 'badge-running',
  cancel_requested: 'badge-warning',
  cancelled: 'badge-muted',
  paused: 'badge-warning',
  failed: 'badge-failed',
  completed: 'badge-success',
}

export function StatusBadge({ status }: { status: JobStatus | string }) {
  const cls = STATUS_STYLES[status as JobStatus] ?? 'badge-muted'
  return <span className={`badge ${cls}`}>{statusLabel(status)}</span>
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const pct = Math.min(100, Math.max(0, value))
  return (
    <div className="progress-wrap">
      {label && <div className="progress-label">{label}</div>}
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="progress-pct">{pct.toFixed(1)}%</span>
    </div>
  )
}

export function StatCard({
  title,
  value,
  subtitle,
  accent,
  icon,
}: {
  title: string
  value: string | number
  subtitle?: string
  accent?: string
  icon?: ReactNode
}) {
  const style = accent
    ? ({ '--stat-accent': accent, '--stat-accent-soft': `${accent}22` } as React.CSSProperties)
    : undefined

  return (
    <div className="stat-card" style={style}>
      <div className="stat-card-head">
        <div className="stat-title">{title}</div>
        {icon && <div className="stat-icon">{icon}</div>}
      </div>
      <div className="stat-value">{value}</div>
      {subtitle && <div className="stat-sub">{subtitle}</div>}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>
}

export function LoadingSpinner() {
  return <div className="spinner" aria-label={t.common.loading} />
}

export function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner">{message}</div>
}

export function JsonViewer({ data }: { data: unknown }) {
  return (
    <pre className="json-viewer" dir="ltr">{JSON.stringify(data, null, 2)}</pre>
  )
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} بايت`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} ك.ب`
  return `${(bytes / (1024 * 1024)).toFixed(1)} م.ب`
}

export const formatDate = formatDateAr

type FieldShellProps = {
  label: string
  hint?: string
  id: string
  required?: boolean
  children: ReactNode
}

export function FormField({ label, hint, id, required, children }: FieldShellProps) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
        {required && <span className="field-required" aria-hidden>*</span>}
      </label>
      {children}
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  )
}

type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string
  hint?: string
  icon?: ReactNode
}

export function TextField({ label, hint, icon, className = '', id, ...props }: TextFieldProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const control = (
    <div className={`field-control${icon ? ' has-icon' : ''}`}>
      {icon && <span className="field-icon" aria-hidden>{icon}</span>}
      <input id={inputId} className={`field-input ${className}`.trim()} {...props} />
    </div>
  )
  if (!label) return control
  return (
    <FormField label={label} hint={hint} id={inputId} required={props.required}>
      {control}
    </FormField>
  )
}

type SelectFieldProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string
  hint?: string
  children: ReactNode
}

export function SelectField({ label, hint, className = '', id, children, ...props }: SelectFieldProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const control = (
    <div className="field-control is-select">
      <select id={inputId} className={`field-input field-select ${className}`.trim()} {...props}>
        {children}
      </select>
    </div>
  )
  if (!label) return control
  return (
    <FormField label={label} hint={hint} id={inputId} required={props.required}>
      {control}
    </FormField>
  )
}

type TextAreaFieldProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string
  hint?: string
}

export function TextAreaField({ label, hint, className = '', id, ...props }: TextAreaFieldProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const control = (
    <div className="field-control is-textarea">
      <textarea id={inputId} className={`field-input field-textarea ${className}`.trim()} {...props} />
    </div>
  )
  if (!label) return control
  return (
    <FormField label={label} hint={hint} id={inputId} required={props.required}>
      {control}
    </FormField>
  )
}

export function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="form-section">
      <h3 className="form-section-title">{title}</h3>
      <div className="form-section-body">{children}</div>
    </div>
  )
}
