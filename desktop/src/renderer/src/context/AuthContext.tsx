import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { ApiError, configureApi } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { User } from '../api/types'

// El token se guarda en sessionStorage: sobrevive a recargar la ventana, pero se borra al cerrar la app.
const TOKEN_KEY = 'automarket.token'

interface AuthState {
  ready: boolean
  apiUrl: string
  appVersion: string
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: (reason?: string) => void
  setApiUrl: (url: string) => Promise<void>
  logoutReason: string | null
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const [ready, setReady] = useState(false)
  const [apiUrl, setApiUrlState] = useState('')
  const [appVersion, setAppVersion] = useState('')
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [logoutReason, setLogoutReason] = useState<string | null>(null)

  const logout = useCallback((reason?: string) => {
    sessionStorage.removeItem(TOKEN_KEY)
    configureApi({ token: null })
    setToken(null)
    setUser(null)
    setLogoutReason(reason ?? null)
  }, [])

  useEffect(() => {
    configureApi({ onUnauthorized: () => logout('Tu sesión expiró. Inicia sesión de nuevo.') })
    window.automarket.getConfig().then(async (cfg) => {
      configureApi({ baseUrl: cfg.apiUrl })
      setApiUrlState(cfg.apiUrl)
      setAppVersion(cfg.appVersion)
      const saved = sessionStorage.getItem(TOKEN_KEY)
      if (saved) {
        configureApi({ token: saved })
        try {
          const me = await endpoints.me()
          if (me.role === 'admin') {
            setUser(me)
            setToken(saved)
          } else logout()
        } catch {
          logout()
        }
      }
      setReady(true)
    })
  }, [logout])

  const login = useCallback(async (email: string, password: string) => {
    const result = await endpoints.login(email, password)
    if (result.user.role !== 'admin') {
      throw new ApiError(403, 'admin_required', 'AutoMarket.exe es solo para administradores de la agencia.')
    }
    sessionStorage.setItem(TOKEN_KEY, result.access_token)
    configureApi({ token: result.access_token })
    setToken(result.access_token)
    setUser(result.user)
    setLogoutReason(null)
  }, [])

  const setApiUrl = useCallback(async (url: string) => {
    const cfg = await window.automarket.setApiUrl(url)
    configureApi({ baseUrl: cfg.apiUrl })
    setApiUrlState(cfg.apiUrl)
  }, [])

  return (
    <AuthContext.Provider value={{ ready, apiUrl, appVersion, user, token, login, logout, setApiUrl, logoutReason }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth fuera de AuthProvider')
  return ctx
}
