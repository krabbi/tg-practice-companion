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

import { listJournal, getJournalEntry } from '@/api/journal'
import { ApiError } from '@/api/client'

const ENTRY = {
  id: 'entry-1',
  text: 'Test entry text',
  source: 'text',
  created_at: '2024-01-15T09:30:00',
  practice_id: 'prac-1',
  practice_name: 'Morning question',
  self_assessment: { leads_to_goals: true, set_via: 'user' },
}

const LIST_RESPONSE = {
  items: [ENTRY],
  total: 1,
  page: 1,
  page_size: 20,
}

function stubFetch(status: number, body: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    }),
  )
}

describe('journal API', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listJournal calls GET /api/journal with no params', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(LIST_RESPONSE),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await listJournal()

    expect(result).toEqual(LIST_RESPONSE)
    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toBe('/api/journal')
  })

  it('listJournal passes page and page_size', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(LIST_RESPONSE),
    })
    vi.stubGlobal('fetch', mockFetch)

    await listJournal({ page: 2, page_size: 10 })

    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toContain('page=2')
    expect(url).toContain('page_size=10')
  })

  it('listJournal passes date_from and date_to filters', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(LIST_RESPONSE),
    })
    vi.stubGlobal('fetch', mockFetch)

    await listJournal({ date_from: '2024-01-01', date_to: '2024-01-31' })

    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toContain('date_from=2024-01-01')
    expect(url).toContain('date_to=2024-01-31')
  })

  it('listJournal passes practice_id filter', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(LIST_RESPONSE),
    })
    vi.stubGlobal('fetch', mockFetch)

    await listJournal({ practice_id: 'prac-abc' })

    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toContain('practice_id=prac-abc')
  })

  it('getJournalEntry calls GET /api/journal/{id}', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(ENTRY),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await getJournalEntry('entry-1')

    expect(result).toEqual(ENTRY)
    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toBe('/api/journal/entry-1')
  })

  it('listJournal throws ApiError on 500', async () => {
    stubFetch(500, { detail: 'Internal Server Error' })

    const err = await listJournal().catch((e) => e)

    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(500)
  })
})
