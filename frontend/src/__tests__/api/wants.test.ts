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

import { listWants, createWant, updateWant, deleteWant } from '@/api/wants'

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

const WANT = {
  id: 'uuid-want-1',
  user_id: 1,
  text: 'Learn piano',
  done: false,
  created_at: '2024-01-01T00:00:00',
}

describe('wants API', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listWants calls GET /api/wants', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve([WANT]),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await listWants()

    expect(result).toEqual([WANT])
    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toBe('/api/wants')
  })

  it('createWant calls POST /api/wants', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve(WANT),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await createWant({ text: 'Learn piano' })

    expect(result).toEqual(WANT)
    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/wants')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body as string)).toEqual({ text: 'Learn piano' })
  })

  it('updateWant calls PATCH /api/wants/{id}', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ ...WANT, done: true }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await updateWant('uuid-want-1', { done: true })

    expect(result.done).toBe(true)
    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/wants/uuid-want-1')
    expect(opts.method).toBe('PATCH')
  })

  it('deleteWant calls DELETE and returns undefined', async () => {
    stubFetch(204)

    const result = await deleteWant('uuid-want-1')

    expect(result).toBeUndefined()
  })

  it('createWant surfaces detail from 422 response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: 'text too short' }),
      }),
    )

    const err = await createWant({ text: '' }).catch((e) => e)

    expect(err.status).toBe(422)
    expect(err.detail).toBe('text too short')
  })
})
