import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { endpoints } from '../api/endpoints'
import { ChartCard, Empty, ErrorBox, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { fmtMoney, fmtNumber, fmtRelative, opLabel, SOURCE } from '../lib/format'

// Serie única -> un solo color: slot 1 de la paleta categórica validada
const SERIES_1 = '#2a78d6'
const AXIS = { stroke: '#c3c2b7', tick: { fill: '#898781', fontSize: 12 }, tickLine: false }

function Tile({ label, value, hint, to, highlight }: {
  label: string; value: string; hint?: string; to?: string; highlight?: boolean
}): React.JSX.Element {
  const body = (
    <>
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
      {hint && <span className="tile-hint">{hint}</span>}
    </>
  )
  return to
    ? <Link to={to} className={`tile tile-link${highlight ? ' tile-highlight' : ''}`}>{body}</Link>
    : <div className="tile">{body}</div>
}

function ChartTooltip({ active, payload, label, money }: {
  active?: boolean; payload?: { value: number }[]; label?: string; money?: boolean
}): React.JSX.Element | null {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      <span>{money ? fmtMoney(payload[0].value) : `${fmtNumber(payload[0].value)} unidades`}</span>
    </div>
  )
}

function SimpleBars({ data, x, y, money, height = 220 }: {
  data: object[]; x: string; y: string; money?: boolean; height?: number
}): React.JSX.Element {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: money ? 16 : -8, bottom: 0 }} barCategoryGap="30%">
        <CartesianGrid vertical={false} stroke="#e1e0d9" />
        <XAxis dataKey={x} {...AXIS} interval={0} />
        <YAxis {...AXIS} axisLine={false} allowDecimals={false}
          tickFormatter={(v: number) => (money ? `$${(v / 1_000_000).toFixed(1)} M` : String(v))} />
        <Tooltip cursor={{ fill: 'rgba(42,120,214,0.08)' }} content={<ChartTooltip money={money} />} />
        <Bar dataKey={y} fill={SERIES_1} radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function DashboardPage(): React.JSX.Element {
  const { data, error, isLoading, refetch, isFetching } = useQuery({ queryKey: ['dashboard'], queryFn: endpoints.dashboard })

  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorBox error={error} onRetry={() => refetch()} />

  const s = data.vehicles.by_status
  // Etiquetas cortas para que no se encimen en el eje ("$300-450 mil" -> "300–450k")
  const ranges = data.price_ranges.map((r) => ({
    ...r, short: r.range.replace(/\$/g, '').replace(/ mil/g, 'k').replace(' M', 'M').replace('-', '–').replace(/\s/g, '')
  }))
  const toConfirm = data.orders_by_status.pagada
  const months = data.sales.monthly.map((m) => ({
    ...m, label: new Date(`${m.month}-01T12:00:00`).toLocaleDateString('es-MX', { month: 'short', year: '2-digit' })
  }))

  return (
    <div className={isFetching ? 'refreshing' : undefined}>
      <PageHeader title="Dashboard" subtitle="Resumen del inventario y de la operación, actualizado en vivo" />

      <div className="tiles">
        <Tile label="Disponibles" value={fmtNumber(s.disponible)} hint={`de ${fmtNumber(data.vehicles.total)} vehículos`}
          to="/vehiculos?status=disponible" />
        <Tile label="Reservados" value={fmtNumber(s.reservado)} hint={`${data.reservations_active} reservas activas`}
          to="/reservas" />
        <Tile label="Vendidos" value={fmtNumber(s.vendido)} to="/ventas" />
        <Tile label="Ventas por confirmar" value={fmtNumber(toConfirm)} hint="órdenes con pago aprobado"
          to="/ordenes?status=pagada" highlight={toConfirm > 0} />
        <Tile label="Valor del inventario" value={fmtMoney(data.vehicles.inventory_value_mxn)}
          hint="disponibles + reservados" />
        <Tile label="Ingresos (30 días)" value={fmtMoney(data.sales.revenue_last_30_days_mxn)}
          hint={`${data.sales.last_30_days} ventas · ${fmtMoney(data.sales.revenue_mxn)} histórico`} />
      </div>

      <div className="grid-2">
        <ChartCard title="Inventario por carrocería" subtitle="Unidades activas"
          chart={<SimpleBars data={data.by_body_type} x="body_type" y="total" />}
          table={
            <table className="table"><thead><tr><th>Carrocería</th><th className="num">Unidades</th></tr></thead>
              <tbody>{data.by_body_type.map((r) => (
                <tr key={r.body_type}><td>{r.body_type}</td><td className="num">{r.total}</td></tr>
              ))}</tbody></table>
          } />
        <ChartCard title="Rangos de precio" subtitle="Unidades activas por precio de lista (MXN)"
          chart={<SimpleBars data={ranges} x="short" y="total" />}
          table={
            <table className="table"><thead><tr><th>Rango</th><th className="num">Unidades</th></tr></thead>
              <tbody>{data.price_ranges.map((r) => (
                <tr key={r.range}><td>{r.range}</td><td className="num">{r.total}</td></tr>
              ))}</tbody></table>
          } />
      </div>

      <div className="grid-2">
        <ChartCard title="Ingresos por mes" subtitle="Ventas confirmadas, últimos 12 meses"
          chart={months.length
            ? <SimpleBars data={months} x="label" y="revenue_mxn" money />
            : <Empty>Aún no hay ventas confirmadas.</Empty>}
          table={
            <table className="table"><thead><tr><th>Mes</th><th className="num">Ventas</th><th className="num">Ingresos</th></tr></thead>
              <tbody>{months.map((m) => (
                <tr key={m.month}><td>{m.label}</td><td className="num">{m.total}</td><td className="num">{fmtMoney(m.revenue_mxn)}</td></tr>
              ))}</tbody></table>
          } />

        <section className="card">
          <div className="card-head"><h2>Por marca</h2></div>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Marca</th><th className="num">Unidades</th><th className="num">Disponibles</th><th className="num">Precio promedio</th></tr></thead>
              <tbody>{data.by_brand.map((b) => (
                <tr key={b.brand}>
                  <td><Link to={`/vehiculos?brand=${encodeURIComponent(b.brand)}`}>{b.brand}</Link></td>
                  <td className="num">{b.total}</td><td className="num">{b.available}</td>
                  <td className="num">{fmtMoney(b.avg_price_mxn)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-head"><h2>Actividad reciente</h2><Link to="/historial" className="small">Ver historial</Link></div>
        <ul className="activity">
          {data.recent_activity.map((a) => (
            <li key={a.id}>
              <span className={`source-pill source-${a.source}`}>{SOURCE[a.source] ?? a.source}</span>
              <span className="activity-op">{opLabel(a.operation)}</span>
              {a.stock_number && a.vehicle_id && <Link to={`/vehiculos/${a.vehicle_id}`}>{a.stock_number}</Link>}
              {a.to_status && <StatusBadge status={a.to_status} />}
              <span className="muted small activity-when">{a.actor ? `${a.actor} · ` : ''}{fmtRelative(a.created_at)}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
