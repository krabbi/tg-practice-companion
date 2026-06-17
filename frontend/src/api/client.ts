const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function getToken(): string | null {
  return localStorage.getItem('auth_token')
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (response.status === 401) {
    // Dynamic imports avoid circular deps at module init time (same pattern as router)
    const { useAuthStore } = await import('@/stores/auth')
    useAuthStore().logout()
    const { default: router } = await import('@/router')
    await router.push('/')
    throw new ApiError(401, 'Unauthorized')
  }

  if (response.status === 403) {
    throw new ApiError(403, 'Access denied')
  }

  if (!response.ok) {
    let detail: string | undefined
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, `Request failed: ${response.status}`, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
