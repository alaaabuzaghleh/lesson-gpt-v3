import type { JobStatus } from '../types/api'

const STATUS_STYLES: Record<JobStatus, string> = {
  queued: 'badge-queued',
  running: 'badge-running',
  cancel_requested: 'badge-warning',
  cancelled: 'badge-muted',
  failed: 'badge-failed',
  completed: 'badge-success',
}

export function StatusBadge({ status }: { status: JobStatus | string }) {
  const cls = STATUS_STYLES[status as JobStatus] ?? 'badge-muted'
  return <span className={`badge ${cls}`}>{status.replace(/_/g, ' ')}</span>
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
}: {
  title: string
  value: string | number
  subtitle?: string
  accent?: string
}) {
  return (
    <div className="stat-card" style={accent ? { borderTopColor: accent } : undefined}>
      <div className="stat-title">{title}</div>
      <div className="stat-value">{value}</div>
      {subtitle && <div className="stat-sub">{subtitle}</div>}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>
}

export function LoadingSpinner() {
  return <div className="spinner" aria-label="Loading" />
}

export function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner">{message}</div>
}

export function JsonViewer({ data }: { data: unknown }) {
  return (
    <pre className="json-viewer">{JSON.stringify(data, null, 2)}</pre>
  )
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}
