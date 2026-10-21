import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { Icon } from '../components/Icon'
import { useAuth } from '../context/AuthContext'
import { ServerSettings } from './SettingsPage'

export function LoginPage(): React.JSX.Element {
  const { login, logoutReason, apiUrl } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [showServer, setShowServer] = useState(false)

  const submit = async (e: FormEvent): Promise<void> => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email.trim(), password)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo iniciar sesión')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <div className="brand brand-lg">
          <span className="brand-mark"><Icon name="car" size={24} /></span>
          <span className="brand-name">AutoMarket</span>
        </div>
        <p className="muted">Panel administrativo de la agencia</p>

        {logoutReason && <div className="alert alert-warning">{logoutReason}</div>}
        {error && <div className="alert alert-critical" role="alert">{error}</div>}

        <label className="field">
          <span>Correo</span>
          <input type="email" autoComplete="username" required autoFocus value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          <span>Contraseña</span>
          <input type="password" autoComplete="current-password" required value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </label>
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Entrando…' : 'Iniciar sesión'}</button>

        <button type="button" className="link-button" onClick={() => setShowServer(!showServer)}>
          Servidor: {apiUrl} · {showServer ? 'ocultar' : 'cambiar'}
        </button>
        {showServer && <ServerSettings compact />}
      </form>
    </div>
  )
}
