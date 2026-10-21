// Conexión WebSocket con el backend: mantiene la app sincronizada con lo que pasa en la página web.
//
// Cada evento invalida solo las consultas afectadas (React Query vuelve a pedirlas), así que las
// pantallas abiertas se actualizan solas. Si se pierde la conexión, reintenta con espera creciente y
// al reconectar recarga todo, porque pudieron perderse eventos.
import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import type { RealtimeEvent } from '../api/types'
import { fmtMoney } from '../lib/format'
import { useAuth } from './AuthContext'
import { useToast } from './ToastContext'

export type LiveStatus = 'connecting' | 'online' | 'offline'
type Listener = (event: RealtimeEvent) => void

interface RealtimeState {
  status: LiveStatus
  lastEventAt: Date | null
  subscribe: (listener: Listener) => () => void
}

const RealtimeContext = createContext<RealtimeState>({ status: 'offline', lastEventAt: null, subscribe: () => () => {} })

const INVALIDATE: Record<string, string[][]> = {
  vehicle: [['vehicles'], ['dashboard'], ['brands'], ['history']],
  reservation: [['reservations'], ['dashboard'], ['history']],
  order: [['orders'], ['dashboard'], ['history']],
  sale: [['sales'], ['orders'], ['dashboard'], ['history']]
}

export function RealtimeProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const { apiUrl, token } = useAuth()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [status, setStatus] = useState<LiveStatus>('offline')
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null)
  const listeners = useRef(new Set<Listener>())

  useEffect(() => {
    if (!token || !apiUrl) return
    let ws: WebSocket | null = null
    let retry = 0
    let lastSeq: number | null = null
    let closedByUs = false
    let pingTimer: ReturnType<typeof setInterval> | undefined
    let retryTimer: ReturnType<typeof setTimeout> | undefined

    const handle = (event: RealtimeEvent): void => {
      if (event.seq !== undefined) {
        if (lastSeq !== null && event.seq !== lastSeq + 1) queryClient.invalidateQueries() // se perdieron eventos
        lastSeq = event.seq
      }
      setLastEventAt(new Date())
      const group = event.type.split('.')[0]
      for (const key of INVALIDATE[group] ?? []) queryClient.invalidateQueries({ queryKey: key })
      const vehicleId = (event.data.vehicle_id ?? (group === 'vehicle' ? event.data.id : undefined)) as string | undefined
      if (vehicleId) {
        queryClient.invalidateQueries({ queryKey: ['vehicle', vehicleId] })
        queryClient.invalidateQueries({ queryKey: ['vehicle-history', vehicleId] })
      }
      notify(event)
      listeners.current.forEach((l) => l(event))
    }

    // Avisos visibles solo para lo que el administrador debe atender (normalmente viene de la web)
    const notify = (event: RealtimeEvent): void => {
      const d = event.data
      const messages: Record<string, [string, string]> = {
        'reservation.created': ['Nueva reserva', `Vehículo ${d.stock_number ?? ''} reservado`],
        'order.created': ['Nueva solicitud de compra', `Total ${fmtMoney(d.total_mxn as number)}`],
        'order.paid': ['Pago simulado aprobado', 'Hay una venta pendiente de confirmar'],
        'reservation.expired': ['Reserva vencida', 'El vehículo volvió a estar disponible']
      }
      const msg = messages[event.type]
      if (msg) {
        toast('info', msg[0], msg[1])
        window.automarket.notify(`AutoMarket · ${msg[0]}`, msg[1])
      }
    }

    const connect = (): void => {
      setStatus('connecting')
      const url = `${apiUrl.replace(/^http/, 'ws')}/api/v1/ws?client=desktop&token=${encodeURIComponent(token)}`
      ws = new WebSocket(url)
      ws.onopen = () => {
        if (retry > 0) queryClient.invalidateQueries() // tras una caída, recarga todo
        retry = 0
        lastSeq = null
        setStatus('online')
        pingTimer = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send('ping'), 25000)
      }
      ws.onmessage = (msg) => {
        const event = JSON.parse(msg.data) as RealtimeEvent
        if (event.type !== 'connection.ready' && event.type !== 'pong') handle(event)
      }
      ws.onclose = (e) => {
        clearInterval(pingTimer)
        setStatus('offline')
        if (closedByUs || e.code === 4401) return
        retry += 1
        retryTimer = setTimeout(connect, Math.min(30000, 1000 * 2 ** Math.min(retry, 5)))
      }
    }

    connect()
    return () => {
      closedByUs = true
      clearInterval(pingTimer)
      clearTimeout(retryTimer)
      ws?.close()
    }
  }, [apiUrl, token, queryClient, toast])

  const subscribe = useCallback((listener: Listener): (() => void) => {
    listeners.current.add(listener)
    return () => listeners.current.delete(listener)
  }, [])

  return <RealtimeContext.Provider value={{ status, lastEventAt, subscribe }}>{children}</RealtimeContext.Provider>
}

export const useRealtime = (): RealtimeState => useContext(RealtimeContext)

/** Ejecuta `listener` con cada evento mientras el componente esté montado. */
export function useRealtimeEvent(listener: Listener): void {
  const { subscribe } = useRealtime()
  const ref = useRef(listener)
  ref.current = listener
  useEffect(() => subscribe((e) => ref.current(e)), [subscribe])
}
