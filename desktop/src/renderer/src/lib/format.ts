// Formatos y etiquetas en español para toda la interfaz.

const money = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 })
const number = new Intl.NumberFormat('es-MX')
const dateTime = new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' })

export const fmtMoney = (v: number | null | undefined): string => (v == null ? '—' : money.format(v))
export const fmtNumber = (v: number): string => number.format(v)
export const fmtKm = (v: number): string => (v === 0 ? 'Nuevo · 0 km' : `${number.format(v)} km`)
export const fmtDate = (iso: string | null | undefined): string => (iso ? dateTime.format(new Date(iso)) : '—')

export function fmtRelative(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'hace un momento'
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`
  return fmtDate(iso)
}

export function fmtRemaining(iso: string): string {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000
  if (diff <= 0) return 'vencida'
  const h = Math.floor(diff / 3600)
  const m = Math.floor((diff % 3600) / 60)
  return h > 0 ? `${h} h ${m} min` : `${m} min`
}

export const TRANSMISSION: Record<string, string> = { manual: 'Manual', automatica: 'Automática', cvt: 'CVT' }
export const FUEL: Record<string, string> = {
  gasolina: 'Gasolina', diesel: 'Diésel', hibrido: 'Híbrido', electrico: 'Eléctrico'
}
export const SOURCE: Record<string, string> = {
  desktop: 'AutoMarket.exe', web: 'Página web', sistema: 'Sistema', pipeline: 'Pipeline de datos'
}
export const DATA_KIND: Record<string, string> = {
  real: 'Catálogo oficial', referencia: 'Derivado del catálogo', prueba: 'Dato de prueba'
}

export const OPERATION: Record<string, string> = {
  carga_inicial: 'Carga inicial',
  vehiculo_registrado: 'Vehículo registrado',
  vehiculo_actualizado: 'Vehículo actualizado',
  precio_actualizado: 'Precio actualizado',
  vehiculo_eliminado: 'Vehículo eliminado',
  foto_agregada: 'Foto agregada',
  foto_principal: 'Foto principal cambiada',
  foto_eliminada: 'Foto eliminada',
  reserva_creada: 'Reserva creada',
  reserva_cancelada: 'Reserva cancelada',
  reserva_expirada: 'Reserva vencida',
  orden_creada: 'Orden de compra',
  pago_aprobado: 'Pago aprobado',
  pago_rechazado: 'Pago rechazado',
  orden_cancelada: 'Orden cancelada',
  venta_confirmada: 'Venta confirmada'
}

export const opLabel = (op: string): string => OPERATION[op] ?? op

const FIELD: Record<string, string> = {
  price_mxn: 'Precio', mileage_km: 'Kilometraje', year: 'Año', version: 'Versión', color: 'Color',
  transmission: 'Transmisión', fuel_type: 'Combustible', engine: 'Motor', description: 'Descripción'
}
export const fieldLabel = (field: string): string => FIELD[field] ?? field

export function fieldValue(field: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (field === 'price_mxn') return fmtMoney(Number(value))
  if (field === 'mileage_km') return `${fmtNumber(Number(value))} km`
  if (field === 'transmission') return TRANSMISSION[String(value)] ?? String(value)
  if (field === 'fuel_type') return FUEL[String(value)] ?? String(value)
  const text = String(value)
  return text.length > 60 ? `${text.slice(0, 57)}…` : text
}
