import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useRealtime } from '../context/RealtimeContext'
import { fmtRelative } from '../lib/format'
import { Icon } from './Icon'

const NAV = [
  { to: '/', label: 'Dashboard', icon: 'dashboard', end: true },
  { to: '/vehiculos', label: 'Inventario', icon: 'car' },
  { to: '/vehiculos/nuevo', label: 'Registrar vehículo', icon: 'plus' },
  { to: '/reservas', label: 'Reservas', icon: 'calendar' },
  { to: '/ordenes', label: 'Órdenes', icon: 'cart' },
  { to: '/ventas', label: 'Ventas', icon: 'receipt' },
  { to: '/historial', label: 'Historial', icon: 'history' },
  { to: '/configuracion', label: 'Configuración', icon: 'settings' }
]

const LIVE_LABEL = { online: 'En vivo', connecting: 'Conectando…', offline: 'Sin conexión en vivo' }

export function Layout(): React.JSX.Element {
  const { user, logout, apiUrl } = useAuth()
  const { status, lastEventAt } = useRealtime()

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><Icon name="car" size={20} /></span>
          <span className="brand-name">AutoMarket</span>
        </div>
        <nav>
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end ?? item.to === '/vehiculos'}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`} title={item.label}>
              <Icon name={item.icon} />
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className={`live live-${status}`} title={`Servidor: ${apiUrl}`}>
            <span className="live-dot" aria-hidden="true" />
            <span>{LIVE_LABEL[status]}</span>
            {status === 'online' && lastEventAt && (
              <span className="muted small">· último evento {fmtRelative(lastEventAt.toISOString())}</span>
            )}
          </div>
          <div className="topbar-user">
            <div className="user-chip">
              <strong>{user?.full_name}</strong>
              <span className="muted small">{user?.email}</span>
            </div>
            <button className="btn btn-ghost" onClick={() => logout()} title="Cerrar sesión">
              <Icon name="logout" /> <span className="hide-narrow">Salir</span>
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
