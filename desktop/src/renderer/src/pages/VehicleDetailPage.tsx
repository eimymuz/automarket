import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError, mediaUrl } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { Vehicle } from '../api/types'
import { Icon } from '../components/Icon'
import { VehicleForm, vehicleToInput } from '../components/VehicleForm'
import { ConfirmButton, ErrorBox, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { useRealtimeEvent } from '../context/RealtimeContext'
import { useToast } from '../context/ToastContext'
import { DATA_KIND, fieldLabel, fieldValue, fmtDate, fmtMoney, opLabel, SOURCE } from '../lib/format'

export function VehicleDetailPage(): React.JSX.Element {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [formKey, setFormKey] = useState(0) // cambiarlo reinicia el formulario con los datos del servidor
  const [remoteChange, setRemoteChange] = useState<string | null>(null)
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({})
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  // Evita confundir el evento de NUESTRO propio guardado (que puede llegar antes que la respuesta HTTP)
  // con un cambio hecho por otra persona.
  const saving = useRef(false)
  const ownVersion = useRef(0)

  const vehicle = useQuery({ queryKey: ['vehicle', id], queryFn: () => endpoints.vehicle(id) })
  const history = useQuery({ queryKey: ['vehicle-history', id], queryFn: () => endpoints.vehicleHistory(id) })

  // Si alguien más modifica este vehículo mientras está abierto, se avisa en lugar de pisar los cambios
  useRealtimeEvent((event) => {
    const target = event.data.vehicle_id ?? event.data.id
    if (target !== id || !event.type.startsWith('vehicle.')) return
    const version = Number(event.data.row_version)
    if (saving.current || version <= Math.max(ownVersion.current, vehicle.data?.row_version ?? 0)) return
    if (event.type === 'vehicle.status_changed') {
      setRemoteChange(`El estado cambió a "${event.data.status}" (${String(event.data.reason ?? '').replace('_', ' ')}).`)
    } else if (event.type === 'vehicle.updated') {
      setRemoteChange('Otro usuario modificó este vehículo. Recarga los datos antes de guardar.')
    }
  })

  const refresh = (v?: Vehicle): void => {
    if (v) queryClient.setQueryData(['vehicle', id], v)
    queryClient.invalidateQueries({ queryKey: ['vehicle', id] })
    queryClient.invalidateQueries({ queryKey: ['vehicle-history', id] })
    queryClient.invalidateQueries({ queryKey: ['vehicles'] })
  }

  const run = async (action: () => Promise<Vehicle | void>, success: string): Promise<void> => {
    try {
      const result = await action()
      refresh(result || undefined)
      toast('success', success)
    } catch (e) {
      toast('error', 'No se pudo completar', e instanceof ApiError ? e.message : String(e))
    }
  }

  if (vehicle.isLoading) return <Spinner />
  if (vehicle.error || !vehicle.data) return <ErrorBox error={vehicle.error} onRetry={() => vehicle.refetch()} />
  const v = vehicle.data
  const sold = v.status === 'vendido'
  const primary = mediaUrl(v.primary_image)

  return (
    <div>
      <PageHeader
        title={`${v.brand} ${v.model} ${v.version}`}
        subtitle={<><span className="mono">{v.stock_number}</span> · {v.year} · <StatusBadge status={v.status} /></>}
        actions={<>
          <Link to="/vehiculos" className="btn btn-ghost"><Icon name="back" /> Inventario</Link>
          <ConfirmButton label="Eliminar" icon="trash" tone="danger" confirmLabel="¿Dar de baja este vehículo?"
            disabled={v.status !== 'disponible'}
            onConfirm={() => run(async () => {
              await endpoints.deleteVehicle(v.id)
              navigate('/vehiculos')
            }, 'Vehículo dado de baja')} />
        </>} />

      {remoteChange && (
        <div className="alert alert-warning">
          <span>{remoteChange}</span>
          <button className="btn btn-ghost btn-sm" onClick={async () => {
            await vehicle.refetch()
            setFormKey((k) => k + 1)
            setRemoteChange(null)
          }}><Icon name="refresh" size={15} /> Recargar datos</button>
        </div>
      )}
      {v.status !== 'disponible' && (
        <div className="alert alert-info">
          {sold ? 'Vehículo vendido: ya no se puede editar ni eliminar.'
            : 'Vehículo reservado o con una orden en proceso: no se puede eliminar hasta que se libere.'}
        </div>
      )}

      <div className="detail-grid">
        <section className="card">
          <div className="card-head">
            <h2>Fotografías</h2>
            <button className="btn btn-ghost btn-sm" disabled={uploading || sold} onClick={() => fileInput.current?.click()}>
              <Icon name="upload" size={15} /> {uploading ? 'Subiendo…' : 'Subir foto'}
            </button>
            <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" hidden multiple
              onChange={async (e) => {
                const files = [...(e.target.files ?? [])]
                e.target.value = ''
                setUploading(true)
                for (const file of files) await run(() => endpoints.uploadImage(v.id, file), `Foto "${file.name}" subida`)
                setUploading(false)
              }} />
          </div>
          {primary
            ? <img className="hero-photo" src={primary} alt={`${v.brand} ${v.model}`} />
            : <div className="hero-photo hero-empty"><Icon name="car" size={40} /><span>Sin fotografías</span></div>}
          {v.images.length > 0 && (
            <div className="thumbs">
              {v.images.map((img) => (
                <figure key={img.id} className={`thumb-item${img.is_primary ? ' is-primary' : ''}`}>
                  <img src={mediaUrl(img.url)!} alt="" />
                  <figcaption>
                    {img.is_primary ? <span className="small strong">Principal</span> : (
                      <button className="icon-btn" title="Usar como principal" disabled={sold}
                        onClick={() => run(() => endpoints.setPrimaryImage(v.id, img.id), 'Foto principal actualizada')}>
                        <Icon name="star" size={14} />
                      </button>
                    )}
                    <button className="icon-btn icon-danger" title="Eliminar foto" disabled={sold}
                      onClick={() => run(() => endpoints.deleteImage(v.id, img.id), 'Foto eliminada')}>
                      <Icon name="trash" size={14} />
                    </button>
                  </figcaption>
                </figure>
              ))}
            </div>
          )}
          <dl className="facts">
            <dt>Precio</dt><dd className="strong">{fmtMoney(v.price_mxn)}</dd>
            <dt>Procedencia</dt><dd>{v.data_source ? `${DATA_KIND[v.data_source.kind]} · ${v.data_source.name}` : 'Registro manual'}</dd>
            <dt>Registrado</dt><dd>{fmtDate(v.created_at)}</dd>
            <dt>Actualizado</dt><dd>{fmtDate(v.updated_at)}</dd>
          </dl>
        </section>

        <section className="card">
          <div className="card-head"><h2>Datos del vehículo</h2></div>
          <VehicleForm key={`${formKey}-${v.id}`} initial={vehicleToInput(v)} editing disabled={sold}
            submitLabel="Guardar cambios" serverErrors={serverErrors}
            onSubmit={async (data) => {
              setServerErrors({})
              const current = vehicleToInput(v)
              const changed = Object.fromEntries(
                Object.entries(data).filter(([k, val]) => String(val ?? '') !== String(current[k as keyof typeof current] ?? ''))
              )
              if (!Object.keys(changed).length) return toast('info', 'No hay cambios que guardar')
              saving.current = true
              try {
                const updated = await endpoints.updateVehicle(v.id, { ...changed, row_version: v.row_version })
                ownVersion.current = updated.row_version
                refresh(updated)
                setRemoteChange(null)
                toast('success', 'Cambios guardados', 'La página web ya muestra la nueva información.')
              } catch (e) {
                if (e instanceof ApiError && e.code === 'version_conflict') {
                  setRemoteChange('No se guardó: otro usuario modificó el vehículo mientras lo editabas. Recarga los datos y vuelve a aplicar tus cambios.')
                } else if (e instanceof ApiError) {
                  setServerErrors(e.fields)
                  toast('error', 'No se guardó', e.message)
                } else throw e
              } finally {
                saving.current = false
              }
            }} />
        </section>
      </div>

      <section className="card">
        <div className="card-head"><h2>Historial del vehículo</h2></div>
        {history.isLoading ? <Spinner /> : (
          <ol className="timeline">
            {history.data?.map((h) => (
              <li key={h.id}>
                <div className="timeline-head">
                  <strong>{opLabel(h.operation)}</strong>
                  <span className={`source-pill source-${h.source}`}>{SOURCE[h.source]}</span>
                  {h.to_status && <StatusBadge status={h.to_status} />}
                  <span className="muted small">{fmtDate(h.created_at)}</span>
                </div>
                {h.details && <HistoryDetails details={h.details} />}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  )
}

function HistoryDetails({ details }: { details: Record<string, unknown> }): React.JSX.Element | null {
  const changes = details.cambios as Record<string, { antes: unknown; despues: unknown }> | undefined
  if (changes) {
    return (
      <ul className="changes">
        {Object.entries(changes).map(([field, c]) => (
          <li key={field}>
            <span className="muted">{fieldLabel(field)}:</span> {fieldValue(field, c.antes)} → <strong>{fieldValue(field, c.despues)}</strong>
          </li>
        ))}
      </ul>
    )
  }
  const interesting = ['cliente', 'total_mxn', 'precio_mxn', 'monto_mxn', 'reference', 'horas', 'data_kind']
  const shown = interesting.filter((k) => details[k] !== undefined && details[k] !== null)
  if (!shown.length) return null
  return (
    <p className="muted small">
      {shown.map((k) => `${k.replace('_mxn', '')}: ${typeof details[k] === 'number' && k.endsWith('_mxn') ? fmtMoney(details[k] as number) : String(details[k])}`).join(' · ')}
    </p>
  )
}
