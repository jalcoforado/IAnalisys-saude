import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/modules/auth/AuthContext'
import { SettingsProvider } from '@/contexts/SettingsContext'
import { PageTitleProvider } from '@/contexts/PageTitleContext'
import PrivateRoute from '@/components/common/PrivateRoute'
import AppShell from '@/components/layout/AppShell'
import LoginPage from '@/modules/auth/LoginPage'
import HomePage from '@/pages/HomePage'
import DesignSystem from '@/pages/DesignSystem'
import SyncPage from '@/modules/admin/SyncPage'
import DashboardPage from '@/modules/dashboard/DashboardPage'
import SettingsPage from '@/modules/settings/SettingsPage'

function App() {
  return (
    <BrowserRouter>
      <SettingsProvider>
        <AuthProvider>
          <PageTitleProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            {import.meta.env.DEV && (
              <Route path="/design-system" element={<DesignSystem />} />
            )}
            <Route
              path="/"
              element={
                <PrivateRoute>
                  <AppShell><HomePage /></AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/admin/sync"
              element={
                <PrivateRoute>
                  <AppShell><SyncPage /></AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/dashboard"
              element={
                <PrivateRoute>
                  <AppShell><DashboardPage /></AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/configuracoes"
              element={
                <PrivateRoute>
                  <AppShell><SettingsPage /></AppShell>
                </PrivateRoute>
              }
            />
          </Routes>
          </PageTitleProvider>
        </AuthProvider>
      </SettingsProvider>
    </BrowserRouter>
  )
}

export default App
