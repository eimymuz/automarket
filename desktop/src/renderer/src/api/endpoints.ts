// Una función por endpoint: las pantallas nunca construyen URLs a mano.
import { api } from './client'
import type {
  Brand, Dashboard, HistoryEntry, Order, OrderStatus, Page, Reservation, ReservationStatus, Sale,
  Source, TokenOut, User, Vehicle, VehicleInput
} from './types'

export interface VehicleFilters {
  q?: string
  brand?: string
  status?: string
  body_type?: string
  transmission?: string
  fuel_type?: string
  year_min?: number | ''
  year_max?: number | ''
  price_min?: number | ''
  price_max?: number | ''
  sort?: string
  page?: number
  page_size?: number
}

export const endpoints = {
  health: () => api<{ api: string; version: string; database: { status: string; version?: string } }>('GET', '/health'),

  login: (email: string, password: string) => api<TokenOut>('POST', '/auth/login', { body: { email, password } }),
  me: () => api<User>('GET', '/auth/me'),

  dashboard: () => api<Dashboard>('GET', '/stats/dashboard'),
  brands: () => api<Brand[]>('GET', '/brands'),

  vehicles: (f: VehicleFilters) => api<Page<Vehicle>>('GET', '/vehicles', { query: { ...f } }),
  vehicle: (id: string) => api<Vehicle>('GET', `/vehicles/${id}`),
  createVehicle: (data: VehicleInput) => api<Vehicle>('POST', '/vehicles', { body: data }),
  updateVehicle: (id: string, data: Partial<VehicleInput> & { row_version: number }) =>
    api<Vehicle>('PATCH', `/vehicles/${id}`, { body: data }),
  deleteVehicle: (id: string) => api<void>('DELETE', `/vehicles/${id}`),
  vehicleHistory: (id: string) => api<HistoryEntry[]>('GET', `/vehicles/${id}/history`),
  uploadImage: (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api<Vehicle>('POST', `/vehicles/${id}/images`, { form })
  },
  setPrimaryImage: (id: string, imageId: number) => api<Vehicle>('POST', `/vehicles/${id}/images/${imageId}/primary`),
  deleteImage: (id: string, imageId: number) => api<Vehicle>('DELETE', `/vehicles/${id}/images/${imageId}`),

  reservations: (status: ReservationStatus | '', page: number) =>
    api<Page<Reservation>>('GET', '/reservations', { query: { status, page, page_size: 20 } }),
  cancelReservation: (id: string) => api<Reservation>('POST', `/reservations/${id}/cancel`),

  orders: (status: OrderStatus | '', page: number) =>
    api<Page<Order>>('GET', '/orders', { query: { status, page, page_size: 20 } }),
  confirmSale: (id: string) => api<Order>('POST', `/orders/${id}/confirm`),
  cancelOrder: (id: string) => api<Order>('POST', `/orders/${id}/cancel`),

  sales: (page: number) => api<Page<Sale>>('GET', '/sales', { query: { page, page_size: 20 } }),
  history: (f: { operation?: string; source?: Source | ''; page: number }) =>
    api<Page<HistoryEntry>>('GET', '/history', { query: { ...f, page_size: 50 } })
}
