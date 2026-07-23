import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './features/auth/AuthContext'
import { LoginPage } from './features/auth/LoginPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { FilingSessionsPage } from './features/filingSessions/FilingSessionsPage'
import { QuestionnaireRunnerPage } from './features/questionnaire/QuestionnaireRunnerPage'
import { RegimeComparisonPage } from './features/taxSummary/RegimeComparisonPage'
import { TaxSummaryPage } from './features/taxSummary/TaxSummaryPage'
import { AppLayout } from './components/layout/AppLayout'
import { ProtectedRoute } from './components/layout/ProtectedRoute'
import { NotFoundPage } from './routes/NotFoundPage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route path="/filing-sessions" element={<FilingSessionsPage />} />
            <Route path="/filing-sessions/:filingSessionId/questionnaire" element={<QuestionnaireRunnerPage />} />
            <Route path="/filing-sessions/:filingSessionId/regime-comparison" element={<RegimeComparisonPage />} />
            <Route path="/filing-sessions/:filingSessionId/tax-summary/:regime" element={<TaxSummaryPage />} />
          </Route>

          <Route path="/404" element={<NotFoundPage />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
