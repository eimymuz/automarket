// Formulario de vehículo, compartido por "Registrar" y "Editar".
import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { endpoints } from '../api/endpoints'
import type { Vehicle, VehicleInput } from '../api/types'
import { FUEL, TRANSMISSION } from '../lib/format'

const BODY_TYPES = ['Sedán', 'SUV', 'Hatchback', 'Pickup', 'Minivan', 'Convertible', 'Coupé']
const CURRENT_YEAR = new Date().getFullYear()

export function emptyVehicle(): VehicleInput {
  return {
    brand: '', model: '', body_type: 'Sedán', year: CURRENT_YEAR, version: '', price_mxn: '', mileage_km: 0,
    color: '', transmission: 'automatica', fuel_type: 'gasolina', engine: '', description: ''
  }
}

export function vehicleToInput(v: Vehicle): VehicleInput {
  return {
    brand: v.brand, model: v.model, body_type: v.body_type, year: v.year, version: v.version,
    price_mxn: String(v.price_mxn), mileage_km: v.mileage_km, color: v.color, transmission: v.transmission,
    fuel_type: v.fuel_type, engine: v.engine, description: v.description ?? ''
  }
}

/** Validación en el cliente (la API vuelve a validar todo; esto solo da respuesta inmediata). */
function validate(v: VehicleInput, editing: boolean): Record<string, string> {
  const e: Record<string, string> = {}
  if (!editing && v.brand.trim().length < 2) e.brand = 'Indica la marca'
  if (!editing && !v.model.trim()) e.model = 'Indica el modelo'
  if (!v.version.trim()) e.version = 'Indica la versión'
  if (v.year < 1990 || v.year > CURRENT_YEAR + 1) e.year = `Entre 1990 y ${CURRENT_YEAR + 1}`
  const price = Number(v.price_mxn)
  if (!Number.isFinite(price) || price <= 0) e.price_mxn = 'Precio mayor a 0'
  if (v.mileage_km < 0) e.mileage_km = 'No puede ser negativo'
  if (v.color.trim().length < 2) e.color = 'Indica el color'
  if (v.engine.trim().length < 2) e.engine = 'Describe el motor (p. ej. 2.0L 150 hp)'
  return e
}

export function VehicleForm({ initial, editing = false, disabled = false, submitLabel, onSubmit, serverErrors = {} }: {
  initial: VehicleInput
  editing?: boolean
  disabled?: boolean
  submitLabel: string
  onSubmit: (data: VehicleInput) => Promise<void>
  serverErrors?: Record<string, string>
}): React.JSX.Element {
  const [values, setValues] = useState<VehicleInput>(initial)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const brands = useQuery({ queryKey: ['brands'], queryFn: endpoints.brands, enabled: !editing })
  const allErrors = { ...serverErrors, ...errors }

  const set = <K extends keyof VehicleInput>(key: K, value: VehicleInput[K]): void => {
    setValues((v) => ({ ...v, [key]: value }))
    setErrors(({ [key]: _, ...rest }) => rest)
  }

  const submit = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    const found = validate(values, editing)
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      await onSubmit({ ...values, description: values.description?.trim() || null })
    } finally {
      setBusy(false)
    }
  }

  const field = (key: keyof VehicleInput, label: string, input: React.JSX.Element, wide = false): React.JSX.Element => (
    <label className={`field${wide ? ' field-wide' : ''}${allErrors[key] ? ' field-error' : ''}`}>
      <span>{label}</span>
      {input}
      {allErrors[key] && <small className="error-text">{allErrors[key]}</small>}
    </label>
  )
  const models = brands.data?.find((b) => b.name.toLowerCase() === values.brand.toLowerCase())?.models ?? []

  return (
    <form className="form-grid" onSubmit={submit} noValidate>
      <fieldset disabled={disabled || busy}>
        {field('brand', 'Marca', <>
          <input list="brand-options" value={values.brand} readOnly={editing} onChange={(e) => set('brand', e.target.value)} />
          <datalist id="brand-options">{brands.data?.map((b) => <option key={b.id} value={b.name} />)}</datalist>
        </>)}
        {field('model', 'Modelo', <>
          <input list="model-options" value={values.model} readOnly={editing} onChange={(e) => set('model', e.target.value)} />
          <datalist id="model-options">{models.map((m) => <option key={m.id} value={m.name} />)}</datalist>
        </>)}
        {field('version', 'Versión', <input value={values.version} onChange={(e) => set('version', e.target.value)} placeholder="Touring, i Sport…" />)}
        {field('year', 'Año', <input type="number" value={values.year} onChange={(e) => set('year', Number(e.target.value))} />)}
        {field('price_mxn', 'Precio (MXN)', <input type="number" min={1} step="0.01" value={values.price_mxn} onChange={(e) => set('price_mxn', e.target.value)} />)}
        {field('mileage_km', 'Kilometraje', <input type="number" min={0} value={values.mileage_km} onChange={(e) => set('mileage_km', Number(e.target.value))} />)}
        {field('color', 'Color', <input value={values.color} onChange={(e) => set('color', e.target.value)} />)}
        {field('engine', 'Motor', <input value={values.engine} onChange={(e) => set('engine', e.target.value)} placeholder="1.5L Turbo 4 cil. 188 hp" />)}
        {field('transmission', 'Transmisión', (
          <select value={values.transmission} onChange={(e) => set('transmission', e.target.value as VehicleInput['transmission'])}>
            {Object.entries(TRANSMISSION).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        ))}
        {field('fuel_type', 'Combustible', (
          <select value={values.fuel_type} onChange={(e) => set('fuel_type', e.target.value as VehicleInput['fuel_type'])}>
            {Object.entries(FUEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        ))}
        {!editing && field('body_type', 'Carrocería', (
          <select value={values.body_type ?? ''} onChange={(e) => set('body_type', e.target.value)}>
            {BODY_TYPES.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        ))}
        {field('description', 'Descripción', (
          <textarea rows={4} value={values.description ?? ''} onChange={(e) => set('description', e.target.value)} />
        ), true)}
        <div className="form-actions">
          <button className="btn btn-primary" type="submit">{busy ? 'Guardando…' : submitLabel}</button>
        </div>
      </fieldset>
    </form>
  )
}
