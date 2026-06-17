import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('starts unauthenticated when no token in localStorage', () => {
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(false)
    expect(store.token).toBeNull()
  })

  it('reads existing token from localStorage', () => {
    localStorage.setItem('auth_token', 'existing-token')
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(true)
    expect(store.token).toBe('existing-token')
  })

  it('persists token to localStorage on successful login', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ token: 'new-token' }),
      }),
    )

    const store = useAuthStore()
    await store.login('test-init-data')

    expect(store.isAuthenticated).toBe(true)
    expect(store.token).toBe('new-token')
    expect(localStorage.getItem('auth_token')).toBe('new-token')
  })

  it('clears token and localStorage on logout', () => {
    localStorage.setItem('auth_token', 'existing-token')
    const store = useAuthStore()

    store.logout()

    expect(store.isAuthenticated).toBe(false)
    expect(store.token).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })

  it('throws when login request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({}),
      }),
    )

    const store = useAuthStore()
    await expect(store.login('bad-data')).rejects.toThrow()
    expect(store.isAuthenticated).toBe(false)
  })
})
