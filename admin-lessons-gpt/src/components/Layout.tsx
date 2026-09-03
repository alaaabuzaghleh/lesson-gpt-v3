import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  BookOpen,
  Briefcase,
  LayoutDashboard,
  Search,
  GraduationCap,
  FolderTree,
  Users,
  LogOut,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { ThemeToggle } from './ThemeToggle'
import { t } from '../i18n/ar'

function userInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return (name[0] ?? '?').toUpperCase()
}

function roleLabel(role: string | undefined) {
  if (role === 'super_admin') return t.admin.superAdmin
  if (role === 'admin') return t.admin.adminRole
  return role ?? ''
}

export function Layout() {
  const { user, logout, isSuperAdmin } = useAuth()
  const location = useLocation()

  const nav = [
    { to: '/', label: t.nav.dashboard, icon: LayoutDashboard, end: true },
    { to: '/catalog/countries', label: t.nav.catalog, icon: FolderTree, end: false, match: '/catalog' },
    { to: '/books', label: t.nav.books, icon: BookOpen },
    { to: '/jobs', label: t.nav.jobs, icon: Briefcase },
    { to: '/search', label: t.nav.search, icon: Search },
    ...(isSuperAdmin ? [{ to: '/admin/users', label: t.nav.admins, icon: Users, end: false }] : []),
  ]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <GraduationCap size={24} strokeWidth={2.2} />
          </div>
          <div>
            <strong>{t.brand.title}</strong>
            <span>{t.brand.subtitle}</span>
          </div>
        </div>

        <div className="sidebar-top">
          <ThemeToggle compact />
        </div>

        <nav className="nav">
          {nav.map(({ to, label, icon: Icon, end, match }) => {
            const isActive = match
              ? location.pathname.startsWith(match)
              : undefined
            return (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive: linkActive }) =>
                `nav-link${(isActive ?? linkActive) ? ' active' : ''}`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
            )
          })}
        </nav>

        <div className="sidebar-footer sidebar-user">
          <div className="sidebar-user-info">
            <div className="sidebar-avatar" aria-hidden>
              {userInitials(user?.full_name ?? '?')}
            </div>
            <div className="sidebar-user-meta">
              <strong>{user?.full_name}</strong>
              <span dir="ltr">{user?.email}</span>
              <span className="role-badge">{roleLabel(user?.role)}</span>
            </div>
          </div>
          <div className="sidebar-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={logout}>
              <LogOut size={16} /> {t.auth.logout}
            </button>
          </div>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
