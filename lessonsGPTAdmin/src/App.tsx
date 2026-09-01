import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { BooksPage } from './pages/BooksPage'
import { BookDetailPage } from './pages/BookDetailPage'
import { JobsPage } from './pages/JobsPage'
import { JobDetailPage } from './pages/JobDetailPage'
import { SearchPage } from './pages/SearchPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="books" element={<BooksPage />} />
          <Route path="books/:resourceId" element={<BookDetailPage />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="jobs/:jobId" element={<JobDetailPage />} />
          <Route path="search" element={<SearchPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
