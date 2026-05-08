import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/modules/auth/AuthContext'
import { SettingsProvider } from '@/contexts/SettingsContext'
import { PageTitleProvider } from '@/contexts/PageTitleContext'
import { TenantProvider } from '@/contexts/TenantContext'
import PrivateRoute from '@/components/common/PrivateRoute'
import RequirePermission from '@/components/common/RequirePermission'
import AppShell from '@/components/layout/AppShell'
import LoginPage from '@/modules/auth/LoginPage'
import ForgotPasswordPage from '@/modules/auth/ForgotPasswordPage'
import ResetPasswordPage from '@/modules/auth/ResetPasswordPage'
import HomePage from '@/pages/HomePage'
import DesignSystem from '@/pages/DesignSystem'
import SyncPage from '@/modules/admin/SyncPage'
import DashboardPage from '@/modules/dashboard/DashboardPage'
import FinanceiroPage from '@/modules/financeiro/FinanceiroPage'
import AnaliseFinanceiroPage from '@/modules/analise/financeiro/FinanceiroPage'
import AnaliseComercialPage from '@/modules/analise/comercial/ComercialPage'
import SettingsPage from '@/modules/settings/SettingsPage'
import CompanySettingsPage from '@/modules/empresa/CompanySettingsPage'
import PermissionsPage from '@/modules/empresa/PermissionsPage'
import UsersPage from '@/modules/empresa/UsersPage'
import AgendaPage from '@/modules/agenda/AgendaPage'

function App() {
  return (
    <BrowserRouter>
      <SettingsProvider>
        <AuthProvider>
          <TenantProvider>
          <PageTitleProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/recuperar-senha" element={<ForgotPasswordPage />} />
            <Route path="/auth/redefinir-senha" element={<ResetPasswordPage />} />
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
                  <AppShell>
                    <RequirePermission permission="sync.run">
                      <SyncPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/dashboard"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="dashboard.read">
                      <DashboardPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/agenda"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="agenda.read">
                      <AgendaPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/financeiro"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="financeiro.read">
                      <FinanceiroPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/analise/financeiro"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="dashboard.read">
                      <AnaliseFinanceiroPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/analise/comercial"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="dashboard.read">
                      <AnaliseComercialPage />
                    </RequirePermission>
                  </AppShell>
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
            <Route
              path="/empresa/configuracoes"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="empresa.settings.read">
                      <CompanySettingsPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/empresa/permissoes"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="empresa.permissions.manage">
                      <PermissionsPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/empresa/usuarios"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="usuarios.read">
                      <UsersPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
          </Routes>
          </PageTitleProvider>
          </TenantProvider>
        </AuthProvider>
      </SettingsProvider>
    </BrowserRouter>
  )
}

export default App
