import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ApiError } from './api/client'
import { Layout } from './components/Layout'
import { Spinner } from './components/ui'
import { AuthProvider, useAuth } from './context/AuthContext'
import { RealtimeProvider } from './context/RealtimeContext'
import { ToastProvider } from './context/ToastContext'
import { OrdersPage, ReservationsPage, SalesPage } from './pages/CommercePages'
import { DashboardPage } from './pages/DashboardPage'
import { HistoryPage } from './pages/HistoryPage'
import { LoginPage } from './pages/LoginPage'
import { NewVehiclePage } from './pages/NewVehiclePage'
import { SettingsPage } from './pages/SettingsPage'
import { VehicleDetailPage } from './pages/VehicleDetailPage'
import { VehiclesPage } from './pages/VehiclesPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Los datos se refrescan por eventos WebSocket; no hace falta volver a pedirlos al enfocar la ventana
      refetchOnWindowFocus: false,
      staleTime: 30_000,
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2
    }
  }
})

function Routed(): React.JSX.Element {
  const { ready, user } = useAuth()
  if (!ready) return <div className="login-screen"><Spinner label="Iniciando AutoMarket…" /></div>
  if (!user) return <LoginPage />

  return (
    <RealtimeProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="vehiculos" element={<VehiclesPage />} />
          <Route path="vehiculos/nuevo" element={<NewVehiclePage />} />
          <Route path="vehiculos/:id" element={<VehicleDetailPage />} />
          <Route path="reservas" element={<ReservationsPage />} />
          <Route path="ordenes" element={<OrdersPage />} />
          <Route path="ventas" element={<SalesPage />} />
          <Route path="historial" element={<HistoryPage />} />
          <Route path="configuracion" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </RealtimeProvider>
  )
}

export default function App(): React.JSX.Element {
  // HashRouter: funciona igual en desarrollo (http://) y en el .exe empaquetado (file://)
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <HashRouter>
            <Routed />
          </HashRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}
