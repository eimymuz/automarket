import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { mediaUrl } from '../api/client'
import { endpoints, type VehicleFilters } from '../api/endpoints'
import { Icon } from '../components/Icon'
import { Empty, ErrorBox, PageHeader, Pagination, Spinner, StatusBadge } from '../components/ui'
import { FUEL, fmtKm, fmtMoney, TRANSMISSION } from '../lib/format'

const PAGE_SIZE = 25
const FILTER_KEYS = ['q', 'brand', 'status', 'body_type', 'transmission', 'fuel_type', 'year_min', 'year_max',
  'price_min', 'price_max', 'sort'] as const

export function VehiclesPage(): React.JSX.Element {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const page = Number(params.get('page') ?? 1)
  const [search, setSearch] = useState(params.get('q') ?? '')

  const filters: VehicleFilters = { page, page_size: PAGE_SIZE }
  for (const key of FILTER_KEYS) {
    const value = params.get(key)
    if (value) (filters as Record<string, unknown>)[key] = value
  }

  const brands = useQuery({ queryKey: ['brands'], queryFn: endpoints.brands })
  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['vehicles', filters], queryFn: () => endpoints.vehicles(filters), placeholderData: keepPreviousData
  })

  const setFilter = (key: string, value: string): void => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  // Búsqueda con retardo: no se consulta la API en cada tecla
  useEffect(() => {
    const t = setTimeout(() => { if (search !== (params.get('q') ?? '')) setFilter('q', search) }, 350)
    return () => clearTimeout(t)
  }) // eslint-disable-line react-hooks/exhaustive-deps

  const bodyTypes = [...new Set(brands.data?.flatMap((b) => b.models.map((m) => m.body_type)).filter(Boolean))] as string[]
  const select = (key: string, label: string, options: [string, string][]): React.JSX.Element => (
    <label className="filter">
      <span>{label}</span>
      <select value={params.get(key) ?? ''} onChange={(e) => setFilter(key, e.target.value)}>
        <option value="">Todos</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  )
  const numberInput = (key: string, label: string, placeholder: string): React.JSX.Element => (
    <label className="filter filter-num">
      <span>{label}</span>
      <input type="number" min={0} placeholder={placeholder} defaultValue={params.get(key) ?? ''}
        key={params.get(key) ?? ''} // se reinicia al limpiar filtros
        onBlur={(e) => setFilter(key, e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && setFilter(key, (e.target as HTMLInputElement).value)} />
    </label>
  )
  const hasFilters = FILTER_KEYS.some((k) => k !== 'sort' && params.get(k))

  return (
    <div>
      <PageHeader title="Inventario"
        subtitle={data ? `${data.total} vehículos${hasFilters ? ' con los filtros aplicados' : ''}` : ' '}
        actions={<Link to="/vehiculos/nuevo" className="btn btn-primary"><Icon name="plus" /> Registrar vehículo</Link>} />

      <div className="filters card">
        <label className="filter filter-search">
          <span>Buscar</span>
          <div className="input-icon">
            <Icon name="search" size={16} />
            <input placeholder="Marca, modelo, versión, color o folio" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        </label>
        {select('brand', 'Marca', (brands.data ?? []).map((b) => [b.name, b.name]))}
        {select('status', 'Estado', [['disponible', 'Disponible'], ['reservado', 'Reservado'], ['vendido', 'Vendido']])}
        {select('body_type', 'Carrocería', bodyTypes.sort().map((b) => [b, b]))}
        {select('transmission', 'Transmisión', Object.entries(TRANSMISSION))}
        {select('fuel_type', 'Combustible', Object.entries(FUEL))}
        {numberInput('year_min', 'Año desde', 'Cualquiera')}
        {numberInput('price_max', 'Precio máx.', 'Sin límite')}
        <label className="filter">
          <span>Ordenar</span>
          <select value={params.get('sort') ?? 'newest'} onChange={(e) => setFilter('sort', e.target.value)}>
            <option value="newest">Más recientes</option>
            <option value="price_asc">Precio: menor a mayor</option>
            <option value="price_desc">Precio: mayor a menor</option>
            <option value="year_desc">Año: más nuevo</option>
            <option value="mileage_asc">Menor kilometraje</option>
          </select>
        </label>
        {hasFilters && (
          <button className="btn btn-ghost filter-clear" onClick={() => { setSearch(''); setParams({}) }}>
            <Icon name="x" size={15} /> Limpiar
          </button>
        )}
      </div>

      {isLoading && <Spinner />}
      {error && <ErrorBox error={error} onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <Empty>No hay vehículos con esos filtros.</Empty>}
      {data && data.items.length > 0 && (
        <section className={`card table-card${isFetching ? ' refreshing' : ''}`}>
          <div className="table-wrap">
            <table className="table table-hover">
              <thead>
                <tr>
                  <th></th><th>Folio</th><th>Vehículo</th><th className="num">Año</th><th className="num">Kilometraje</th>
                  <th>Transmisión</th><th>Color</th><th className="num">Precio</th><th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((v) => (
                  <tr key={v.id} onClick={() => navigate(`/vehiculos/${v.id}`)} tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && navigate(`/vehiculos/${v.id}`)}>
                    <td className="thumb-cell">
                      {v.primary_image ? <img className="thumb" src={mediaUrl(v.primary_image)!} alt="" loading="lazy" />
                        : <span className="thumb thumb-empty"><Icon name="car" size={16} /></span>}
                    </td>
                    <td className="mono">{v.stock_number}</td>
                    <td><strong>{v.brand} {v.model}</strong><div className="muted small">{v.version} · {v.engine}</div></td>
                    <td className="num">{v.year}</td>
                    <td className="num">{fmtKm(v.mileage_km)}</td>
                    <td>{TRANSMISSION[v.transmission]}</td>
                    <td>{v.color}</td>
                    <td className="num strong">{fmtMoney(v.price_mxn)}</td>
                    <td><StatusBadge status={v.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} total={data.total} pageSize={PAGE_SIZE} onChange={(p) => setFilter('page', String(p))} />
        </section>
      )}
    </div>
  )
}
