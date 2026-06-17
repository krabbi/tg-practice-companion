import { apiFetch } from './client'

export interface Blessing {
  id: string
  text: string
  rotation_order: number
  active: boolean
}

export interface BlessingCreate {
  text: string
  active?: boolean
}

export interface BlessingUpdate {
  text?: string
  active?: boolean
}

export function listBlessings(): Promise<Blessing[]> {
  return apiFetch<Blessing[]>('/api/blessings')
}

export function createBlessing(data: BlessingCreate): Promise<Blessing> {
  return apiFetch<Blessing>('/api/blessings', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateBlessing(id: string, data: BlessingUpdate): Promise<Blessing> {
  return apiFetch<Blessing>(`/api/blessings/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deleteBlessing(id: string): Promise<void> {
  return apiFetch<void>(`/api/blessings/${id}`, { method: 'DELETE' })
}

export function reorderBlessings(ids: string[]): Promise<Blessing[]> {
  return apiFetch<Blessing[]>('/api/blessings/reorder', {
    method: 'POST',
    body: JSON.stringify({ ids }),
  })
}
