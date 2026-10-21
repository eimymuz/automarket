// Piezas de interfaz reutilizables.
import { useState, type ReactNode } from 'react'
import { ApiError } from '../api/client'
import { Icon } from './Icon'

const STATUS_LABEL: Record<string, string> = {
  disponible: 'Disponible', reservado: 'Reservado', vendido: 'Vendido',
  activa: 'Activa', cancelada: 'Cancelada', expirada: 'Vencida', convertida: 'Convertida en orden',
  pendiente: 'Pendiente de pago', pagada: 'Pagada', confirmada: 'Venta confirmada',
  aprobado: 'Aprobado', rechazado: 'Rechazado'
}
// Color de estado + texto siempre juntos (el color nunca es la única señal)
const STATUS_TONE: Record<string, string> = {
  disponible: 'good', reservado: 'warning', vendido: 'neutral',
  activa: 'warning', cancelada: 'neutral', expirada: 'neutral', convertida: 'info',
  pendiente: 'warning', pagada: 'info', confirmada: 'good', aprobado: 'good', rechazado: 'critical'
}

export function StatusBadge({ status }: { status: string }): React.JSX.Element {
  return (
    <span className={`badge badge-${STATUS_TONE[status] ?? 'neutral'}`}>
      <span className="badge-dot" aria-hidden="true" />
      {STATUS_LABEL[status] ?? status}
    </span>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }): React.JSX.Element {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

export function Pagination({ page, total, pageSize, onChange }: {
  page: number; total: number; pageSize: number; onChange: (p: number) => void
}): React.JSX.Element | null {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (total === 0) return null
  const from = (page - 1) * pageSize + 1
  const to = Math.min(total, page * pageSize)
  return (
    <div className="pagination">
      <span className="muted">{from}–{to} de {total}</span>
      <div>
        <button className="btn btn-ghost" disabled={page <= 1} onClick={() => onChange(page - 1)}>Anterior</button>
        <span className="pagination-page">{page} / {pages}</span>
        <button className="btn btn-ghost" disabled={page >= pages} onClick={() => onChange(page + 1)}>Siguiente</button>
      </div>
    </div>
  )
}

export function Spinner({ label = 'Cargando…' }: { label?: string }): React.JSX.Element {
  return <div className="spinner-wrap"><span className="spinner" aria-hidden="true" /> {label}</div>
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }): React.JSX.Element {
  const message = error instanceof ApiError ? error.message : 'Ocurrió un error inesperado'
  return (
    <div className="alert alert-critical" role="alert">
      <span>{message}</span>
      {onRetry && <button className="btn btn-ghost" onClick={onRetry}>Reintentar</button>}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }): React.JSX.Element {
  return <div className="empty">{children}</div>
}

/** Botón que pide confirmación en el mismo lugar antes de ejecutar una acción irreversible. */
export function ConfirmButton({ label, confirmLabel = '¿Confirmar?', onConfirm, tone = 'primary', disabled, icon }: {
  label: string; confirmLabel?: string; onConfirm: () => void; tone?: 'primary' | 'danger'; disabled?: boolean; icon?: string
}): React.JSX.Element {
  const [asking, setAsking] = useState(false)
  if (asking) {
    return (
      <span className="confirm-inline">
        <span className="muted">{confirmLabel}</span>
        <button className={`btn btn-${tone} btn-sm`} onClick={() => { setAsking(false); onConfirm() }}>Sí</button>
        <button className="btn btn-ghost btn-sm" onClick={() => setAsking(false)}>No</button>
      </span>
    )
  }
  return (
    <button className={`btn btn-${tone === 'danger' ? 'danger-ghost' : 'primary'} btn-sm`} disabled={disabled}
      onClick={() => setAsking(true)}>
      {icon && <Icon name={icon} size={15} />} {label}
    </button>
  )
}

/** Tarjeta de gráfica con alternancia gráfica/tabla (la tabla es el equivalente accesible). */
export function ChartCard({ title, subtitle, chart, table }: {
  title: string; subtitle?: string; chart: ReactNode; table: ReactNode
}): React.JSX.Element {
  const [asTable, setAsTable] = useState(false)
  return (
    <section className="card chart-card">
      <div className="card-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="muted small">{subtitle}</p>}
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => setAsTable(!asTable)}
          aria-label={asTable ? 'Ver como gráfica' : 'Ver como tabla'}>
          <Icon name={asTable ? 'chart' : 'table'} size={15} /> {asTable ? 'Gráfica' : 'Tabla'}
        </button>
      </div>
      {asTable ? <div className="table-wrap">{table}</div> : chart}
    </section>
  )
}
