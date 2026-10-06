import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '@/lib/auth'
import { HealthProvider } from '@/lib/health'
import { Toaster } from '@/components/ui/toaster'
import Layout from '@/components/Layout'
import Account from '@/pages/Account'
import Analyse from '@/pages/Analyse'
import Connecting from '@/pages/Connecting'
import History from '@/pages/History'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import ResetPassword from '@/pages/ResetPassword'

export default function App() {
  return (
    <HealthProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Connecting />} />
              <Route path="/analyse" element={<Analyse />} />
              <Route path="/history" element={<History />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/account" element={<Account />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster />
      </AuthProvider>
    </HealthProvider>
  )
}
