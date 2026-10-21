import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { endpoints } from '../api/endpoints'
import type { Source } from '../api/types'
import { Empty, ErrorBox, PageHeader, Pagination, Spinner, StatusBadge } from '../components/ui'
import { fieldLabel, fieldValue, fmtDate, fmtMoney, OPERATION, opLabel, SOURCE } from '../lib/format'

export function HistoryPage(): React.JSX.Element {
  const [params, setParams] = useSearchParams()
  const page = Number(params.get('page') ?? 1)
  const operation = params.get('operation') ?? ''
  const source = (params.get('source') ?? '') as Source | ''

  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['history', operation, source, page],
    queryFn: () => endpoints.history({ operation, source, page }),
    placeholderData: keepPreviousData
  })

  const set = (key: string, value: string): void => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  return (
    <div>
      <PageHeader title="Historial de operaciones"
        subtitle="Todo lo que ocurre en el inventario, venga de AutoMarket.exe, de la página web o del sistema." />
      <div className="filters card">
        <label className="filter">
          <span>Operación</span>
          <select value={operation} onChange={(e) => set('operation', e.target.value)}>
            <option value="">Todas</option>
            {Object.entries(OPERATION).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="filter">
          <span>Origen</span>
          <select value={source} onChange={(e) => set('source', e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(SOURCE).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>

      {isLoading && <Spinner />}
      {error && <ErrorBox error={error} onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <Empty>No hay operaciones con esos filtros.</Empty>}
      {data && data.items.length > 0 && (
        <section className={`card table-card${isFetching ? ' refreshing' : ''}`}>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Fecha</th><th>Operación</th><th>Origen</th><th>Vehículo</th><th>Cambio de estado</th><th>Detalle</th></tr></thead>
              <tbody>
                {data.items.map((h) => (
                  <tr key={h.id}>
                    <td className="nowrap">{fmtDate(h.created_at)}</td>
                    <td><strong>{opLabel(h.operation)}</strong>{h.actor_name && <div className="muted small">{h.actor_name}</div>}</td>
                    <td><span className={`source-pill source-${h.source}`}>{SOURCE[h.source]}</span></td>
                    <td>{h.vehicle_id ? (
                      <Link to={`/vehiculos/${h.vehicle_id}`} className="mono">{h.stock_number ?? 'Ver vehículo'}</Link>
                    ) : '—'}</td>
                    <td>{h.to_status ? (
                      <span className="transition">
                        {h.from_status && h.from_status !== h.to_status && <><StatusBadge status={h.from_status} /> →</>}
                        <StatusBadge status={h.to_status} />
                      </span>
                    ) : '—'}</td>
                    <td className="small muted">{summary(h.details)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={data.total} pageSize={50} onChange={(p) => set('page', String(p))} />
        </section>
      )}
    </div>
  )
}

function summary(details: Record<string, unknown> | null): string {
  if (!details) return ''
  const changes = details.cambios as Record<string, { antes: unknown; despues: unknown }> | undefined
  if (changes) return Object.entries(changes).map(([k, c]) => `${fieldLabel(k)}: ${fieldValue(k, c.antes)} → ${fieldValue(k, c.despues)}`).join(' · ')
  const parts: string[] = []
  if (details.cliente) parts.push(String(details.cliente))
  for (const k of ['total_mxn', 'precio_mxn', 'monto_mxn']) if (typeof details[k] === 'number') parts.push(fmtMoney(details[k] as number))
  if (details.reference) parts.push(String(details.reference))
  if (details.data_kind) parts.push(String(details.data_kind))
  return parts.join(' · ')
}
