import { apiFetch } from './client'

export type ContentType =
  | 'question'
  | 'text'
  | 'audio'
  | 'image'
  | 'video'
  | 'want'
  | 'good_deeds'
  | 'motivational_image'

export type PeriodicityType = 'every_n_hours' | 'fixed_times'

export interface Practice {
  id: string
  name: string
  content_type: ContentType
  content: string | null
  media_asset_id: string | null
  periodicity_type: PeriodicityType
  interval_hours: number | null
  schedule_times: string[] | null
  anchor_hour: number | null
  anchor_minute: number | null
  active: boolean
  start_date: string | null
  end_date: string | null
  sort_order: number
  created_at: string
  updated_at: string
}

export interface PracticeCreate {
  name: string
  content_type: ContentType
  content?: string | null
  media_asset_id?: string | null
  periodicity_type: PeriodicityType
  interval_hours?: number | null
  schedule_times?: string[] | null
  anchor_hour?: number
  anchor_minute?: number
  active?: boolean
  start_date?: string | null
  end_date?: string | null
  sort_order?: number
}

export type PracticeUpdate = Partial<PracticeCreate>

export function listPractices(active?: boolean): Promise<Practice[]> {
  const query = active !== undefined ? `?active=${active}` : ''
  return apiFetch<Practice[]>(`/api/practices${query}`)
}

export function getPractice(id: string): Promise<Practice> {
  return apiFetch<Practice>(`/api/practices/${id}`)
}

export function createPractice(data: PracticeCreate): Promise<Practice> {
  return apiFetch<Practice>('/api/practices', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updatePractice(id: string, data: PracticeUpdate): Promise<Practice> {
  return apiFetch<Practice>(`/api/practices/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export function deletePractice(id: string): Promise<void> {
  return apiFetch<void>(`/api/practices/${id}`, { method: 'DELETE' })
}
