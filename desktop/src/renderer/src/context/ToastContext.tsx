import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

export type ToastTone = 'info' | 'success' | 'warning' | 'error'
interface Toast {
  id: number
  tone: ToastTone
  title: string
  body?: string
}

const ToastContext = createContext<(tone: ToastTone, title: string, body?: string) => void>(() => {})
let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const [toasts, setToasts] = useState<Toast[]>([])

  const push = useCallback((tone: ToastTone, title: string, body?: string) => {
    const id = nextId++
    setToasts((t) => [...t.slice(-4), { id, tone, title, body }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === 'error' ? 8000 : 5000)
  }, [])

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            <strong>{t.title}</strong>
            {t.body && <span>{t.body}</span>}
            <button aria-label="Cerrar" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}>
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = (): ((tone: ToastTone, title: string, body?: string) => void) => useContext(ToastContext)
