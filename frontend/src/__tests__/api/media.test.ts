import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { ApiError } from '@/api/client'

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

import { listMediaAssets, deleteMediaAsset, createMotivationalImage, uploadMediaAsset, getMediaUrl } from '@/api/media'

function stubFetch(status: number, body?: unknown): ReturnType<typeof vi.fn> {
  const mock = vi.fn().mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body ?? null),
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

class MockXHR {
  open = vi.fn()
  setRequestHeader = vi.fn()
  send = vi.fn()
  status = 0
  responseText = ''
  upload = { addEventListener: vi.fn() }
  addEventListener = vi.fn()

  trigger(type: string): void {
    const calls = this.addEventListener.mock.calls as [string, () => void][]
    calls.find(([t]) => t === type)?.[1]?.()
  }

  triggerProgress(loaded: number, total: number): void {
    const calls = this.upload.addEventListener.mock.calls as [
      string,
      (e: { lengthComputable: boolean; loaded: number; total: number }) => void,
    ][]
    calls
      .find(([t]) => t === 'progress')?.[1]?.({ lengthComputable: true, loaded, total })
  }
}

const ASSET = {
  id: 'asset-1',
  kind: 'image' as const,
  storage_path: '/uploads/img.jpg',
  telegram_file_id: null,
  mime: 'image/jpeg',
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
}

describe('media API', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('listMediaAssets', () => {
    it('calls GET /api/media with no filter', async () => {
      const mockFetch = stubFetch(200, [ASSET])

      const result = await listMediaAssets()

      expect(result).toEqual([ASSET])
      const [url] = mockFetch.mock.calls[0] as [string]
      expect(url).toBe('/api/media')
    })

    it('calls GET /api/media?kind=image with kind filter', async () => {
      const mockFetch = stubFetch(200, [ASSET])

      await listMediaAssets('image')

      const [url] = mockFetch.mock.calls[0] as [string]
      expect(url).toBe('/api/media?kind=image')
    })
  })

  describe('deleteMediaAsset', () => {
    it('calls DELETE /api/media/{id} and returns undefined', async () => {
      const mockFetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 204,
        json: () => Promise.resolve(null),
      })
      vi.stubGlobal('fetch', mockFetch)

      const result = await deleteMediaAsset('asset-1')

      expect(result).toBeUndefined()
      const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
      expect(url).toBe('/api/media/asset-1')
      expect(opts.method).toBe('DELETE')
    })
  })

  describe('createMotivationalImage', () => {
    it('calls POST /api/motivational-images and returns the created record', async () => {
      const motivImg = { id: 'motiv-1', media_asset_id: 'asset-1', active: true }
      const mockFetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: () => Promise.resolve(motivImg),
      })
      vi.stubGlobal('fetch', mockFetch)

      const result = await createMotivationalImage({ media_asset_id: 'asset-1', active: true })

      expect(result).toEqual(motivImg)
      const [url, opts] = mockFetch.mock.calls[0] as [string, RequestInit]
      expect(url).toBe('/api/motivational-images')
      expect(opts.method).toBe('POST')
    })
  })

  describe('getMediaUrl', () => {
    it('calls GET /api/media/{id}/url and returns presigned URL response', async () => {
      const presigned = { url: 'https://s3.example.com/img.jpg?sig=abc', expires_in: 900 }
      const mockFetch = stubFetch(200, presigned)

      const result = await getMediaUrl('asset-1')

      expect(result).toEqual(presigned)
      const [url] = mockFetch.mock.calls[0] as [string]
      expect(url).toBe('/api/media/asset-1/url')
    })
  })

  describe('uploadMediaAsset', () => {
    let mockXHR: MockXHR

    beforeEach(() => {
      mockXHR = new MockXHR()
      vi.stubGlobal('XMLHttpRequest', vi.fn(() => mockXHR))
    })

    it('resolves with MediaAsset on 201 status', async () => {
      mockXHR.status = 201
      mockXHR.responseText = JSON.stringify(ASSET)
      const file = new File(['content'], 'img.jpg', { type: 'image/jpeg' })

      const promise = uploadMediaAsset(file, 'image')
      mockXHR.trigger('load')

      expect(await promise).toEqual(ASSET)
    })

    it('sets Authorization header when token is stored', async () => {
      localStorage.setItem('auth_token', 'my-token')
      mockXHR.status = 201
      mockXHR.responseText = JSON.stringify(ASSET)
      const file = new File(['content'], 'img.jpg', { type: 'image/jpeg' })

      const promise = uploadMediaAsset(file, 'image')
      mockXHR.trigger('load')
      await promise

      expect(mockXHR.setRequestHeader).toHaveBeenCalledWith('Authorization', 'Bearer my-token')
    })

    it('rejects with ApiError containing detail on non-201 load', async () => {
      mockXHR.status = 413
      mockXHR.responseText = JSON.stringify({ detail: 'File too large' })
      const file = new File(['content'], 'img.jpg', { type: 'image/jpeg' })

      const promise = uploadMediaAsset(file, 'image')
      mockXHR.trigger('load')

      const err = await promise.catch((e) => e)
      expect(err).toBeInstanceOf(ApiError)
      expect((err as ApiError).status).toBe(413)
      expect((err as ApiError).detail).toBe('File too large')
    })

    it('rejects with ApiError(0) on network error', async () => {
      const file = new File(['content'], 'img.jpg', { type: 'image/jpeg' })

      const promise = uploadMediaAsset(file, 'image')
      mockXHR.trigger('error')

      const err = await promise.catch((e) => e)
      expect(err).toBeInstanceOf(ApiError)
      expect((err as ApiError).status).toBe(0)
    })

    it('rejects with ApiError(0) on abort', async () => {
      const file = new File(['content'], 'img.jpg', { type: 'image/jpeg' })

      const promise = uploadMediaAsset(file, 'image')
      mockXHR.trigger('abort')

      const err = await promise.catch((e) => e)
      expect(err).toBeInstanceOf(ApiError)
      expect((err as ApiError).status).toBe(0)
    })

    it('calls onProgress callback with computed percentage', async () => {
      mockXHR.status = 201
      mockXHR.responseText = JSON.stringify(ASSET)
      const onProgress = vi.fn()
      const file = new File(['content'], 'img.jpg', { type: 'image/jpeg' })

      const promise = uploadMediaAsset(file, 'image', onProgress)
      mockXHR.triggerProgress(50, 100)
      mockXHR.trigger('load')
      await promise

      expect(onProgress).toHaveBeenCalledWith(50)
    })
  })
})
