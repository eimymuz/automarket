import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { endpoints } from '../api/endpoints'
import { PageHeader } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useRealtime } from '../context/RealtimeContext'

/** Cambiar el servidor: localhost, una IP de la red local o un dominio en internet. */
export function ServerSettings({ compact = false }: { compact?: boolean }): React.JSX.Element {
  const { apiUrl, setApiUrl } = useAuth()
  const [value, setValue] = useState(apiUrl)
  const [message, setMessage] = useState<{ tone: string; text: string } | null>(null)

  const test = async (url: string): Promise<boolean> => {
    try {
      const r = await fetch(`${new URL(url).origin}/api/v1/health`)
      const body = await r.json()
      setMessage({ tone: body.database?.status === 'ok' ? 'good' : 'warning',
        text: `Servidor ${body.version} · base de datos: ${body.database?.status}` })
      return true
    } catch {
      setMessage({ tone: 'critical', text: 'No responde. Verifica la dirección y que el backend esté encendido.' })
      return false
    }
  }

  const save = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    try {
      if (await test(value)) {
        await setApiUrl(value)
        setMessage({ tone: 'good', text: 'Servidor guardado.' })
      }
    } catch (err) {
      setMessage({ tone: 'critical', text: err instanceof Error ? err.message : 'URL inválida' })
    }
  }

  return (
    <form className={compact ? 'server-form compact' : 'server-form'} onSubmit={save}>
      <label className="field">
        <span>URL del servidor AutoMarket</span>
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="http://192.168.1.50:8000" />
      </label>
      <div className="row-gap">
        <button type="button" className="btn btn-ghost" onClick={() => test(value)}>Probar conexión</button>
        <button className="btn btn-primary">Guardar</button>
      </div>
      {message && <div className={`alert alert-${message.tone}`}>{message.text}</div>}
    </form>
  )
}

export function SettingsPage(): React.JSX.Element {
  const { appVersion, user } = useAuth()
  const { status } = useRealtime()
  const health = useQuery({ queryKey: ['health'], queryFn: endpoints.health, refetchInterval: 30_000 })

  return (
    <div>
      <PageHeader title="Configuración" />
      <div className="grid-2">
        <section className="card">
          <div className="card-head"><h2>Servidor</h2></div>
          <p className="muted small">
            AutoMarket.exe y la página web comparten este backend. Cámbialo para trabajar en la red local o con un servidor en internet.
          </p>
          <ServerSettings />
        </section>
        <section className="card">
          <div className="card-head"><h2>Estado</h2></div>
          <dl className="facts">
            <dt>API</dt><dd>{health.data ? `${health.data.api} · v${health.data.version}` : health.error ? 'sin respuesta' : '…'}</dd>
            <dt>Base de datos</dt><dd>{health.data?.database.version ?? health.data?.database.status ?? '…'}</dd>
            <dt>Tiempo real</dt><dd>{status === 'online' ? 'Conectado (WebSocket)' : status === 'connecting' ? 'Conectando…' : 'Desconectado'}</dd>
            <dt>Sesión</dt><dd>{user?.email} ({user?.role})</dd>
            <dt>Versión de la app</dt><dd>{appVersion}</dd>
          </dl>
        </section>
      </div>
    </div>
  )
}
