import { apiFetch } from './client'

interface AuthResponse {
  token: string
}

interface MeResponse {
  id: number
  exp: number
}

export async function postTelegramAuth(initData: string): Promise<AuthResponse> {
  return apiFetch<AuthResponse>('/api/auth/telegram', {
    method: 'POST',
    body: JSON.stringify({ init_data: initData }),
  })
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/api/auth/me')
}
