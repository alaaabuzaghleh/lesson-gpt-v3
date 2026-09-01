import { NavLink, Outlet } from 'react-router-dom'
import {
  BookOpen,
  Briefcase,
  LayoutDashboard,
  Search,
  GraduationCap,
} from 'lucide-react'
import { t } from '../i18n/ar'

const NAV = [
  { to: '/', label: t.nav.dashboard, icon: LayoutDashboard, end: true },
  { to: '/books', label: t.nav.books, icon: BookOpen },
  { to: '/jobs', label: t.nav.jobs, icon: Briefcase },
  { to: '/search', label: t.nav.search, icon: Search },
]

export function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <GraduationCap size={28} strokeWidth={2.2} />
          <div>
            <strong>{t.brand.title}</strong>
            <span>{t.brand.subtitle}</span>
          </div>
        </div>
        <nav className="nav">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span>{t.brand.footer}</span>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
