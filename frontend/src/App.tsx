import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import DashboardPage from './pages/Dashboard'
import ExceptionsPage from './pages/Exceptions'
import ExceptionDetailPage from './pages/ExceptionDetail'
import ReconciliationPage from './pages/Reconciliation'
import CashPositionPage from './pages/Cash'
import CopilotPage from './pages/Copilot'
import AuditLogPage from './pages/AuditLog'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="exceptions" element={<ExceptionsPage />} />
          <Route path="exceptions/:id" element={<ExceptionDetailPage />} />
          <Route path="reconciliation" element={<ReconciliationPage />} />
          <Route path="cash" element={<CashPositionPage />} />
          <Route path="copilot" element={<CopilotPage />} />
          <Route path="audit" element={<AuditLogPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
