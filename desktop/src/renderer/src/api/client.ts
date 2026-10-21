// Cliente HTTP de la API: agrega el token, identifica la app y normaliza los errores.

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, string> = {}
  ) {
    super(message)
  }
}

interface ApiState {
  baseUrl: string
  token: string | null
  onUnauthorized: () => void
}

const state: ApiState = { baseUrl: 'http://localhost:8000', token: null, onUnauthorized: () => {} }

export function configureApi(partial: Partial<ApiState>): void {
  Object.assign(state, partial)
}

export function apiBaseUrl(): string {
  return state.baseUrl
}

/** Las fotos subidas desde la app vienen como /media/...; las del catálogo, como URL absoluta. */
export function mediaUrl(url: string | null | undefined): string | null {
  if (!url) return null
  return url.startsWith('/') ? `${state.baseUrl}${url}` : url
}

type Query = Record<string, string | number | boolean | null | undefined>

export async function api<T>(
  method: string,
  path: string,
  options: { body?: unknown; query?: Query; form?: FormData } = {}
): Promise<T> {
  const url = new URL(`${state.baseUrl}/api/v1${path}`)
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  }

  const headers: Record<string, string> = { 'X-Client-App': 'desktop' }
  if (state.token) headers.Authorization = `Bearer ${state.token}`
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: options.form ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined)
    })
  } catch {
    throw new ApiError(0, 'network_error', `No se pudo conectar con el servidor (${state.baseUrl})`)
  }

  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => null)
  if (response.ok) return data as T

  if (response.status === 401 && state.token) state.onUnauthorized()
  if (response.status === 422 && Array.isArray(data?.detail)) {
    // Errores de validación de Pydantic -> { campo: mensaje }
    const fields: Record<string, string> = {}
    for (const err of data.detail) fields[String(err.loc?.at(-1))] = err.msg
    throw new ApiError(422, 'validation_error', 'Revisa los campos marcados', fields)
  }
  throw new ApiError(response.status, data?.code ?? 'error', data?.detail ?? `Error ${response.status}`)
}
