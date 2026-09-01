import { NavLink, Outlet } from 'react-router-dom'
import {
  BookOpen,
  Briefcase,
  LayoutDashboard,
  Search,
  GraduationCap,
} from 'lucide-react'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/books', label: 'Books', icon: BookOpen },
  { to: '/jobs', label: 'Jobs', icon: Briefcase },
  { to: '/search', label: 'Search', icon: Search },
]

export function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <GraduationCap size={28} strokeWidth={2.2} />
          <div>
            <strong>LessonsGPT</strong>
            <span>Admin</span>
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
          <span>Textbook Ingestor v4</span>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
