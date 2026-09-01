import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { GraduationCap, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { ThemeToggle } from '../components/ThemeToggle'
import { ErrorBanner, LoadingSpinner } from '../components/ui'
import { t } from '../i18n/ar'

export function LoginPage() {
  const { login, token, loading } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (loading) return <LoadingSpinner />
  if (token) {
    const from = (location.state as { from?: string } | null)?.from ?? '/'
    return <Navigate to={from} replace />
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(email, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : t.auth.loginFailed)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <section className="login-hero" aria-hidden="false">
        <div className="login-hero-content">
          <div className="login-hero-badge">
            <Sparkles size={16} />
            {t.brand.subtitle}
          </div>
          <h2>{t.auth.heroTitle}</h2>
          <p>{t.auth.heroSubtitle}</p>
          <ul className="login-features">
            {t.auth.heroFeatures.map((feature) => (
              <li key={feature}>
                <span className="login-feature-dot" />
                {feature}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-panel-top">
          <ThemeToggle />
        </div>
        <form className="login-card" onSubmit={handleSubmit}>
          <div className="brand login-brand">
            <div className="brand-icon">
              <GraduationCap size={28} />
            </div>
            <div>
              <strong>{t.brand.title}</strong>
              <span>{t.brand.subtitle}</span>
            </div>
          </div>
          <h1>{t.auth.loginTitle}</h1>
          <p className="muted">{t.auth.loginSubtitle}</p>
          {error && <ErrorBanner message={error} />}
          <label>
            {t.auth.email}
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              dir="ltr"
              autoComplete="email"
              placeholder="admin@example.com"
            />
          </label>
          <label>
            {t.auth.password}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              dir="ltr"
              autoComplete="current-password"
            />
          </label>
          <button type="submit" className="btn btn-primary btn-lg" disabled={submitting}>
            {submitting ? t.auth.loggingIn : t.auth.login}
          </button>
        </form>
      </section>
    </div>
  )
}
