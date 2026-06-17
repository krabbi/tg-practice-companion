import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

const { mockLogout, mockRouterPush } = vi.hoisted(() => ({
  mockLogout: vi.fn(),
  mockRouterPush: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({ logout: mockLogout })),
}))

vi.mock('@/router', () => ({
  default: { push: mockRouterPush },
}))

import { getPeriodReport } from '@/api/reports'
import { ApiError } from '@/api/client'

const REPORT = {
  date_from: '2024-01-01',
  date_to: '2024-01-31',
  n_total: 42,
  n_leads: 30,
  n_practices: 100,
  n_good_deeds: 5,
}

describe('reports API', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('getPeriodReport calls GET /api/reports with date params', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(REPORT),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await getPeriodReport('2024-01-01', '2024-01-31')

    expect(result).toEqual(REPORT)
    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toContain('/api/reports')
    expect(url).toContain('date_from=2024-01-01')
    expect(url).toContain('date_to=2024-01-31')
  })

  it('getPeriodReport throws ApiError on 422', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: 'date_from is required' }),
      }),
    )

    const err = await getPeriodReport('', '').catch((e) => e)

    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(422)
    expect(err.detail).toBe('date_from is required')
  })
})
