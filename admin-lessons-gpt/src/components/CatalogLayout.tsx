import { NavLink, Outlet } from 'react-router-dom'
import { Globe2, Building2, GraduationCap, BookOpen } from 'lucide-react'
import { t } from '../i18n/ar'

const SECTIONS = [
  { to: '/catalog/countries', label: t.catalog.navCountries, icon: Globe2 },
  { to: '/catalog/systems', label: t.catalog.navSystems, icon: Building2 },
  { to: '/catalog/grades', label: t.catalog.navGrades, icon: GraduationCap },
  { to: '/catalog/subjects', label: t.catalog.navSubjects, icon: BookOpen },
] as const

export function CatalogLayout() {
  return (
    <div className="catalog-section-layout">
      <header className="page-header">
        <div>
          <h1>{t.catalog.title}</h1>
          <p>{t.catalog.manageSubtitle}</p>
        </div>
      </header>

      <nav className="catalog-subnav" aria-label={t.catalog.title}>
        {SECTIONS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `catalog-subnav-link${isActive ? ' active' : ''}`}
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  )
}
