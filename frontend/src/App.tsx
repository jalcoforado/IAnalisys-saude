import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/modules/auth/AuthContext'
import PrivateRoute from '@/components/common/PrivateRoute'
import LoginPage from '@/modules/auth/LoginPage'
import HomePage from '@/pages/HomePage'
import DesignSystem from '@/pages/DesignSystem'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          {import.meta.env.DEV && (
            <Route path="/design-system" element={<DesignSystem />} />
          )}
          <Route
            path="/"
            element={
              <PrivateRoute>
                <HomePage />
              </PrivateRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
