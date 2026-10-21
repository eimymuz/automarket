// Reservas, órdenes de compra y ventas: lo que llega desde la página web y se gestiona aquí.
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { OrderStatus, ReservationStatus, VehicleSummary } from '../api/types'
import { ConfirmButton, Empty, ErrorBox, PageHeader, Pagination, Spinner, StatusBadge } from '../components/ui'
import { useToast } from '../context/ToastContext'
import { fmtDate, fmtMoney, fmtRemaining } from '../lib/format'

function usePageParam(): [number, string, (key: string, value: string) => void] {
  const [params, setParams] = useSearchParams()
  const set = (key: string, value: string): void => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }
  return [Number(params.get('page') ?? 1), params.get('status') ?? '', set]
}

function useAction(): (fn: () => Promise<unknown>, ok: string) => Promise<void> {
  const toast = useToast()
  const queryClient = useQueryClient()
  return async (fn, ok) => {
    try {
      await fn()
      toast('success', ok)
      for (const key of ['reservations', 'orders', 'sales', 'dashboard', 'vehicles']) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
    } catch (e) {
      toast('error', 'No se pudo completar', e instanceof ApiError ? e.message : String(e))
    }
  }
}

function VehicleCell({ v }: { v: VehicleSummary }): React.JSX.Element {
  return (
    <td>
      <Link to={`/vehiculos/${v.id}`} onClick={(e) => e.stopPropagation()}><strong>{v.brand} {v.model}</strong></Link>
      <div className="muted small"><span className="mono">{v.stock_number}</span> · {v.version} {v.year}</div>
    </td>
  )
}

function StatusTabs<T extends string>({ value, options, onChange }: {
  value: string; options: [T | '', string][]; onChange: (v: string) => void
}): React.JSX.Element {
  return (
    <div className="tabs" role="tablist">
      {options.map(([v, label]) => (
        <button key={v || 'all'} role="tab" aria-selected={value === v} className={`tab${value === v ? ' active' : ''}`}
          onClick={() => onChange(v)}>{label}</button>
      ))}
    </div>
  )
}

// ======================= Reservas =======================
export function ReservationsPage(): React.JSX.Element {
  const [page, status, set] = usePageParam()
  const act = useAction()
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['reservations', status, page],
    queryFn: () => endpoints.reservations(status as ReservationStatus | '', page),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000 // el tiempo restante se recalcula aunque no haya eventos
  })

  return (
    <div>
      <PageHeader title="Reservas" subtitle="Reservas hechas desde la página web (o por un administrador). Vencen solas." />
      <StatusTabs value={status} onChange={(v) => set('status', v)} options={[
        ['activa', 'Activas'], ['convertida', 'Convertidas'], ['cancelada', 'Canceladas'], ['expirada', 'Vencidas'], ['', 'Todas']
      ]} />
      {isLoading && <Spinner />}
      {error && <ErrorBox error={error} onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <Empty>No hay reservas en esta categoría.</Empty>}
      {data && data.items.length > 0 && (
        <section className="card table-card">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Vehículo</th><th>Cliente</th><th>Creada</th><th>Vence</th><th>Estado</th><th></th></tr></thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <VehicleCell v={r.vehicle} />
                    <td>{r.user.full_name}<div className="muted small">{r.user.email}</div></td>
                    <td>{fmtDate(r.created_at)}</td>
                    <td>{r.status === 'activa' ? <strong>{fmtRemaining(r.expires_at)}</strong> : fmtDate(r.expires_at)}</td>
                    <td><StatusBadge status={r.status} /></td>
                    <td className="actions">
                      {r.status === 'activa' && (
                        <ConfirmButton label="Cancelar" tone="danger" confirmLabel="¿Cancelar reserva?"
                          onConfirm={() => act(() => endpoints.cancelReservation(r.id), 'Reserva cancelada; el vehículo está disponible')} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={data.total} pageSize={20} onChange={(p) => set('page', String(p))} />
        </section>
      )}
    </div>
  )
}

// ======================= Órdenes =======================
export function OrdersPage(): React.JSX.Element {
  const [page, status, set] = usePageParam()
  const act = useAction()
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['orders', status, page],
    queryFn: () => endpoints.orders(status as OrderStatus | '', page),
    placeholderData: keepPreviousData
  })

  return (
    <div>
      <PageHeader title="Órdenes de compra"
        subtitle="Compras simuladas de la página web. Confirma la venta cuando el pago simulado esté aprobado." />
      <StatusTabs value={status} onChange={(v) => set('status', v)} options={[
        ['pagada', 'Por confirmar'], ['pendiente', 'Pendientes de pago'], ['confirmada', 'Confirmadas'], ['cancelada', 'Canceladas'], ['', 'Todas']
      ]} />
      {isLoading && <Spinner />}
      {error && <ErrorBox error={error} onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <Empty>No hay órdenes en esta categoría.</Empty>}
      {data && data.items.length > 0 && (
        <section className="card table-card">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Vehículo</th><th>Cliente</th><th className="num">Total</th><th>Pagos simulados</th><th>Creada</th><th>Estado</th><th></th></tr></thead>
              <tbody>
                {data.items.map((o) => (
                  <tr key={o.id}>
                    <VehicleCell v={o.vehicle} />
                    <td>{o.user.full_name}<div className="muted small">{o.user.email}</div></td>
                    <td className="num strong">{fmtMoney(o.total_mxn)}</td>
                    <td>
                      {o.payments.length === 0 ? <span className="muted">Sin pagos</span> : o.payments.map((p) => (
                        <div key={p.id} className="small"><StatusBadge status={p.status} /> <span className="mono">{p.reference}</span></div>
                      ))}
                    </td>
                    <td>{fmtDate(o.created_at)}</td>
                    <td><StatusBadge status={o.status} /></td>
                    <td className="actions">
                      {o.status === 'pagada' && (
                        <ConfirmButton label="Confirmar venta" confirmLabel="¿Marcar como vendido?"
                          onConfirm={() => act(() => endpoints.confirmSale(o.id), 'Venta confirmada; la web ya lo muestra como vendido')} />
                      )}
                      {(o.status === 'pendiente' || o.status === 'pagada') && (
                        <ConfirmButton label="Cancelar" tone="danger" confirmLabel="¿Cancelar orden?"
                          onConfirm={() => act(() => endpoints.cancelOrder(o.id), 'Orden cancelada; el vehículo está disponible')} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={data.total} pageSize={20} onChange={(p) => set('page', String(p))} />
        </section>
      )}
    </div>
  )
}

// ======================= Ventas =======================
export function SalesPage(): React.JSX.Element {
  const [page, , set] = usePageParam()
  const { data, error, isLoading, refetch } = useQuery({
    queryKey: ['sales', page], queryFn: () => endpoints.sales(page), placeholderData: keepPreviousData
  })
  const dashboard = useQuery({ queryKey: ['dashboard'], queryFn: endpoints.dashboard })

  return (
    <div>
      <PageHeader title="Ventas" subtitle={dashboard.data
        ? `${dashboard.data.sales.total} ventas confirmadas · ${fmtMoney(dashboard.data.sales.revenue_mxn)} en total`
        : ' '} />
      {isLoading && <Spinner />}
      {error && <ErrorBox error={error} onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <Empty>Todavía no hay ventas confirmadas.</Empty>}
      {data && data.items.length > 0 && (
        <section className="card table-card">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Vehículo</th><th>Comprador</th><th className="num">Precio de venta</th><th>Fecha</th></tr></thead>
              <tbody>
                {data.items.map((s) => (
                  <tr key={s.id}>
                    {s.vehicle ? <VehicleCell v={s.vehicle} /> : <td>—</td>}
                    <td>{s.buyer?.full_name}<div className="muted small">{s.buyer?.email}</div></td>
                    <td className="num strong">{fmtMoney(s.sale_price_mxn)}</td>
                    <td>{fmtDate(s.sold_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={data.total} pageSize={20} onChange={(p) => set('page', String(p))} />
        </section>
      )}
    </div>
  )
}
