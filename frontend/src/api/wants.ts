import { apiFetch } from './client'

export interface Want {
  id: string
  user_id: number
  text: string
  done: boolean
  created_at: string
}

export interface WantCreate {
  text: string
}

export interface WantUpdate {
  text?: string
  done?: boolean
}

export function listWants(): Promise<Want[]> {
  return apiFetch<Want[]>('/api/wants')
}

export function createWant(data: WantCreate): Promise<Want> {
  return apiFetch<Want>('/api/wants', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateWant(id: string, data: WantUpdate): Promise<Want> {
  return apiFetch<Want>(`/api/wants/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deleteWant(id: string): Promise<void> {
  return apiFetch<void>(`/api/wants/${id}`, { method: 'DELETE' })
}
