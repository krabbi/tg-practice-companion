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

import {
  listPractices,
  createPractice,
  updatePractice,
  deletePractice,
} from '@/api/practices'

function stubFetch(status: number, body?: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body ?? null),
    }),
  )
}

const PRACTICE = {
  id: 'abc-123',
  name: 'Morning question',
  content_type: 'question' as const,
  content: 'How are you?',
  media_asset_id: null,
  periodicity_type: 'every_n_hours' as const,
  interval_hours: 4,
  schedule_times: null,
  anchor_hour: 6,
  anchor_minute: 0,
  active: true,
  start_date: null,
  end_date: null,
  sort_order: 0,
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
}

describe('practices API', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listPractices calls GET /api/practices', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve([PRACTICE]),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await listPractices()

    expect(result).toEqual([PRACTICE])
    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toBe('/api/practices')
  })

  it('listPractices passes active query param', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    })
    vi.stubGlobal('fetch', mockFetch)

    await listPractices(true)

    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toBe('/api/practices?active=true')
  })

  it('createPractice calls POST /api/practices', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve(PRACTICE),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await createPractice({
      name: 'Morning question',
      content_type: 'question',
      periodicity_type: 'every_n_hours',
      interval_hours: 4,
    })

    expect(result).toEqual(PRACTICE)
    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/practices')
    expect(opts.method).toBe('POST')
  })

  it('updatePractice calls PATCH /api/practices/{id}', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ ...PRACTICE, active: false }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await updatePractice('abc-123', { active: false })

    expect(result.active).toBe(false)
    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/practices/abc-123')
    expect(opts.method).toBe('PATCH')
  })

  it('deletePractice calls DELETE and returns undefined', async () => {
    stubFetch(204)

    const result = await deletePractice('abc-123')

    expect(result).toBeUndefined()
  })

  it('createPractice surfaces detail from 400 response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'anchor-outside-window' }),
      }),
    )

    const err = await createPractice({
      name: 'Bad',
      content_type: 'question',
      periodicity_type: 'every_n_hours',
      interval_hours: 1,
    }).catch((e) => e)

    expect(err.status).toBe(400)
    expect(err.detail).toBe('anchor-outside-window')
  })
})
