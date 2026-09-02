import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { Layout } from './components/Layout'
import { CatalogLayout } from './components/CatalogLayout'
import { CatalogSectionPage } from './components/CatalogSectionPage'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { BooksPage } from './pages/BooksPage'
import { BookDetailPage } from './pages/BookDetailPage'
import { JobsPage } from './pages/JobsPage'
import { JobDetailPage } from './pages/JobDetailPage'
import { SearchPage } from './pages/SearchPage'
import { AdminUsersPage } from './pages/AdminUsersPage'

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="catalog" element={<CatalogLayout />}>
                <Route index element={<Navigate to="countries" replace />} />
                <Route path="countries" element={<CatalogSectionPage section="countries" />} />
                <Route path="systems" element={<CatalogSectionPage section="systems" />} />
                <Route path="grades" element={<CatalogSectionPage section="grades" />} />
                <Route path="subjects" element={<CatalogSectionPage section="subjects" />} />
              </Route>
              <Route path="books" element={<BooksPage />} />
              <Route path="books/:resourceId" element={<BookDetailPage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="jobs/:jobId" element={<JobDetailPage />} />
              <Route path="search" element={<SearchPage />} />
              <Route path="admin/users" element={<AdminUsersPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}
