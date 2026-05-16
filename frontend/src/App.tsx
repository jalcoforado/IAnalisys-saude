import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/modules/auth/AuthContext'
import { SettingsProvider } from '@/contexts/SettingsContext'
import { PageTitleProvider } from '@/contexts/PageTitleContext'
import { TenantProvider } from '@/contexts/TenantContext'
import { SonIAProvider } from '@/components/sonia/SonIAContext'
import PrivateRoute from '@/components/common/PrivateRoute'
import RequirePermission from '@/components/common/RequirePermission'
import AppShell from '@/components/layout/AppShell'
import LoginPage from '@/modules/auth/LoginPage'
import ForgotPasswordPage from '@/modules/auth/ForgotPasswordPage'
import ResetPasswordPage from '@/modules/auth/ResetPasswordPage'
import HomePage from '@/pages/HomePage'
import DesignSystem from '@/pages/DesignSystem'
import SyncPage from '@/modules/admin/SyncPage'
import FinanceiroPage from '@/modules/financeiro/FinanceiroPage'
import DREPage from '@/modules/financeiro/DREPage'
import AnaliseFinanceiroPage from '@/modules/analise/financeiro/FinanceiroPage'
import AnaliseComercialPage from '@/modules/analise/comercial/ComercialPage'
import DashboardPacientesPage from '@/modules/pacientes/DashboardPacientesPage'
import CaptacaoPage from '@/modules/pacientes/CaptacaoPage'
import InteligenciaPage from '@/modules/pacientes/InteligenciaPage'
import SettingsPage from '@/modules/settings/SettingsPage'
import CompanySettingsPage from '@/modules/empresa/CompanySettingsPage'
import MetaConfigPage from '@/modules/empresa/MetaConfigPage'
import VisaoGeralPage from '@/modules/marketing/VisaoGeralPage'
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
          <SonIAProvider>
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
              path="/financeiro/dre"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="financeiro.read">
                      <DREPage />
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
              path="/pacientes"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="dashboard.read">
                      <DashboardPacientesPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/pacientes/captacao"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="dashboard.read">
                      <CaptacaoPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/pacientes/inteligencia"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="dashboard.read">
                      <InteligenciaPage />
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
            <Route
              path="/empresa/meta-config"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="empresa.settings.read">
                      <MetaConfigPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
            <Route
              path="/marketing/visao-geral"
              element={
                <PrivateRoute>
                  <AppShell>
                    <RequirePermission permission="empresa.settings.read">
                      <VisaoGeralPage />
                    </RequirePermission>
                  </AppShell>
                </PrivateRoute>
              }
            />
          </Routes>
          </SonIAProvider>
          </PageTitleProvider>
          </TenantProvider>
        </AuthProvider>
      </SettingsProvider>
    </BrowserRouter>
  )
}

export default App
