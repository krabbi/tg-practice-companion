import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// Hoist mock references so they are available inside vi.mock() factory functions,
// which are hoisted to the top of the module by Vitest before variable declarations.
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

import { apiFetch, ApiError } from '@/api/client'

describe('apiFetch', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function stubFetch(status: number, body?: unknown): ReturnType<typeof vi.fn> {
    const mock = vi.fn().mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body ?? null),
    })
    vi.stubGlobal('fetch', mock)
    return mock
  }

  it('attaches Authorization Bearer header when a token is stored', async () => {
    localStorage.setItem('auth_token', 'my-token')
    const mockFetch = stubFetch(200, {})

    await apiFetch('/api/test')

    const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }]
    expect(opts.headers['Authorization']).toBe('Bearer my-token')
  })

  it('sends no Authorization header when no token is stored', async () => {
    const mockFetch = stubFetch(200, {})

    await apiFetch('/api/test')

    const [, opts] = mockFetch.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }]
    expect(opts.headers['Authorization']).toBeUndefined()
  })

  it('returns parsed JSON on a successful response', async () => {
    const payload = { id: 1, name: 'item' }
    stubFetch(200, payload)

    const result = await apiFetch('/api/resource')

    expect(result).toEqual(payload)
  })

  it('returns undefined for 204 No Content', async () => {
    stubFetch(204)

    const result = await apiFetch('/api/resource')

    expect(result).toBeUndefined()
  })

  it('calls logout and navigates to / on 401, throws ApiError(401)', async () => {
    stubFetch(401)

    const error = await apiFetch('/api/protected').catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(401)
    expect(mockLogout).toHaveBeenCalledOnce()
    expect(mockRouterPush).toHaveBeenCalledWith('/')
  })

  it('throws ApiError(403) without calling logout on 403', async () => {
    stubFetch(403)

    const error = await apiFetch('/api/forbidden').catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(403)
    expect(mockLogout).not.toHaveBeenCalled()
    expect(mockRouterPush).not.toHaveBeenCalled()
  })

  it('throws ApiError with the response status code for other non-OK responses', async () => {
    stubFetch(500)

    const error = await apiFetch('/api/error').catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(500)
    expect(mockLogout).not.toHaveBeenCalled()
  })
})
