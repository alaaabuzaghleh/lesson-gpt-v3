import { useCallback, useEffect, useState } from 'react'
import { Mail, User, Lock } from 'lucide-react'
import { api } from '../api/client'
import type { User as AdminUser } from '../types/api'
import { ErrorBanner, LoadingSpinner, TextField } from '../components/ui'
import { t } from '../i18n/ar'

export function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await api.listAdminUsers()
      setUsers(res.items)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : t.admin.loadError)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function createAdmin(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await api.createAdmin({ email, password, full_name: fullName })
      setEmail('')
      setFullName('')
      setPassword('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t.admin.createFailed)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{t.admin.title}</h1>
          <p>{t.admin.subtitle}</p>
        </div>
      </header>
      {error && <ErrorBanner message={error} />}

      <section className="card">
        <h2>{t.admin.createTitle}</h2>
        <form className="form-stack" onSubmit={createAdmin}>
          <TextField
            label={t.admin.fullName}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder={t.admin.fullName}
            icon={<User size={18} />}
            required
          />
          <TextField
            label={t.auth.email}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@example.com"
            icon={<Mail size={18} />}
            required
            dir="ltr"
            autoComplete="email"
          />
          <TextField
            label={t.auth.password}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t.auth.password}
            icon={<Lock size={18} />}
            required
            minLength={8}
            dir="ltr"
            autoComplete="new-password"
            hint={t.admin.passwordHint}
          />
          <button type="submit" className="btn btn-primary">{t.admin.create}</button>
        </form>
      </section>

      <section className="card">
        <h2>{t.admin.listTitle}</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t.admin.fullName}</th>
                <th>{t.auth.email}</th>
                <th>{t.admin.role}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.full_name}</td>
                  <td dir="ltr">{u.email}</td>
                  <td>{u.role === 'super_admin' ? t.admin.superAdmin : t.admin.adminRole}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
