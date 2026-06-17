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
  listBlessings,
  createBlessing,
  updateBlessing,
  deleteBlessing,
  reorderBlessings,
} from '@/api/blessings'

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

const BLESSING = {
  id: 'uuid-blessing-1',
  text: 'Have a wonderful day!',
  rotation_order: 1,
  active: true,
}

describe('blessings API', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listBlessings calls GET /api/blessings', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve([BLESSING]),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await listBlessings()

    expect(result).toEqual([BLESSING])
    const [url] = mockFetch.mock.calls[0] as [string]
    expect(url).toBe('/api/blessings')
  })

  it('createBlessing calls POST /api/blessings', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve(BLESSING),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await createBlessing({ text: 'Have a wonderful day!', active: true })

    expect(result).toEqual(BLESSING)
    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/blessings')
    expect(opts.method).toBe('POST')
  })

  it('updateBlessing calls PATCH /api/blessings/{id}', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ ...BLESSING, active: false }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await updateBlessing('uuid-blessing-1', { active: false })

    expect(result.active).toBe(false)
    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/blessings/uuid-blessing-1')
    expect(opts.method).toBe('PATCH')
  })

  it('deleteBlessing calls DELETE and returns undefined', async () => {
    stubFetch(204)

    const result = await deleteBlessing('uuid-blessing-1')

    expect(result).toBeUndefined()
  })

  it('reorderBlessings calls POST /api/blessings/reorder', async () => {
    const ids = ['uuid-2', 'uuid-1']
    const reordered = [
      { ...BLESSING, id: 'uuid-2', rotation_order: 1 },
      { ...BLESSING, id: 'uuid-1', rotation_order: 2 },
    ]
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(reordered),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await reorderBlessings(ids)

    expect(result).toEqual(reordered)
    const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/blessings/reorder')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body as string)).toEqual({ ids })
  })

  it('createBlessing surfaces detail from 422 response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: 'text too short' }),
      }),
    )

    const err = await createBlessing({ text: '' }).catch((e) => e)

    expect(err.status).toBe(422)
    expect(err.detail).toBe('text too short')
  })
})
