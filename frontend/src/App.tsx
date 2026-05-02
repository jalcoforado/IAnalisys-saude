import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/modules/auth/AuthContext'
import PrivateRoute from '@/components/common/PrivateRoute'
import LoginPage from '@/modules/auth/LoginPage'
import HomePage from '@/pages/HomePage'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
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
