import { apiFetch } from './client'

export interface PeriodReport {
  date_from: string
  date_to: string
  n_total: number
  n_leads: number
  n_practices: number
  n_good_deeds: number
}

export function getPeriodReport(dateFrom: string, dateTo: string): Promise<PeriodReport> {
  const q = new URLSearchParams({ date_from: dateFrom, date_to: dateTo })
  return apiFetch<PeriodReport>(`/api/reports?${q}`)
}
