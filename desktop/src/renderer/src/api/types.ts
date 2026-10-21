// Tipos de la API AutoMarket (reflejan los esquemas Pydantic del backend).

export type VehicleStatus = 'disponible' | 'reservado' | 'vendido'
export type Transmission = 'manual' | 'automatica' | 'cvt'
export type FuelType = 'gasolina' | 'diesel' | 'hibrido' | 'electrico'
export type ReservationStatus = 'activa' | 'cancelada' | 'expirada' | 'convertida'
export type OrderStatus = 'pendiente' | 'pagada' | 'confirmada' | 'cancelada'
export type PaymentMethod = 'tarjeta_simulada' | 'transferencia_simulada' | 'efectivo_simulado'
export type Source = 'desktop' | 'web' | 'sistema' | 'pipeline'

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface User {
  id: string
  email: string
  full_name: string
  phone: string | null
  role: 'admin' | 'cliente'
  is_active: boolean
  created_at: string
}

export interface TokenOut {
  access_token: string
  expires_at: string
  user: User
}

export interface VehicleImage {
  id: number
  url: string
  is_primary: boolean
  position: number
}

export interface Vehicle {
  id: string
  stock_number: string
  brand: string
  model: string
  body_type: string | null
  year: number
  version: string
  price_mxn: number
  mileage_km: number
  color: string
  transmission: Transmission
  fuel_type: FuelType
  engine: string
  description: string | null
  status: VehicleStatus
  primary_image: string | null
  images: VehicleImage[]
  data_source: { name: string; kind: 'real' | 'referencia' | 'prueba'; url: string | null } | null
  row_version: number
  created_at: string
  updated_at: string
}

export interface VehicleSummary {
  id: string
  stock_number: string
  brand: string
  model: string
  year: number
  version: string
  price_mxn: number
  status: VehicleStatus
  primary_image: string | null
}

export interface VehicleInput {
  brand: string
  model: string
  body_type: string | null
  year: number
  version: string
  price_mxn: string
  mileage_km: number
  color: string
  transmission: Transmission
  fuel_type: FuelType
  engine: string
  description: string | null
}

export interface Brand {
  id: number
  name: string
  models: { id: number; name: string; body_type: string | null; available: number }[]
}

export interface UserSummary {
  id: string
  email: string
  full_name: string
}

export interface Reservation {
  id: string
  status: ReservationStatus
  expires_at: string
  cancelled_at: string | null
  notes: string | null
  created_at: string
  vehicle: VehicleSummary
  user: UserSummary
}

export interface Payment {
  id: string
  amount_mxn: number
  method: PaymentMethod
  status: 'aprobado' | 'rechazado'
  reference: string
  created_at: string
}

export interface Sale {
  id: string
  order_id: string
  sale_price_mxn: number
  sold_at: string
  confirmed_by: string
  vehicle: VehicleSummary | null
  buyer: UserSummary | null
}

export interface Order {
  id: string
  status: OrderStatus
  total_mxn: number
  reservation_id: string | null
  created_at: string
  updated_at: string
  vehicle: VehicleSummary
  user: UserSummary
  payments: Payment[]
  sale: Sale | null
}

export interface HistoryEntry {
  id: number
  vehicle_id: string | null
  actor_user_id: string | null
  operation: string
  source: Source
  from_status: string | null
  to_status: string | null
  details: Record<string, unknown> | null
  created_at: string
  stock_number?: string | null
  actor_name?: string | null
}

export interface Dashboard {
  vehicles: { total: number; by_status: Record<VehicleStatus, number>; inventory_value_mxn: number }
  by_brand: { brand: string; total: number; available: number; avg_price_mxn: number }[]
  by_body_type: { body_type: string; total: number }[]
  price_ranges: { range: string; total: number }[]
  reservations_active: number
  orders_by_status: Record<OrderStatus, number>
  sales: {
    total: number
    revenue_mxn: number
    last_30_days: number
    revenue_last_30_days_mxn: number
    monthly: { month: string; total: number; revenue_mxn: number }[]
  }
  recent_activity: {
    id: number
    operation: string
    source: Source
    vehicle_id: string | null
    stock_number: string | null
    actor: string | null
    to_status: string | null
    created_at: string
  }[]
}

export interface RealtimeEvent {
  seq?: number
  type: string
  data: Record<string, unknown>
  occurred_at?: string
}
