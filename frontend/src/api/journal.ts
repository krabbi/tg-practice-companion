import { apiFetch } from './client'

export interface SelfAssessment {
  leads_to_goals: boolean
  set_via: string
}

export interface JournalEntry {
  id: string
  text: string
  source: string
  created_at: string
  practice_id: string | null
  practice_name: string | null
  self_assessment: SelfAssessment | null
}

export interface JournalListResponse {
  items: JournalEntry[]
  total: number
  page: number
  page_size: number
}

export interface JournalListParams {
  page?: number
  page_size?: number
  date_from?: string
  date_to?: string
  practice_id?: string
}

export function listJournal(params: JournalListParams = {}): Promise<JournalListResponse> {
  const q = new URLSearchParams()
  if (params.page !== undefined) q.set('page', String(params.page))
  if (params.page_size !== undefined) q.set('page_size', String(params.page_size))
  if (params.date_from) q.set('date_from', params.date_from)
  if (params.date_to) q.set('date_to', params.date_to)
  if (params.practice_id) q.set('practice_id', params.practice_id)
  const qs = q.toString()
  return apiFetch<JournalListResponse>(`/api/journal${qs ? `?${qs}` : ''}`)
}

export function getJournalEntry(id: string): Promise<JournalEntry> {
  return apiFetch<JournalEntry>(`/api/journal/${id}`)
}
